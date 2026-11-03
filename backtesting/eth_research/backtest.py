"""Cost-aware, unlevered research simulation; no execution or account connection."""
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass
class Assumptions:
    fee_bps_per_side: float = 4.0
    slippage_bps_per_side: float = 2.0
    swap_bps_daily: float = 3.3
    profit_share: float = .90
    notional_fraction: float = .10
    # Leave unset until the user's actual account plan is known.
    daily_loss_limit: float | None = None
    total_loss_limit: float | None = None

    def __post_init__(self):
        if not 0 < self.notional_fraction <= 1 or not 0 < self.profit_share <= 1:
            raise ValueError("Use positive unlevered notional fraction and profit share <= 1")
        if min(self.fee_bps_per_side, self.slippage_bps_per_side, self.swap_bps_daily) < 0:
            raise ValueError("Costs cannot be negative")
        for limit in [self.daily_loss_limit, self.total_loss_limit]:
            if limit is not None and not 0 < limit < 1:
                raise ValueError("Loss limits must be fractions between 0 and 1")


def simulate(frame, probability, threshold=.5, assumptions=None):
    cfg = assumptions or Assumptions()
    probability = np.asarray(probability, dtype=float)
    if len(frame) != len(probability) or not np.isfinite(probability).all():
        raise ValueError("Backtest predictions must match the rows")
    # Each signal is held for exactly one future five-minute bar and closed.
    direction = np.where(probability >= threshold, 1, np.where(probability <= 1 - threshold, -1, 0))
    if threshold == 1.0:
        direction[:] = 0  # explicit no-trade candidate
    trades = frame[["timestamp", "entry_time", "label_end", "entry", "exit", "exit_low", "exit_high", "forward_return"]].copy()
    trades["probability_up"] = probability
    trades["direction"] = direction
    cost = (cfg.fee_bps_per_side + cfg.slippage_bps_per_side) / 10000
    # Terminal financing: 3.3bp/day, charged at four-hour boundaries.
    snapshots = (pd.to_datetime(trades.label_end, utc=True).dt.as_unit("ns").astype("int64") // (4 * 3600 * 10**9) -
                 pd.to_datetime(trades.entry_time, utc=True).dt.as_unit("ns").astype("int64") // (4 * 3600 * 10**9))
    swap = snapshots.to_numpy() * cfg.swap_bps_daily / 6 / 10000
    gross = direction * trades.forward_return.to_numpy()
    # Exit fee charged on exit notional; both sides assume adverse slippage.
    net = gross - cost * (1 + trades.exit.to_numpy() / trades.entry.to_numpy()) - swap
    net = np.where(direction != 0, net, 0.)
    adverse = np.where(direction > 0, trades.exit_low / trades.entry - 1,
                       1 - trades.exit_high / trades.entry)
    adverse = np.where(direction != 0, adverse - 2 * cost - swap, 0.)
    equity, peak, worst_dd, balance_floor = 1., 1., 0., 1.
    daily_start, risk_day, breaches = 1., None, []
    stopped = False
    curve, pnls, worst_marks, executed = [], [], [], []
    for i, row in enumerate(trades.itertuples()):
        day = (row.entry_time - pd.Timedelta(minutes=30)).date()
        if day != risk_day:
            risk_day, daily_start = day, equity
        active = direction[i] != 0 and not stopped
        # Fixed fraction of initial capital, capped to current equity; no leverage.
        notional = min(cfg.notional_fraction, max(0, equity)) if active else 0.
        worst = equity + notional * adverse[i]
        pnl = notional * net[i]
        daily_floor = daily_start - (cfg.daily_loss_limit or float("inf"))
        total_floor = 1 - (cfg.total_loss_limit or float("inf"))
        if active and worst <= max(daily_floor, total_floor):
            # A breached funded account is forfeited; stop further simulated trading.
            breaches.append({"timestamp": str(row.entry_time), "worst_equity": float(worst),
                             "reason": "daily" if daily_floor >= total_floor else "total"})
            stopped = True
        if not active:
            pnl, worst = 0., equity
        worst_dd = max(worst_dd, (peak - worst) / peak)
        balance_floor = min(balance_floor, worst)
        equity += pnl
        peak = max(peak, equity)
        curve.append(equity)
        pnls.append(pnl)
        worst_marks.append(worst)
        executed.append(active)
    trades["executed"] = executed
    trades["pnl_fraction_initial"] = pnls
    trades["equity_fraction_initial"] = curve
    trades["worst_intrabar_equity"] = worst_marks
    active_pnl = np.asarray(pnls)[np.asarray(executed)]
    wins = active_pnl[active_pnl > 0].sum()
    losses = -active_pnl[active_pnl < 0].sum()
    metrics = {"trades": len(active_pnl), "net_return": equity - 1,
               "win_rate_after_costs": float((active_pnl > 0).mean()) if len(active_pnl) else None,
               "profit_factor": float(wins / losses) if losses else None,
               "max_intrabar_drawdown": float(worst_dd), "minimum_intrabar_equity": float(balance_floor),
               "trader_share_of_positive_net_profit": max(0., equity - 1) * cfg.profit_share,
               "breaches": breaches,
               "rule_compliance_evaluated": cfg.daily_loss_limit is not None and cfg.total_loss_limit is not None,
               "assumptions": asdict(cfg)}
    return metrics, trades

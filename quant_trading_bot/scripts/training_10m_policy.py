"""Policy and Qualification Gates for 10,000,000 Institutional Search.
Mandate:
- Zero data contamination: 100% Training split (2020-2023) across 4 chronological folds.
- Strict funded account rule: Intrabar DD strictly < $1,750 on every fold.
- High Expectancy: Ranks configurations by (Win Rate * Profit Factor * Weekly PnL / Drawdown).
"""
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

SPECS = {
    "MNQ": {"tick": 0.25, "multiplier": 2.0},
    "MES": {"tick": 0.25, "multiplier": 5.0},
}


def execution_cfg_10m(c, factor=1):
    symbol = c["instrument"]
    spec = SPECS[symbol]
    qty = int(c.get("max_contracts", 1))

    risk_trade = 150.0 * qty
    daily_lim = 400.0 * qty

    return dict(
        initial_balance=50000.0,
        tick=spec["tick"],
        multiplier=spec["multiplier"],
        commission_per_side=0.50,
        exchange_per_side=0.0,
        regulatory_per_side=0.0,
        spread_ticks=1,
        slippage_ticks=1,
        impact_ticks=0.25 * (qty - 1),
        factor=factor,
        maxqty=qty,
        risk_per_trade=risk_trade,
        max_open_risk=risk_trade,
        daily_loss=daily_lim,
        hard_drawdown=2000.0,
        stop_atr=float(c["stop_atr"]),
        target_ratio=float(c["target_r"]),
        hold_bars=int(c["hold_bars"]),
        entry_start=int(c["session_start"]) - 15,
        entry_end=int(c["session_end"]) - 30,
        flat_minute=min(int(c["session_end"]), 955),
        max_gap_minutes=20,
        participation=0.01,
        trailing_atr=float(c["trailing_atr"]),
        max_consecutive_losses=5,
        funded_drawdown=2000.0,
        funded_cap=50100.0,
    )


def aggregate_10m(c, fold_metrics, signal):
    """Aggregate fold metrics and rank by Win Rate and Profit Factor."""
    trades = sum((m.get('trades') or 0) for m in fold_metrics)
    net_pnl = sum((m.get('net_pnl') or 0.0) for m in fold_metrics)
    realized_dd = max((m.get('realized_drawdown') or 0.0) for m in fold_metrics) if fold_metrics else 0.0
    closing_dd = max((m.get('max_drawdown') or 0.0) for m in fold_metrics) if fold_metrics else 0.0
    intrabar_dd = max((m.get('intrabar_drawdown') or 0.0) for m in fold_metrics) if fold_metrics else 0.0
    locks = sum((m.get('lock') or 0) for m in fold_metrics)
    funded_failed = sum((m.get('funded_failed') or 0) for m in fold_metrics)

    wins = sum((m.get('positive_trade_pnl') or 0.0) for m in fold_metrics)
    loss = abs(sum((m.get('negative_trade_pnl') or 0.0) for m in fold_metrics))
    pf = (wins / loss) if loss > 0 else (99.0 if wins > 0 else 0.0)

    total_wins_approx = sum(round((m.get('trades') or 0) * (m.get('win_rate') or 0.0)) for m in fold_metrics)
    win_rate = (total_wins_approx / trades) if trades > 0 else 0.0

    pos_folds = sum(1 for m in fold_metrics if (m.get('net_pnl') or 0.0) > 0)
    max_fold_dd = max((m.get('intrabar_drawdown') or 0.0) for m in fold_metrics) if fold_metrics else 0.0

    annual_pnl = net_pnl / 4.0
    weekly_pnl = annual_pnl / 52.0
    trades_per_week = trades / 208.0
    weeks_to_3k = (3000.0 / weekly_pnl) if weekly_pnl > 0 else 999.0
    dd_cushion = max(0.0, 2000.0 - intrabar_dd)

    champ_score = (win_rate * 100.0) * pf * (weekly_pnl / (1.0 + intrabar_dd)) * (pos_folds / 4.0)

    # Strict Institutional Qualification Gates:
    # 1. Net profit >= $6,500 across training folds
    # 2. Minimum 35 trades
    # 3. Positive in at least 3 of 4 folds
    # 4. Intrabar drawdown strictly < $1,750 ($250 safety buffer)
    # 5. Max single fold drawdown strictly < $1,750
    # 6. Zero locks, zero funded failures
    # 7. Win rate >= 45%
    # 8. Profit factor >= 1.50
    qualified = bool(
        net_pnl >= 6500.0 and
        trades >= 35 and
        pos_folds >= 3 and
        intrabar_dd < 1750.0 and
        max_fold_dd < 1750.0 and
        locks == 0 and
        funded_failed == 0 and
        win_rate >= 0.45 and
        pf >= 1.50
    )

    return {
        "config_id": c["config_id"],
        "instrument": c["instrument"],
        "family": c["family"],
        "contracts": int(c["max_contracts"]),
        "net_pnl": round(float(net_pnl), 2),
        "intrabar_drawdown": round(float(intrabar_dd), 2),
        "max_fold_drawdown": round(float(max_fold_dd), 2),
        "win_rate": round(float(win_rate), 4),
        "profit_factor": round(float(pf), 3),
        "trades": int(trades),
        "trades_per_week": round(float(trades_per_week), 2),
        "weekly_pnl": round(float(weekly_pnl), 2),
        "weeks_to_3k": round(float(weeks_to_3k), 1),
        "positive_folds": int(pos_folds),
        "champ_score": round(float(champ_score), 4),
        "qualified": qualified,
        "payload": json.dumps(c)
    }

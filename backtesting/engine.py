"""Event-driven DVS state machine and OHLC broker-emulator approximation.

Parity mode is a source-faithful candidate, not a certified TradingView match.
Every execution assumption and the source hash are exported with each run.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import math

import numpy as np
import pandas as pd

from .config import StrategyConfig
from .indicators import prepare_indicators
from .market_data import BAR, clean_candles
from .paths import PINE, PINE_V1


@dataclass
class Setup:
    direction: int = 0
    level: float = float("nan")
    bar: int = -1
    retested: bool = False
    extreme: float = float("nan")

    def clear(self):
        # Pine leaves setupLevel/setupBar stale when it resets the setup.
        self.direction, self.retested, self.extreme = 0, False, float("nan")


@dataclass
class Position:
    direction: int
    quantity: float
    entry_price: float
    stop: float
    target: float
    entry_bar_open: pd.Timestamp
    entry_time: pd.Timestamp
    entry_commission_remaining: float
    swap_remaining: float = 0.
    initial_risk: float = 0.


@dataclass
class BacktestResult:
    metrics: dict
    trades: pd.DataFrame
    equity: pd.DataFrame
    signals: pd.DataFrame
    events: pd.DataFrame
    config: dict
    quality: dict
    provenance: dict


class Broker:
    def __init__(self, config: StrategyConfig):
        self.cfg = config
        self.cash = config.initial_capital
        self.position: Position | None = None
        self.trades: list[dict] = []
        self.events: list[dict] = []
        self.peak = config.initial_capital
        self.max_drawdown = 0.
        self.closed_equity_peak = config.initial_capital
        self.closed_equity_drawdown_usd = 0.
        self.closed_equity_drawdown_fraction = 0.
        self.total_commission = self.total_swap = 0.
        self.margin_calls = 0
        self.bar_worst = config.initial_capital

    def equity_at(self, price: float) -> float:
        p = self.position
        return self.cash + (p.direction * p.quantity * (price - p.entry_price) * self.cfg.point_value if p else 0.)

    def mark(self, price: float):
        equity = self.equity_at(price)
        self.peak = max(self.peak, equity)
        self.bar_worst = min(self.bar_worst, equity)
        self.max_drawdown = max(self.max_drawdown, (self.peak - equity) / self.peak)
        # TradingView's intrabar metric anchors to equity before trades, not
        # an unrealized intratrade high-water mark. Preserve both conventions.
        if self.position is None:
            self.closed_equity_peak = max(self.closed_equity_peak, self.cash)
        deficit = max(0., self.closed_equity_peak - equity)
        self.closed_equity_drawdown_usd = max(self.closed_equity_drawdown_usd, deficit)
        self.closed_equity_drawdown_fraction = max(self.closed_equity_drawdown_fraction, deficit / self.closed_equity_peak)

    def market_price(self, price: float, order_direction: int) -> float:
        return price + order_direction * (self.cfg.slippage_ticks * self.cfg.tick_size + price * self.cfg.slippage_bps / 10000)

    def enter(self, direction: int, quantity: float, close: float, stop: float, target: float,
              bar_open: pd.Timestamp, fill_time: pd.Timestamp):
        if self.position is not None or quantity <= 0:
            raise ValueError("Pyramiding is disabled")
        fill = self.market_price(close, direction)
        commission = quantity * fill * self.cfg.point_value * self.cfg.commission_bps / 10000
        self.cash -= commission
        self.total_commission += commission
        self.position = Position(direction, quantity, fill, stop, target, bar_open, fill_time, commission)
        self.position.initial_risk = abs(fill - stop)
        self.events.append({"bar_open": bar_open, "event": "entry", "direction": direction, "quantity": quantity, "price": fill})
        self.mark(close)

    def exit(self, price: float, bar_open: pd.Timestamp, reason: str, phase: str, quantity=None):
        p = self.position
        if p is None:
            return
        quantity = min(p.quantity, quantity if quantity is not None else p.quantity)
        fill = price if reason == "target" else self.market_price(price, -p.direction)
        commission = quantity * fill * self.cfg.point_value * self.cfg.commission_bps / 10000
        fraction = quantity / p.quantity
        entry_commission = p.entry_commission_remaining * fraction
        swap = p.swap_remaining * fraction
        gross = p.direction * quantity * (fill - p.entry_price) * self.cfg.point_value
        self.cash += gross - commission
        self.total_commission += commission
        self.trades.append({"entry_bar_open": p.entry_bar_open, "entry_time": p.entry_time,
                            "exit_bar_open": bar_open, "exit_time": bar_open if phase == "open" else bar_open + BAR,
                            "exit_time_is_upper_bound": phase != "open", "exit_phase": phase,
                            "direction": "LONG" if p.direction == 1 else "SHORT", "quantity": quantity,
                            "entry_price": p.entry_price, "exit_price": fill, "stop": p.stop, "target": p.target,
                            "gross_pnl": gross, "commission": commission + entry_commission, "swap": swap,
                            "net_pnl": gross - commission - entry_commission - swap, "reason": reason})
        self.events.append({"bar_open": bar_open, "event": reason, "quantity": quantity, "price": fill})
        p.quantity -= quantity
        p.entry_commission_remaining -= entry_commission
        p.swap_remaining -= swap
        if p.quantity < .0005:
            self.position = None
        self.mark(price)

    def _margin(self, price, bar_open, phase):
        p = self.position
        if p is None:
            return
        deficit = p.quantity * price * self.cfg.point_value * self.cfg.margin_ratio - self.equity_at(price)
        cover = math.floor(max(0., deficit) / self.cfg.margin_ratio / (price * self.cfg.point_value) * 1000 + 1e-8) / 1000
        if cover > 0:
            self.margin_calls += 1
            self.exit(price, bar_open, "margin_call", phase, quantity=min(p.quantity, 4 * cover))

    def _margin_level(self):
        p = self.position
        if p is None:
            return None
        denominator = p.direction * p.quantity - self.cfg.margin_ratio * max(0., p.quantity - .001)
        level = (p.direction * p.quantity * p.entry_price - self.cash / self.cfg.point_value) / denominator
        # First adverse instrument tick at which at least .001 ETH can be covered.
        units = level / self.cfg.tick_size
        return (math.floor(units) if p.direction == 1 else math.ceil(units)) * self.cfg.tick_size

    def bar(self, row):
        self.bar_worst = self.equity_at(row.open)
        p = self.position
        if p is None:
            self.mark(row.open)
            return
        if self.cfg.swap_daily_bps and row.timestamp.hour % 4 == 0 and row.timestamp.minute == 0:
            cost = p.quantity * row.open * self.cfg.point_value * self.cfg.swap_daily_bps / 6 / 10000
            self.cash -= cost
            self.total_swap += cost
            p.swap_remaining += cost
            self.events.append({"bar_open": row.timestamp, "event": "financing", "amount": cost})
        # Gap crossings fill at the new open, never at a skipped stop/limit price.
        stop_gap = row.open <= p.stop if p.direction == 1 else row.open >= p.stop
        target_gap = row.open >= p.target if p.direction == 1 else row.open <= p.target
        if stop_gap or target_gap:
            self.exit(row.open, row.timestamp, "stop" if stop_gap else "target", "open")
            return
        self._margin(row.open, row.timestamp, "open")
        self.mark(row.open)
        if self.position is None:
            return
        p = self.position
        both = row.low <= min(p.stop, p.target) and row.high >= max(p.stop, p.target)
        if self.cfg.intrabar_policy == "stop_first" and both:
            self.mark(p.stop)
            self.exit(p.stop, row.timestamp, "stop", "research_stop_first")
            return
        # Historical OHLC path, without bar magnifier. Equal-distance tie uses low first.
        path = [row.open, row.high, row.low, row.close] if abs(row.open - row.high) < abs(row.open - row.low) else [row.open, row.low, row.high, row.close]
        for start, end in zip(path, path[1:]):
            current = start
            for _ in range(100):
                if self.position is None:
                    break
                p = self.position
                levels = [(p.stop, "stop"), (p.target, "target")]
                margin = self._margin_level()
                if margin is not None and margin > 0:
                    levels.append((margin, "margin_call"))
                crossing = [(price, reason) for price, reason in levels
                            if min(current, end) <= price <= max(current, end)
                            and (price != current or reason != "margin_call")]
                if not crossing:
                    self.mark(end)
                    break
                price, reason = min(crossing, key=lambda value: abs(value[0] - current))
                self.mark(price)
                if reason == "margin_call":
                    before = p.quantity
                    self._margin(price, row.timestamp, "intrabar")
                    if self.position is not None and self.position.quantity == before:
                        self.mark(end)
                        break
                    current = price
                else:
                    self.exit(price, row.timestamp, reason, "intrabar")
                    break
            else:
                raise RuntimeError("Margin event loop exceeded its bound")


def backtest(bars: pd.DataFrame, config: StrategyConfig | None = None,
             indicators: pd.DataFrame | None = None, quality: dict | None = None,
             capture_details: bool = True) -> BacktestResult:
    cfg = config or StrategyConfig()
    v11 = cfg.strategy_version == "v1.1"
    bars, actual_quality = clean_candles(bars)
    quality = quality or actual_quality
    if cfg.gap_policy == "reject" and (actual_quality["missing_bars"] or quality.get("missing_bars", 0)):
        raise ValueError("Missing candles: parity run rejected. Repair data or explicitly use research gap segmentation.")
    frame = prepare_indicators(bars) if indicators is None else indicators.reset_index(drop=True)
    if len(frame) != len(bars) or not frame.timestamp.equals(bars.timestamp):
        raise ValueError("Indicator rows must match candle timestamps exactly")
    broker, setup = Broker(cfg), Setup()
    entries_today, day_start_equity, day, previous_row, pending = 0, cfg.initial_capital, None, None, None
    daily_locked = False
    last_retest_bar = -1  # Pine's var persists across setup resets.
    trace, curve = [], []
    daily_equity, total_entries = {}, 0
    last_exit_bar = -10**9
    filtered_entries = 0
    for i, row in enumerate(frame.itertuples(index=False)):
        gap = previous_row is not None and row.timestamp - previous_row.timestamp != BAR
        if gap:
            if broker.position:
                broker.exit(previous_row.close, previous_row.timestamp, "gap_boundary", "research_close")
            setup.clear()
            pending = None
        exits_before_bar = len(broker.trades)
        broker.bar(row)
        if pending is not None and broker.position is None:
            direction, quantity, stop, target = pending
            broker.enter(direction, quantity, row.open, stop, target, row.timestamp, row.timestamp)
            # Next-open mode participates in this bar's subsequent range.
            broker.bar(row)
            pending = None
        if broker.position is not None and cfg.mode == "research":
            p = broker.position
            held_bars = (row.timestamp + BAR - p.entry_time) / BAR
            if cfg.max_holding_bars and held_bars >= cfg.max_holding_bars:
                broker.exit(row.close, row.timestamp, "time_stop", "research_close")
            else:
                favorable = p.direction * (row.close - p.entry_price)
                proposed_stop = p.stop
                if cfg.breakeven_r and favorable >= cfg.breakeven_r * p.initial_risk:
                    cost = estimated_round_trip_cost(cfg, p.entry_price)
                    proposed_stop = p.entry_price + p.direction * cost
                if cfg.trail_atr and favorable >= max(1., cfg.breakeven_r) * p.initial_risk:
                    trailing = row.close - p.direction * cfg.trail_atr * row.atr5
                    proposed_stop = max(proposed_stop, trailing) if p.direction == 1 else min(proposed_stop, trailing)
                tighter = proposed_stop > p.stop if p.direction == 1 else proposed_stop < p.stop
                placeable = p.direction * (row.close - proposed_stop) > cfg.tick_size
                if tighter and placeable:
                    p.stop = proposed_stop
                    broker.events.append({"bar_open": row.timestamp, "event": "stop_update", "price": proposed_stop,
                                          "effective_at": row.timestamp + BAR})
        if len(broker.trades) > exits_before_bar and broker.position is None:
            last_exit_bar = i
        equity = broker.equity_at(row.close)
        if row.timestamp.date() != day:
            day, day_start_equity, entries_today = row.timestamp.date(), equity, 0
            daily_locked = False
        if v11 and equity <= day_start_equity - cfg.max_daily_loss:
            daily_locked = True
        can_trade = (not daily_locked if v11 else equity > day_start_equity - cfg.max_daily_loss) and entries_today < cfg.max_trades_day
        long_break = bool(row.new15 and row.bull_bias and pd.notna(row.res15) and row.p15 <= row.res15
                          and row.c15 > row.res15 and row.v15 >= cfg.breakout_rvol)
        short_break = bool(row.new15 and row.bear_bias and pd.notna(row.sup15) and row.p15 >= row.sup15
                           and row.c15 < row.sup15 and row.v15 >= cfg.breakout_rvol)
        expired = setup.direction != 0 and (i - setup.bar > cfg.max_setup_bars or
                  (setup.direction == 1 and not row.bull_bias) or (setup.direction == -1 and not row.bear_bias))
        if expired or (v11 and not can_trade):
            setup.clear()
        if broker.position is None and can_trade:
            if long_break or short_break:
                setup = Setup(1 if long_break else -1, row.res15 if long_break else row.sup15, i)
        active = can_trade and broker.position is None and setup.direction != 0 and i > setup.bar
        near = active and row.low <= setup.level + cfg.retest_atr * row.atr5 and row.high >= setup.level - cfg.retest_atr * row.atr5
        if near and ((setup.direction == 1 and row.close >= setup.level) or (setup.direction == -1 and row.close <= setup.level)):
            value = row.low if setup.direction == 1 else row.high
            setup.extreme = value if math.isnan(setup.extreme) else (min(setup.extreme, value) if setup.direction == 1 else max(setup.extreme, value))
            setup.retested = True
        failed = active and ((setup.direction == 1 and row.close < setup.level - cfg.retest_atr * row.atr5) or
                             (setup.direction == -1 and row.close > setup.level + cfg.retest_atr * row.atr5))
        if failed:
            setup.clear()
        # Preserve Pine statement order: nearLevel was computed before failure
        # clearing; lastRetestBar updates whenever nearLevel AND retested holds,
        # including later nearby candles that do not update the extreme.
        if v11 and near and setup.retested:
            last_retest_bar = i
        after_retest = not v11 or i > last_retest_bar
        confirm_long = active and setup.direction == 1 and setup.retested and after_retest and row.close > row.open and row.close > row.previous_high and row.rv5 >= cfg.entry_rvol
        confirm_short = active and setup.direction == -1 and setup.retested and after_retest and row.close < row.open and row.close < row.previous_low and row.rv5 >= cfg.entry_rvol
        entered = False
        if confirm_long or confirm_short:
            direction = 1 if confirm_long else -1
            stop = setup.extreme - direction * cfg.stop_atr * row.atr5
            distance = abs(row.close - stop)
            valid = stop < row.close if direction == 1 else stop > row.close
            allowed = research_entry_allowed(cfg, row, direction) and i - last_exit_bar >= cfg.cooldown_bars
            if cfg.mode == "research":
                distance = max(distance, cfg.min_stop_bps / 10000 * row.close, cfg.min_stop_atr * row.atr5)
                stop = row.close - direction * distance
            sizing_multiplier = cfg.point_value if v11 else 1.
            estimated_cost = estimated_round_trip_cost(cfg, row.close)
            risk_distance = distance + (estimated_cost if cfg.risk_includes_costs else 0.)
            quantity = math.floor(min(cfg.risk_usd / (risk_distance * sizing_multiplier), equity * cfg.max_leverage / (row.close * sizing_multiplier)) * 1000) / 1000 if risk_distance > 0 else 0.
            target = row.close + direction * cfg.reward_r * distance
            allowed = allowed and cfg.reward_r * distance >= cfg.min_reward_cost_ratio * estimated_cost
            if valid and distance > cfg.tick_size and quantity > 0 and allowed:
                if cfg.entry_timing == "signal_close":
                    broker.enter(direction, quantity, row.close, stop, target, row.timestamp, row.timestamp + BAR)
                else:
                    pending = (direction, quantity, stop, target)
                entries_today += 1
                total_entries += 1
                entered = True
            elif not allowed:
                filtered_entries += 1
            setup.clear()
        broker.mark(row.close)
        daily_equity[(row.timestamp + BAR).date()] = broker.equity_at(row.close)
        if capture_details:
            curve.append({"timestamp": row.timestamp + BAR, "cash": broker.cash, "equity": broker.equity_at(row.close),
                      "intrabar_worst_equity": broker.bar_worst, "position_qty": broker.position.quantity * broker.position.direction if broker.position else 0.})
            trace.append({"timestamp": row.timestamp, "bull_bias": row.bull_bias, "bear_bias": row.bear_bias,
                      "long_break": long_break, "short_break": short_break, "can_trade": can_trade,
                      "setup_direction": setup.direction, "setup_level": setup.level, "retested": setup.retested,
                      "retest_extreme": setup.extreme, "expired": expired, "failed": failed,
                      "confirm_long": bool(confirm_long), "confirm_short": bool(confirm_short),
                      "entered": entered, "entries_today": entries_today, "day_start_equity": day_start_equity,
                      "daily_locked": daily_locked, "last_retest_bar": last_retest_bar if last_retest_bar >= 0 else None})
        previous_row = row
    trades = pd.DataFrame(broker.trades)
    equity_curve = pd.DataFrame(curve)
    net = trades.net_pnl if len(trades) else pd.Series(dtype=float)
    gains, losses = net.clip(lower=0).sum(), -net.clip(upper=0).sum()
    daily_returns = pd.Series(daily_equity).pct_change().dropna()
    final = float(broker.equity_at(previous_row.close))
    metrics = {"initial_capital": cfg.initial_capital, "final_equity": final, "final_cash": broker.cash,
               "net_return": final / cfg.initial_capital - 1, "closed_trade_legs": len(trades),
               "entries": total_entries, "filtered_entry_signals": filtered_entries,
               "win_rate": float((net > 0).mean()) if len(net) else None,
               "profit_factor": float(gains / losses) if losses else None,
               "max_intrabar_drawdown": broker.max_drawdown, "total_commission": broker.total_commission,
               "max_closed_equity_drawdown_usd": broker.closed_equity_drawdown_usd,
               "max_closed_equity_drawdown_fraction": broker.closed_equity_drawdown_fraction,
               "total_swap": broker.total_swap, "margin_call_events": broker.margin_calls,
               "daily_sharpe": float(daily_returns.mean() / daily_returns.std() * np.sqrt(365)) if daily_returns.std() > 0 else None,
               "open_position": asdict(broker.position) if broker.position else None,
               "illustrative_90pct_profit_share": max(0., final - cfg.initial_capital) * cfg.profit_share if cfg.mode == "research" else None}
    pine_source = PINE if v11 else PINE_V1
    provenance = {"source": "Binance ETHUSDT USD-M perpetual futures", "pine_file": str(pine_source),
                  "pine_sha256": hashlib.sha256(pine_source.read_bytes()).hexdigest(),
                  "pine_title": f"DVS ETH {cfg.strategy_version} | Bias + Structure + Volume",
                  "parity_status": "unverified: requires TradingView signal/trade export reconciliation",
                  "execution": "OHLC path; no bar magnifier; equal-distance path uses low first; intrabar timestamps are bounds",
                  "drawdown": "both unrealized running-peak and closed-trade-equity-peak conventions; neither export-verified",
                  "margin": "documented four-times truncated cover quantity; broker ordering remains unverified",
                  "funded_account_compliance": "not assessed; personal Pine risk controls are not prop-firm rules"}
    signal_frame = pd.DataFrame(trace)
    # Fixed nullable integer schema; future retests must not change the dtype
    # of an earlier all-NA prefix during replay/export.
    if capture_details:
        signal_frame["last_retest_bar"] = pd.array(signal_frame.last_retest_bar, dtype="Int64")
    return BacktestResult(metrics, trades, equity_curve, signal_frame, pd.DataFrame(broker.events),
                          asdict(cfg), quality, provenance)


def estimated_round_trip_cost(cfg: StrategyConfig, price: float) -> float:
    """Cost per unit of quoted price, excluding unknowable future financing."""
    return 2 * price * (cfg.commission_bps + cfg.slippage_bps) / 10000 + 2 * cfg.slippage_ticks * cfg.tick_size


def research_entry_allowed(cfg: StrategyConfig, row, direction: int) -> bool:
    if cfg.mode != "research":
        return True
    if cfg.trade_direction != "both" and direction != (1 if cfg.trade_direction == "long" else -1):
        return False
    if not cfg.allow_weekends and row.timestamp.dayofweek >= 5:
        return False
    hour = row.timestamp.hour
    if cfg.session == "europe_us" and not 7 <= hour < 21:
        return False
    if cfg.session == "us" and not 13 <= hour < 21:
        return False
    if cfg.session == "asia" and not 0 <= hour < 8:
        return False
    atr_bps = row.atr5 / row.close * 10000
    if atr_bps < cfg.min_atr_bps or (cfg.max_atr_bps and atr_bps > cfg.max_atr_bps):
        return False
    if cfg.min_trend_gap_bps:
        if not hasattr(row, "close4h") or not hasattr(row, "ema4h") or not math.isfinite(row.ema4h):
            return False
        if direction * (row.close4h / row.ema4h - 1) * 10000 < cfg.min_trend_gap_bps:
            return False
    return True

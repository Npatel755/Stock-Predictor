"""Candidate execution: frozen hourly logic with a separate sizing cost budget.

This separate implementation preserves the hash-locked v1.11 simulator. The
only strategy change is the slippage assumption used to calculate quantity.
Market/stop fills still use config.slippage_bps, never the sizing reserve.
"""
from __future__ import annotations

from dataclasses import asdict, replace
import math

import pandas as pd

from .alternative_strategies import prepare_signals
from .engine import Broker, estimated_round_trip_cost
from .market_data import BAR, clean_candles


def sizing_config(config, sizing_slippage_bps):
    if not math.isfinite(sizing_slippage_bps) or sizing_slippage_bps < 0:
        raise ValueError('Sizing slippage must be finite and nonnegative')
    return replace(config, slippage_bps=sizing_slippage_bps)


def simulate(bars, rule, config, signals=None, *, sizing_slippage_bps=8., validator=None):
    """Replay one reserve; no threshold search or changes to fill assumptions."""
    if config.mode != 'research' or config.entry_timing != 'next_open':
        raise ValueError('Independent strategies require next-open Research execution')
    reserve_config = sizing_config(config, sizing_slippage_bps)
    bars, quality = (clean_candles if validator is None else validator)(bars)
    if quality['missing_bars']:
        raise ValueError('Independent strategy research rejects missing candles')
    frame = prepare_signals(bars, rule) if signals is None else signals.reset_index(drop=True)
    if len(frame) != len(bars) or not frame.timestamp.equals(bars.timestamp):
        raise ValueError('Signal rows must match candle timestamps')
    broker = Broker(config)
    pending = None
    entries = entries_today = 0
    day, start_equity, locked = None, config.initial_capital, False
    for row in frame.itertuples(index=False):
        broker.bar(row)
        if pending is not None:
            direction, quantity, stop, target = pending
            broker.enter(direction, quantity, row.open, stop, target, row.timestamp, row.timestamp)
            broker.bar(row)
            pending = None
        if broker.position:
            p = broker.position
            held = (row.timestamp+BAR-p.entry_time)/BAR
            if rule.max_holding_bars and held >= rule.max_holding_bars:
                broker.exit(row.close, row.timestamp, 'time_stop', 'research_close')
            elif rule.trail_atr and math.isfinite(row.management_atr):
                proposed = row.close-p.direction*rule.trail_atr*row.management_atr
                tighter = proposed > p.stop if p.direction == 1 else proposed < p.stop
                if tighter and p.direction*(row.close-proposed) > config.tick_size:
                    p.stop = proposed
                    broker.events.append(dict(bar_open=row.timestamp, event='stop_update', price=proposed, effective_at=row.timestamp+BAR))
        equity = broker.equity_at(row.close)
        if day != row.timestamp.date():
            day, start_equity, entries_today, locked = row.timestamp.date(), equity, 0, False
        if equity <= start_equity-config.max_daily_loss:
            locked = True
        if row.signal and not broker.position and not locked and entries_today < config.max_trades_day and math.isfinite(row.signal_atr):
            direction = int(row.signal)
            distance = rule.stop_atr*row.signal_atr
            risk_distance = distance+estimated_round_trip_cost(reserve_config, row.close)
            quantity = math.floor(min(config.risk_usd/(risk_distance*config.point_value),
                                      equity*config.max_leverage/(row.close*config.point_value))*1000)/1000
            if distance > config.tick_size and quantity > 0:
                pending = (direction, quantity, row.close-direction*distance, row.close+direction*rule.reward_r*distance)
                entries_today += 1
                entries += 1
        broker.mark(row.close)
    trades = pd.DataFrame(broker.trades)
    net = trades.net_pnl if len(trades) else pd.Series(dtype=float)
    gains, losses = net.clip(lower=0).sum(), -net.clip(upper=0).sum()
    metrics = dict(initial_capital=config.initial_capital, final_equity=broker.equity_at(frame.close.iloc[-1]),
                   entries=entries, closed_trade_legs=len(trades), win_rate=float((net > 0).mean()) if len(net) else None,
                   profit_factor=float(gains/losses) if losses else None,
                   max_intrabar_drawdown=broker.max_drawdown, max_closed_equity_drawdown_usd=broker.closed_equity_drawdown_usd,
                   total_commission=broker.total_commission, total_swap=broker.total_swap, margin_call_events=broker.margin_calls,
                   open_position=asdict(broker.position) if broker.position else None)
    return metrics, trades, pd.DataFrame(broker.events)

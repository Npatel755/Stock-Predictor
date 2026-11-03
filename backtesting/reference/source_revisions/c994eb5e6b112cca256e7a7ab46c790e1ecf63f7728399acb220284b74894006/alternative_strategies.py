"""Independent hourly ETH signals executed on real five-minute candles.

No DVS bias/pivot/retest logic is used. Signals use only a completed hour and
are sent after its final five-minute candle; entries fill at the next open.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math

import numpy as np
import pandas as pd

from .config import StrategyConfig
from .engine import Broker, estimated_round_trip_cost
from .indicators import resample_complete, rma
from .market_data import BAR, clean_candles


@dataclass(frozen=True)
class SignalRule:
    family: str
    lookback: int = 20
    slow: int = 50
    stop_atr: float = 2.
    reward_r: float = 2.
    trail_atr: float = 0.
    max_holding_bars: int = 0

    def __post_init__(self):
        if self.family not in {"ema_cross", "channel_breakout", "bollinger_reversion"}:
            raise ValueError("Unknown independent strategy family")
        if self.lookback < 2 or self.slow <= self.lookback or min(self.stop_atr, self.reward_r) <= 0 or self.trail_atr < 0 or self.max_holding_bars < 0:
            raise ValueError("Invalid signal parameters")


def prepare_signals(bars: pd.DataFrame, rule: SignalRule) -> pd.DataFrame:
    """Place a completed hour's signal on its final constituent 5m close."""
    hours = resample_complete(bars, "1h")
    c = hours.close
    tr = pd.concat([hours.high-hours.low, (hours.high-c.shift()).abs(), (hours.low-c.shift()).abs()], axis=1).max(axis=1)
    atr = rma(tr, 14)
    fast = c.ewm(span=rule.lookback, adjust=False).mean()
    slow = c.ewm(span=rule.slow, adjust=False).mean()
    ready = c.expanding().count() >= rule.slow
    if rule.family == "ema_cross":
        long = (fast > slow) & (fast.shift() <= slow.shift())
        short = (fast < slow) & (fast.shift() >= slow.shift())
    elif rule.family == "channel_breakout":
        upper = hours.high.shift().rolling(rule.lookback).max()
        lower = hours.low.shift().rolling(rule.lookback).min()
        long = (c > upper) & (c > slow)
        short = (c < lower) & (c < slow)
    else:
        middle = c.rolling(rule.lookback).mean()
        deviation = c.rolling(rule.lookback).std(ddof=0)
        upper, lower = middle+2*deviation, middle-2*deviation
        # Return inside a two-standard-deviation band, confirmed at hourly close.
        long = (c.shift() < lower.shift()) & (c >= lower)
        short = (c.shift() > upper.shift()) & (c <= upper)
    # ATR's original hourly index must not be label-aligned against the shifted
    # availability index; carry values positionally with the signal.
    hourly = pd.DataFrame(dict(signal=np.where(ready & long, 1, np.where(ready & short, -1, 0)), signal_atr=atr.to_numpy()), index=hours.index+pd.Timedelta(minutes=55))
    mapped = hourly.reindex(pd.DatetimeIndex(bars.timestamp))
    mapped.index = bars.index
    output = bars.copy()
    output["signal"] = mapped.signal.fillna(0).astype(int)
    output["signal_atr"] = mapped.signal_atr
    # Management can use the most recently completed hour's ATR on any later bar.
    known_atr = pd.Series(atr.to_numpy(), index=hours.index+pd.Timedelta(minutes=55))
    output["management_atr"] = known_atr.reindex(pd.DatetimeIndex(bars.timestamp), method="ffill").to_numpy()
    return output


def simulate(bars: pd.DataFrame, rule: SignalRule, config: StrategyConfig, signals=None):
    """Shared Broker costs, OHLC path, financing and margin; independent signals."""
    if config.mode != "research" or config.entry_timing != "next_open":
        raise ValueError("Independent strategies require next-open Research execution")
    bars, quality = clean_candles(bars)
    if quality["missing_bars"]:
        raise ValueError("Independent strategy research rejects missing candles")
    frame = prepare_signals(bars, rule) if signals is None else signals.reset_index(drop=True)
    if len(frame) != len(bars) or not frame.timestamp.equals(bars.timestamp):
        raise ValueError("Signal rows must match candle timestamps")
    broker = Broker(config)
    pending = None
    entries = 0
    entries_today = 0
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
                broker.exit(row.close, row.timestamp, "time_stop", "research_close")
            elif rule.trail_atr and math.isfinite(row.management_atr):
                proposed = row.close-p.direction*rule.trail_atr*row.management_atr
                tighter = proposed > p.stop if p.direction == 1 else proposed < p.stop
                if tighter and p.direction*(row.close-proposed) > config.tick_size:
                    p.stop = proposed
                    broker.events.append(dict(bar_open=row.timestamp, event="stop_update", price=proposed, effective_at=row.timestamp+BAR))
        equity = broker.equity_at(row.close)
        if day != row.timestamp.date():
            day, start_equity, entries_today, locked = row.timestamp.date(), equity, 0, False
        if equity <= start_equity-config.max_daily_loss:
            locked = True
        if row.signal and not broker.position and not locked and entries_today < config.max_trades_day and math.isfinite(row.signal_atr):
            direction = int(row.signal)
            distance = rule.stop_atr*row.signal_atr
            risk_distance = distance+estimated_round_trip_cost(config, row.close)
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

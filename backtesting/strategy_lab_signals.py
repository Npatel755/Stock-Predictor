"""Causal signal families for a bounded, chronological development experiment.

Signals become available only at the last five-minute close of a completed
1h/4h candle. No backdated signals, current partial candles or future pivots.
"""
from dataclasses import dataclass
import math

import numpy as np
import pandas as pd

from .alternative_strategies import SignalRule
from .indicators import resample_complete, rma
from .market_data import BAR


FAMILIES = ('trend_pullback', 'rsi_pullback', 'squeeze_breakout',
            'supertrend', 'range_reversion', 'time_series_momentum')


@dataclass(frozen=True)
class LabRule:
    family: str
    timeframe_hours: int
    stop_atr: float
    reward_r: float
    trail_atr: float

    def __post_init__(self):
        if self.family not in FAMILIES or self.timeframe_hours not in {1, 4}:
            raise ValueError('Unknown lab family or timeframe')
        if not all(math.isfinite(x) and x > 0 for x in [self.stop_atr, self.reward_r, self.trail_atr]):
            raise ValueError('Lab exit settings must be positive and finite')

    def execution_rule(self):
        # The existing execution loop receives explicit signals; this object
        # supplies bracket/trailing geometry only, never its EMA-cross signals.
        return SignalRule('ema_cross', lookback=20, slow=200, stop_atr=self.stop_atr,
                          reward_r=self.reward_r, trail_atr=self.trail_atr)


def rsi(close, length):
    change = close.diff()
    gain, loss = rma(change.clip(lower=0), length), rma((-change).clip(lower=0), length)
    value = 100-100/(1+gain/loss.replace(0., np.nan))
    return value.mask(loss.eq(0) & gain.gt(0), 100.).mask(loss.eq(0) & gain.eq(0), 50.)


def supertrend_direction(hours, atr, multiplier=3.):
    upper = (hours.high+hours.low)/2+multiplier*atr
    lower = (hours.high+hours.low)/2-multiplier*atr
    directions = np.zeros(len(hours), dtype=int)
    previous_upper = previous_lower = previous_close = float('nan')
    direction = 0
    for i, (up, down, close) in enumerate(zip(upper, lower, hours.close)):
        if not np.isfinite([up, down, close]).all():
            continue
        if direction == 0:
            direction = 1
        else:
            if close > previous_upper:
                direction = 1
            elif close < previous_lower:
                direction = -1
            up = up if up < previous_upper or previous_close > previous_upper else previous_upper
            down = down if down > previous_lower or previous_close < previous_lower else previous_lower
        directions[i] = direction
        previous_upper, previous_lower, previous_close = up, down, close
    return pd.Series(directions, index=hours.index)


def prepare(bars, rule):
    hours = resample_complete(bars, f'{rule.timeframe_hours}h')
    c = hours.close
    tr = pd.concat([hours.high-hours.low, (hours.high-c.shift()).abs(),
                    (hours.low-c.shift()).abs()], axis=1).max(axis=1)
    atr = rma(tr, 14)
    fast, slow = c.ewm(span=20, adjust=False).mean(), c.ewm(span=200, adjust=False).mean()
    ready = c.expanding().count() >= 200
    # A single fixed volume gate for trend families, not optimized by venue.
    volume_ok = hours.volume >= hours.volume.shift().rolling(20).mean()
    if rule.family == 'trend_pullback':
        long = (c > fast) & (c.shift() <= fast.shift()) & (c > slow)
        short = (c < fast) & (c.shift() >= fast.shift()) & (c < slow)
    elif rule.family == 'rsi_pullback':
        value = rsi(c, 2)
        long = (value > 10) & (value.shift() <= 10) & (c > slow)
        short = (value < 90) & (value.shift() >= 90) & (c < slow)
    elif rule.family == 'squeeze_breakout':
        middle, deviation = c.rolling(20).mean(), c.rolling(20).std(ddof=0)
        upper, lower = middle+2*deviation, middle-2*deviation
        squeeze = (upper < fast+1.5*atr) & (lower > fast-1.5*atr)
        preceding_squeeze = squeeze.shift().rolling(6).max().eq(1)
        long = preceding_squeeze & (c > upper) & (c.shift() <= upper.shift()) & (c > slow)
        short = preceding_squeeze & (c < lower) & (c.shift() >= lower.shift()) & (c < slow)
    elif rule.family == 'supertrend':
        direction = supertrend_direction(hours, atr)
        long = direction.eq(1) & direction.shift().eq(-1) & (c > slow)
        short = direction.eq(-1) & direction.shift().eq(1) & (c < slow)
    elif rule.family == 'time_series_momentum':
        momentum = c/c.shift(20)-1
        long = (momentum > 0) & (momentum.shift() <= 0) & (c > slow)
        short = (momentum < 0) & (momentum.shift() >= 0) & (c < slow)
    else:
        up, down = hours.high.diff(), -hours.low.diff()
        plus = pd.Series(np.where((up > down) & (up > 0), up, 0.), index=hours.index)
        minus = pd.Series(np.where((down > up) & (down > 0), down, 0.), index=hours.index)
        pdi, mdi = 100*rma(plus, 14)/atr, 100*rma(minus, 14)/atr
        adx = rma(100*(pdi-mdi).abs()/(pdi+mdi).replace(0., np.nan), 14)
        value = rsi(c, 14)
        range_ok = (adx < 20) & ((c-slow).abs() <= 2*atr)
        long = range_ok & (value > 30) & (value.shift() <= 30)
        short = range_ok & (value < 70) & (value.shift() >= 70)
        volume_ok = pd.Series(True, index=hours.index)
    availability = hours.index+pd.Timedelta(hours=rule.timeframe_hours)-BAR
    hourly = pd.DataFrame(dict(signal=np.where(ready & volume_ok & long, 1,
                                      np.where(ready & volume_ok & short, -1, 0)),
                               signal_atr=atr.to_numpy()), index=availability)
    mapped = hourly.reindex(pd.DatetimeIndex(bars.timestamp))
    output = bars.copy()
    output['signal'] = mapped.signal.fillna(0).to_numpy(dtype=int)
    output['signal_atr'] = mapped.signal_atr.to_numpy()
    output['management_atr'] = pd.Series(atr.to_numpy(), index=availability).reindex(
        pd.DatetimeIndex(bars.timestamp), method='ffill').to_numpy()
    return output

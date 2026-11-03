"""Completed-hour entry filters for independent ETH strategies.

Filters modify only the existing signal column. Broker rules, position size,
stops, targets and management remain in the frozen independent simulator.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import pandas as pd

from .alternative_strategies import prepare_signals
from .indicators import resample_complete


@dataclass(frozen=True)
class RegimeFilter:
    direction: str = 'both'
    min_atr_bps: float = 0.
    max_atr_bps: float = 0.
    min_trend_gap_bps: float = 0.
    min_signed_slope_bps: float | None = None
    min_rvol: float = 0.
    weekends: bool = True

    def __post_init__(self):
        if self.direction not in {'both', 'long', 'short'}:
            raise ValueError('Unknown filter direction')
        values = [self.min_atr_bps, self.max_atr_bps, self.min_trend_gap_bps, self.min_rvol]
        if not all(math.isfinite(v) and v >= 0 for v in values):
            raise ValueError('Filter thresholds must be finite and nonnegative')
        if self.max_atr_bps and self.max_atr_bps < self.min_atr_bps:
            raise ValueError('ATR upper bound is below its lower bound')
        if self.min_signed_slope_bps is not None and (not math.isfinite(self.min_signed_slope_bps) or self.min_signed_slope_bps < 0):
            raise ValueError('EMA slope threshold must be finite and nonnegative')


def prepare_features(bars, rule):
    frame = prepare_signals(bars, rule)
    hourly = resample_complete(bars, '1h')
    ema = hourly.close.ewm(span=rule.slow, adjust=False).mean()
    derived = pd.DataFrame({
        'trend_gap_bps': (hourly.close/ema-1).to_numpy()*10000,
        'ema_slope_6h_bps': (ema/ema.shift(6)-1).to_numpy()*10000,
        'hourly_rvol': (hourly.volume/hourly.volume.shift().rolling(20).mean().replace(0, float('nan'))).to_numpy(),
    }, index=hourly.index+pd.Timedelta(minutes=55))
    mapped = derived.reindex(pd.DatetimeIndex(frame.timestamp))
    for name in derived.columns:
        frame[name] = mapped[name].to_numpy()
    frame['hourly_atr_bps'] = frame.signal_atr/frame.close*10000
    return frame


def apply_filter(features, settings):
    frame = features.copy()
    keep = pd.Series(True, index=frame.index)
    if settings.direction != 'both':
        keep &= frame.signal == (1 if settings.direction == 'long' else -1)
    if settings.min_atr_bps:
        keep &= frame.hourly_atr_bps >= settings.min_atr_bps
    if settings.max_atr_bps:
        keep &= frame.hourly_atr_bps <= settings.max_atr_bps
    if settings.min_trend_gap_bps:
        keep &= frame.signal*frame.trend_gap_bps >= settings.min_trend_gap_bps
    if settings.min_signed_slope_bps is not None:
        keep &= frame.signal*frame.ema_slope_6h_bps >= settings.min_signed_slope_bps
    if settings.min_rvol:
        keep &= frame.hourly_rvol >= settings.min_rvol
    if not settings.weekends:
        keep &= frame.timestamp.dt.dayofweek < 5
    frame['signal'] = frame.signal.where(keep, 0).astype(int)
    return frame

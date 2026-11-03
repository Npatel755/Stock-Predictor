import numpy as np
import pandas as pd

from backtesting.funding_fade_lab import CONFIRMS, FADE_RULE, PERCENTILES, candidates, fade_signals, settled_rate_by_hour
from backtesting.indicators import resample_complete
from backtesting.market_data import BAR
from test_dvs import candles


def settlements_for(bars, rate=lambda i: 1.+(i % 3)):
    times = pd.date_range(bars.timestamp.iloc[0].floor('8h'), bars.timestamp.iloc[-1], freq='8h', tz='UTC')
    return pd.DataFrame(dict(timestamp=times, rate_8h_bps=[rate(i) for i in range(len(times))]))


def test_candidate_universe_and_geometry_are_fixed():
    rows = candidates()
    assert len(rows) == 6 and len({r['id'] for r in rows}) == 6 and rows == candidates()
    assert {r['percentile'] for r in rows} == set(PERCENTILES) and {r['confirm'] for r in rows} == set(CONFIRMS)
    assert (FADE_RULE.stop_atr, FADE_RULE.reward_r, FADE_RULE.trail_atr, FADE_RULE.max_holding_bars) == (2., 3., 0., 96*12)


def test_settled_rate_uses_only_settlements_published_before_the_hour_closes():
    bars = candles(5000)
    hours = resample_complete(bars, '1h')
    settlements = settlements_for(bars)
    rate = settled_rate_by_hour(hours, settlements)
    for hour, value in rate.dropna().items():
        available = hour+pd.Timedelta(hours=1)-BAR
        eligible = settlements[settlements.timestamp+pd.Timedelta(hours=1) <= available]
        assert value == eligible.rate_8h_bps.iloc[-1]
    # A settlement published after the hour's final close must not leak into that hour.
    late = settlements.copy()
    late.loc[len(late)] = dict(timestamp=hours.index[100]+pd.Timedelta(minutes=30), rate_8h_bps=999.)
    assert settled_rate_by_hour(hours, late.sort_values('timestamp').reset_index(drop=True)).iloc[100] != 999.


def test_fade_signals_are_prefix_causal_and_fire_once_per_state():
    bars = candles(30000)
    settlements = settlements_for(bars, rate=lambda i: float(np.sin(i/5.)*5))
    candidate = candidates()[1]
    frame = fade_signals(bars, settlements, candidate)
    assert len(frame) == len(bars) and set(frame.signal.unique()) <= {-1, 0, 1}
    changed = bars.copy()
    changed.loc[25000:, ['open', 'high', 'low', 'close', 'volume']] *= 2
    other = fade_signals(changed, settlements, candidate)
    cutoff = bars.timestamp.iloc[25000]-pd.Timedelta(hours=2)
    pd.testing.assert_series_equal(frame.signal[frame.timestamp < cutoff], other.signal[other.timestamp < cutoff])
    hourly = frame[frame.signal != 0]
    assert (hourly.timestamp.diff().dropna() >= pd.Timedelta(hours=1)).all()
    assert hourly.signal_atr.notna().all()

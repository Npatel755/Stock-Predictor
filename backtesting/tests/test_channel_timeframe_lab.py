import pandas as pd
import pytest

from backtesting.channel_timeframe_lab import candidates, prepare, geometry
from test_dvs import candles


@pytest.mark.parametrize('hours', [1, 4, 24])
@pytest.mark.parametrize('length', [20, 55])
def test_channel_timeframes_use_only_completed_prior_channels(hours, length):
    candidate = next(c for c in candidates() if c['hours'] == hours and c['length'] == length)
    bars = candles(74000)
    frame = prepare(bars, candidate)
    prefix = prepare(bars.iloc[:70003], candidate)
    pd.testing.assert_frame_equal(frame.iloc[:70003], prefix, check_exact=True)
    changed = bars.copy()
    changed.loc[70003:, ['open', 'high', 'low', 'close', 'volume']] *= 4
    pd.testing.assert_frame_equal(frame.iloc[:70003], prepare(changed, candidate).iloc[:70003], check_exact=True)
    signals = frame[frame.signal.ne(0)]
    assert signals.timestamp.dt.minute.eq(55).all()
    assert signals.timestamp.dt.hour.mod(hours).eq(hours-1).all()
    if len(signals):
        assert signals.timestamp.min() >= bars.timestamp.iloc[hours*12*200-1]
    assert geometry(candidate).max_holding_bars == 0


def test_channel_candidate_budget_is_exactly_twelve_without_hidden_thresholds():
    variants = candidates()
    assert len(variants) == 12 and len({c['id'] for c in variants}) == 12
    assert set(c['hours'] for c in variants) == {1, 4, 24}
    assert set(c['length'] for c in variants) == {20, 55}

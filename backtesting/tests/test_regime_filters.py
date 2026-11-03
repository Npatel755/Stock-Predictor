from dataclasses import replace

import pandas as pd
import pytest

from backtesting.alternative_strategies import SignalRule, prepare_signals, simulate
from backtesting.optimize import baseline
from backtesting.regime_filters import RegimeFilter, apply_filter, prepare_features
from test_dvs import candles


def test_filter_features_and_signals_are_causal_at_partial_hour_boundaries():
    bars = candles(5000)
    rule = SignalRule('channel_breakout', lookback=20, slow=50)
    original = prepare_features(bars, rule)
    changed = bars.copy()
    changed.loc[3503:, ['open', 'high', 'low', 'close', 'volume']] *= 3
    other = prepare_features(changed, rule)
    pd.testing.assert_frame_equal(original.iloc[:3503], other.iloc[:3503])
    pd.testing.assert_frame_equal(prepare_features(bars.iloc[:3503], rule), original.iloc[:3503])
    filtered = apply_filter(original, RegimeFilter(min_trend_gap_bps=50, min_signed_slope_bps=0, min_rvol=1))
    pd.testing.assert_frame_equal(filtered.iloc[:3503], apply_filter(other, RegimeFilter(min_trend_gap_bps=50, min_signed_slope_bps=0, min_rvol=1)).iloc[:3503])
    assert original.loc[original.signal.ne(0), ['hourly_atr_bps', 'trend_gap_bps', 'ema_slope_6h_bps', 'hourly_rvol']].notna().all().all()


def test_neutral_filter_reproduces_the_unmodified_simulator_exactly():
    bars = candles(5000)
    rule = SignalRule('channel_breakout', lookback=20, slow=50)
    plain = prepare_signals(bars, rule)
    filtered = apply_filter(prepare_features(bars, rule), RegimeFilter())
    pd.testing.assert_frame_equal(filtered[plain.columns], plain)
    cfg = replace(baseline(), risk_includes_costs=True)
    a, at, ae = simulate(bars, rule, cfg, signals=plain)
    b, bt, be = simulate(bars, rule, cfg, signals=filtered)
    assert a == b
    pd.testing.assert_frame_equal(at, bt)
    pd.testing.assert_frame_equal(ae, be)


def test_signed_trend_filters_treat_short_and_long_symmetrically():
    data = pd.DataFrame(dict(timestamp=pd.to_datetime(['2025-01-06 00:55Z']*4), signal=[1, -1, 1, -1],
                             hourly_atr_bps=[40]*4, trend_gap_bps=[60, -60, -60, 60],
                             ema_slope_6h_bps=[8, -8, 8, -8], hourly_rvol=[2]*4))
    f = RegimeFilter(min_atr_bps=20, max_atr_bps=80, min_trend_gap_bps=50, min_signed_slope_bps=5, min_rvol=1)
    assert apply_filter(data, f).signal.tolist() == [1, -1, 0, 0]
    assert apply_filter(data, RegimeFilter(direction='short')).signal.tolist() == [0, -1, 0, -1]
    data['timestamp'] = pd.to_datetime(['2025-01-05 00:55Z']*4)
    assert apply_filter(data, RegimeFilter(weekends=False)).signal.eq(0).all()
    assert apply_filter(data, RegimeFilter(min_rvol=3)).signal.eq(0).all()


@pytest.mark.parametrize('values', [dict(direction='buy'), dict(min_atr_bps=-1), dict(min_atr_bps=80, max_atr_bps=40),
                                     dict(min_rvol=float('nan')), dict(min_signed_slope_bps=float('inf'))])
def test_invalid_filters_cannot_enter_an_experiment(values):
    with pytest.raises(ValueError):
        RegimeFilter(**values)

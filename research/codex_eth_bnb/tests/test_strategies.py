import numpy as np
import pandas as pd
import pytest

from research.codex_eth_bnb.strategies import build_features, build_signal, library


def candles(n=1800, freq='5min', start='2021-01-01', seed=9):
    rng = np.random.default_rng(seed)
    close = 100.*np.exp(np.cumsum(rng.normal(.00001, .002, n)))
    open_ = np.r_[100., close[:-1]]
    result = pd.DataFrame(dict(timestamp=pd.date_range(start, periods=n, freq=freq, tz='UTC'),
                               open=open_, close=close, high=np.maximum(open_, close)*1.002,
                               low=np.minimum(open_, close)*.998, volume=rng.uniform(1, 100, n)))
    return result


def test_library_is_bounded_deterministic_and_identifiable():
    specs = library()
    assert specs == library()
    assert len(specs) == 60
    assert sum(not spec['baseline'] for spec in specs) == 48
    assert len({spec['id'] for spec in specs}) == 60
    assert {spec['timeframe'] for spec in specs} == {'5m', '15m', '1h', '4h'}
    assert all(spec['mechanism'] for spec in specs)


def test_all_primary_signals_and_features_are_prefix_equivalent():
    bars = candles()
    context = dict(BTC=candles(seed=2), BNB=candles(seed=4))
    full_features = build_features(bars, context)
    prefix = 1237  # Deliberately leaves a higher-timeframe candle unfinished.
    prefix_features = build_features(bars.iloc[:prefix], {key: value.iloc[:prefix] for key, value in context.items()})
    for name in ('atr', 'rv', 'rv_reference', 'rv_ratio', 'autocorr', 'trend_strength', 'session_vwap', 'htf_trend', 'regime', 'regime_detail', 'liquidity_regime', 'serial_regime', 'context_BTC_close'):
        pd.testing.assert_series_equal(full_features[name].iloc[:prefix].reset_index(drop=True), prefix_features[name], check_names=False)
    for spec in library():
        if spec['timeframe'] != '5m':
            continue
        spec = {**spec, 'symbol': 'ETH'}
        complete = build_signal(full_features, spec)
        partial = build_signal(prefix_features, spec)
        np.testing.assert_array_equal(complete.signal.iloc[:prefix], partial.signal)
        assert set(complete.signal.unique()).issubset({-1, 0, 1})
        assert len(complete) == len(bars)


def test_changing_future_prices_cannot_change_past_features_or_signals():
    original = candles(900)
    changed = original.copy()
    changed.loc[600:, ['open', 'high', 'low', 'close']] *= 10
    a, b = build_features(original), build_features(changed)
    for spec in library():
        if spec['timeframe'] == '5m':
            np.testing.assert_array_equal(build_signal(a, spec).signal.iloc[:600], build_signal(b, spec).signal.iloc[:600])


def test_utc_session_vwap_resets_and_handles_zero_volume_without_filling():
    bars = candles(4, start='2021-01-01 23:50')
    bars.loc[2, 'volume'] = 0.
    features = build_features(bars)
    assert pd.isna(features.session_vwap.iloc[2])
    typical = (bars.high.iloc[3]+bars.low.iloc[3]+bars.close.iloc[3])/3
    assert features.session_vwap.iloc[3] == pytest.approx(typical)
    previous = np.average(((bars.high+bars.low+bars.close)/3).iloc[:2], weights=bars.volume.iloc[:2])
    assert features.session_vwap.iloc[1] == pytest.approx(previous)


def test_context_is_available_only_after_its_bar_has_closed():
    own = candles(36)
    btc = candles(3, freq='1h', seed=3)
    features = build_features(own, dict(BTC=btc))
    assert features.context_BTC_close.iloc[:11].isna().all()
    assert features.context_BTC_close.iloc[11] == btc.close.iloc[0]
    assert features.context_BTC_close.iloc[22] == btc.close.iloc[0]
    assert features.context_BTC_close.iloc[23] == btc.close.iloc[1]
    poisoned = btc.copy()
    poisoned.loc[1:, ['open', 'high', 'low', 'close']] *= 100
    again = build_features(own, dict(BTC=poisoned))
    pd.testing.assert_series_equal(features.context_BTC_close.iloc[:23], again.context_BTC_close.iloc[:23])


def test_funding_uses_previously_settled_observation_not_current_rate():
    own = candles(100)
    own['funding_rate'] = np.nan
    own.loc[80, 'funding_rate'] = .001
    features = build_features(own)
    assert pd.isna(features.past_settled_funding.iloc[80])
    assert features.past_settled_funding.iloc[:91].isna().all()
    assert features.past_settled_funding.iloc[91] == .001
    assert features.past_settled_funding.iloc[99] == .001
    without = build_features(own.drop(columns='funding_rate'))
    spec = next(s for s in library() if s['family'] == 'funding_fade')
    assert build_signal(without, spec).signal.eq(0).all()


def test_ingestion_settled_funding_overrides_unlagged_cashflow_events():
    own = candles(100)
    own['funding_rate'] = .25
    own['settled_funding'] = np.nan
    own.loc[90:, 'settled_funding'] = .001
    features = build_features(own)
    assert features.past_settled_funding.iloc[:90].isna().all()
    assert features.past_settled_funding.iloc[90] == .001


def test_gaps_and_duplicate_or_unsorted_source_data_fail_explicitly():
    own = candles(100)
    with pytest.raises(ValueError, match='Gaps'):
        build_features(own.drop(index=30))
    with pytest.raises(ValueError, match='unique'):
        build_features(pd.concat([own, own.iloc[-1:]], ignore_index=True))
    with pytest.raises(ValueError, match='ordered'):
        build_features(own.iloc[::-1])


@pytest.mark.parametrize('freq,label', [('5min', '5m'), ('15min', '15m'), ('1h', '1h'), ('4h', '4h')])
def test_horizon_independence_and_no_nan_exposure(freq, label):
    bars = candles(400, freq=freq)
    bars.attrs['timeframe'] = label
    features = build_features(bars)
    for spec in library():
        if spec['timeframe'] == label:
            output = build_signal(features, {**spec, 'symbol': 'ETH'})
            assert output.signal.notna().all()
            assert output.signal.isin([-1, 0, 1]).all()


def test_warmup_suppresses_nonbaseline_exposure_and_channel_uses_prior_extremes():
    bars = candles(10)
    features = build_features(bars)
    for spec in library():
        if spec['timeframe'] == '5m' and not spec['baseline']:
            assert build_signal(features, spec).signal.eq(0).all()


def test_secondary_regimes_are_explicit_and_use_causal_volume_autocorrelation():
    bars = candles(400)
    features = build_features(bars)
    assert features.loc[features.rvol.ge(1.5), 'liquidity_regime'].eq('high_volume').all()
    assert features.loc[features.rvol.lt(.5), 'liquidity_regime'].eq('low_volume').all()
    assert features.loc[features.autocorr.ge(.1), 'serial_regime'].eq('positive_serial').all()
    assert features.loc[features.autocorr.le(-.1), 'serial_regime'].eq('negative_serial').all()
    assert features.regime_detail.str.count(r'\|').eq(2).all()
    assert features.regime.isin(['trend', 'range', 'high_volatility', 'warmup']).all()
    assert 'Secondary labels' in features.attrs['regime_classifier']

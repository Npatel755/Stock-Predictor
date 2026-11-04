import numpy as np
import pandas as pd
import pytest

from research.codex_eth_bnb.analytics import block_statistics, combine_sleeves, daily_returns, holm, metric_extras


def test_daily_calendar_belongs_to_open_and_first_day_includes_initial():
    data = pd.DataFrame(dict(bar_open=pd.to_datetime(['2026-01-31 23:00Z', '2026-02-01 00:00Z', '2026-02-01 23:00Z']),
                             timestamp=pd.to_datetime(['2026-02-01 00:00Z', '2026-02-01 01:00Z', '2026-02-02 00:00Z']),
                             equity=[110., 115., 121.]))
    daily = daily_returns(data, initial=100.)
    assert daily.index.strftime('%Y-%m-%d').tolist() == ['2026-01-31', '2026-02-01']
    np.testing.assert_allclose(daily, [.1, .1])


def test_no_synthetic_missing_calendar_prices():
    data = pd.Series([100., 110.], index=pd.to_datetime(['2026-01-01', '2026-01-03'], utc=True))
    result = daily_returns(data, initial=100.)
    assert len(result) == 2
    assert pd.Timestamp('2026-01-02', tz='UTC') not in result.index
    np.testing.assert_allclose(result, [0., .1])


def test_block_null_constant_positive_and_seed_determinism():
    zero = block_statistics(np.zeros(100))
    assert zero['pvalue_centered_1s'] == 1.
    assert zero['annual_mean_daily_lower'] == zero['annual_mean_daily_upper'] == 0.
    positive = block_statistics(np.full(100, .001))
    assert positive['pvalue_centered_1s'] == pytest.approx(1/5000)
    assert positive['annual_mean_daily_lower'] == pytest.approx(.36525)
    assert positive['annual_mean_daily_upper'] == pytest.approx(.36525)
    sample = np.random.default_rng(10).normal(.0001, .01, 355)
    first, second = block_statistics(sample, draws=299), block_statistics(sample, draws=299)
    assert first == second
    assert first['mean_daily_lower'] < first['mean_daily'] < first['mean_daily_upper']


def test_bootstrap_rejects_missing_values_and_flags_tiny_sample():
    with pytest.raises(ValueError, match='finite'):
        block_statistics([0., np.nan])
    assert block_statistics([.01, -.02], draws=10)['insufficient_evidence']
    empty = block_statistics([], draws=10)
    assert empty['pvalue_centered_1s'] == 1.
    assert empty['mean_daily'] is None


def test_holm_preserves_full_family_and_original_order():
    assert holm([.001, .0001, .004], family_size=124) == pytest.approx([.123, .0124, .488])
    assert holm([None, .01, .005, float('nan')], family_size=4) == pytest.approx([1., .03, .02, 1.])
    with pytest.raises(ValueError, match='smaller'):
        holm([.01, .02], family_size=1)
    with pytest.raises(ValueError, match='between'):
        holm([-1.])


def test_identical_correlated_sleeves_do_not_double_return():
    dates = pd.date_range('2026-01-01', periods=3, freq='D', tz='UTC')
    returns = np.array([.01, -.02, .03])
    sleeve = pd.Series(25000.*np.cumprod(1+returns), index=dates)
    combined = combine_sleeves([sleeve, sleeve])
    np.testing.assert_allclose(combined['daily_returns'], returns)
    np.testing.assert_allclose(combined['equity'].equity, 2*sleeve)
    assert combined['correlation'].iloc[0, 1] == pytest.approx(1.)
    assert combined['metrics']['max_drawdown'] == pytest.approx(.02)
    assert combined['metrics']['final_equity'] == pytest.approx(50000.*np.prod(1+returns))


def test_combined_intrabar_bound_sums_minima_without_claiming_synchrony():
    date = pd.to_datetime(['2026-01-01 00:00Z', '2026-01-01 12:00Z'])
    first = pd.DataFrame(dict(bar_open=date, equity=[26000., 25000.], cash=[25000., 25000.],
                              intrabar_worst_equity=[24000., 25000.], exposed=[True, False]))
    second = pd.DataFrame(dict(bar_open=date, equity=[25000., 26000.], cash=[25000., 26000.],
                               intrabar_worst_equity=[25000., 24000.], exposed=[False, True]))
    result = combine_sleeves([first, second])
    assert result['equity'].intrabar_worst_equity.iloc[0] == 48000.
    assert 'need not be simultaneous' in result['metrics']['adverse_bound_note']


def test_period_pnl_and_direction_attribution_reconcile():
    times = pd.to_datetime(['2026-01-31 23:00Z', '2026-02-01 23:00Z', '2026-02-02 23:00Z'])
    curve = pd.DataFrame(dict(bar_open=times, timestamp=times+pd.Timedelta(hours=1),
                             equity=[110., 105., 120.], regime=['bull', 'range', 'bear']))
    trades = pd.DataFrame(dict(direction=[1, -1], net_pnl=[25., -5.]))
    extras = metric_extras(dict(equity=curve, trades=trades, metrics=dict(initial_capital=100.)))
    assert [x['period'] for x in extras['monthly']] == ['2026-01', '2026-02']
    assert [x['net_pnl'] for x in extras['monthly']] == [10., 10.]
    assert sum(x['net_pnl'] for x in extras['regime_pnl_attribution']) == 20.
    assert extras['long_short']['long']['net_pnl'] == 25.
    assert extras['long_short']['short']['net_pnl'] == -5.
    by_regime = {r['regime']: r for r in extras['daily_regime_performance']}
    assert by_regime['unknown']['net_pnl'] == 10.
    assert by_regime['bull']['net_pnl'] == -5.
    assert by_regime['range']['net_pnl'] == 15.

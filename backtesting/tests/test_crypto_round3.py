import numpy as np
import pandas as pd
import pytest

from backtesting.crypto_research import data, round3


def synthetic_bars(days=400, seed=5):
    ts = pd.date_range('2022-01-01', periods=days*288, freq='5min', tz='UTC')
    rng = np.random.default_rng(seed)
    # Alternating quiet/active 20-day regimes so volatility-contraction setups exist.
    sigma = np.where((np.arange(len(ts))//(20*288)) % 2 == 0, .001, .004)
    close = 300*np.exp(np.cumsum(rng.normal(0, sigma)))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close)*(1+rng.uniform(0, .002, len(ts)))
    low = np.minimum(open_, close)*(1-rng.uniform(0, .002, len(ts)))
    return pd.DataFrame(dict(timestamp=ts, ticker=data.ticker('BNB'), open=open_, high=high, low=low, close=close,
                             volume=rng.uniform(1, 100, len(ts)), exchange_close_time=ts+pd.Timedelta(minutes=4, seconds=59)))


def test_grid_is_fixed_and_new():
    rows = round3.candidates()
    assert len(rows) == 32 and len({r['id'] for r in rows}) == 32
    assert not set(round3.FAMILIES) & {'trend_pullback', 'rsi_pullback', 'squeeze_breakout', 'supertrend', 'range_reversion', 'time_series_momentum'}
    with pytest.raises(ValueError):
        round3.FamilyRule('donchian20', '8h', 2., 3., 3.)
    with pytest.raises(ValueError):
        round3.FamilyRule('bollinger', '4h', 2., 3., 3.)


def test_every_family_signals_on_completed_candles_only():
    bars = synthetic_bars()
    feats = round3.Features(bars)
    for family in round3.FAMILIES:
        for tf, expected_hours in [('4h', {3, 7, 11, 15, 19, 23}), ('1D', {23})]:
            out = feats.signals(round3.FamilyRule(family, tf, 2., 3., 3.))
            fired = out.loc[out.signal != 0, 'timestamp']
            assert len(fired) > 0, (family, tf)
            assert set(fired.dt.hour) <= expected_hours and set(fired.dt.minute) == {55}, (family, tf)
            assert out.loc[out.signal != 0, 'signal_atr'].notna().all()
    daily = feats.base('1D')
    assert daily['ready'].sum() == len(daily['candles'])-59


def test_held_out_versions_are_sequential_and_never_overwrite(tmp_path):
    (tmp_path/'candidates/crypto_v0_2').mkdir(parents=True)
    outcome = dict(version='crypto_v0_2', symbol='BTC', candidate=dict(id='x', kind='carry_over', rule={}))
    cfg = type('C', (), dict(risk_usd=100., initial_capital=50000., commission_bps=4.))()
    with pytest.raises(ValueError):
        round3.register(tmp_path, outcome, cfg)
    assert round3.carry_over_candidate()['rule']['family'] == 'squeeze_breakout' and round3.FIRST_VERSION == 2

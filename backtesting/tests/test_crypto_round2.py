import numpy as np
import pandas as pd
import pytest

from backtesting.crypto_research import data, round2
from backtesting.strategy_lab_signals import LabRule, prepare


def test_grid_is_fixed_and_contains_v0_1():
    rows = round2.candidates()
    assert len(rows) == 240 and len({r['id'] for r in rows}) == 240
    base = next(r for r in rows if r['id'] == round2.BASELINE_ID)
    assert base['rule'] == dict(lookback=20, trend=200, volume_gate=True, timeframe_hours=4, stop_atr=3., reward_r=5., trail_atr=4.)
    with pytest.raises(ValueError):
        round2.MomentumRule(25, 200, True, 4, 3., 5., 4.)


def test_neighbours_are_one_step_moves():
    rows = round2.candidates()
    base = next(r for r in rows if r['id'] == round2.BASELINE_ID)
    near = {r['id'] for r in round2.neighbours(base, rows)}
    # lookback 15/30, trend 100/none, volume off, 8h, exits tight/wide = 8 neighbours
    assert len(near) == 8
    assert {'tsm_l15_t200_von_4h_patient', 'tsm_l30_t200_von_4h_patient', 'tsm_l20_t100_von_4h_patient',
            'tsm_l20_tnone_von_4h_patient', 'tsm_l20_t200_voff_4h_patient', 'tsm_l20_t200_von_8h_patient',
            'tsm_l20_t200_von_4h_tight', 'tsm_l20_t200_von_4h_wide'} == near
    corner = next(r for r in rows if r['id'] == 'tsm_l10_t100_von_4h_tight')
    assert len(round2.neighbours(corner, rows)) == 5


def test_plateau_gate_rejects_isolated_spike():
    rows = round2.candidates()
    base = next(r for r in rows if r['id'] == round2.BASELINE_ID)
    near = [r['id'] for r in round2.neighbours(base, rows)]
    scores = {r['id']: dict(score=-100., eligible=False) for r in rows}
    scores[base['id']] = dict(score=900., eligible=True)
    spike = round2.plateau_rank(base, rows, scores)
    assert not spike['eligible'] and spike['score'] == -100. and 'own_score' not in spike
    for k in near[:4]:
        scores[k] = dict(score=300., eligible=True)
    half = round2.plateau_rank(base, rows, scores)
    assert half['eligible'] and half['neighbours_eligible'] == 4 and half['score'] == pytest.approx(np.median([900.]+[300.]*4+[-100.]*4))
    scores[base['id']] = dict(score=900., eligible=False)
    assert not round2.plateau_rank(base, rows, scores)['eligible']


def synthetic_bars(days=120, seed=3):
    ts = pd.date_range('2023-01-01', periods=days*288, freq='5min', tz='UTC')
    rng = np.random.default_rng(seed)
    close = 300*np.exp(np.cumsum(rng.normal(0, .002, len(ts))))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close)*(1+rng.uniform(0, .002, len(ts)))
    low = np.minimum(open_, close)*(1-rng.uniform(0, .002, len(ts)))
    return pd.DataFrame(dict(timestamp=ts, ticker=data.ticker('BNB'), open=open_, high=high, low=low, close=close,
                             volume=rng.uniform(1, 100, len(ts)), exchange_close_time=ts+pd.Timedelta(minutes=4, seconds=59)))


def test_baseline_grid_point_reproduces_round1_signals():
    bars = synthetic_bars()
    rule = round2.MomentumRule(20, 200, True, 4, 3., 5., 4.)
    mine = round2.Features(bars).signals(rule)
    theirs = prepare(bars, LabRule('time_series_momentum', 4, 3., 5., 4.))
    assert mine.signal.abs().sum() > 0
    pd.testing.assert_series_equal(mine.signal, theirs.signal)
    pd.testing.assert_series_equal(mine.signal_atr, theirs.signal_atr)
    pd.testing.assert_series_equal(mine.management_atr, theirs.management_atr)


def test_trend_and_volume_switches_relax_the_rule():
    bars = synthetic_bars()
    feats = round2.Features(bars)
    strict = feats.signals(round2.MomentumRule(20, 200, True, 4, 3., 5., 4.)).signal.abs().sum()
    no_trend = feats.signals(round2.MomentumRule(20, 0, True, 4, 3., 5., 4.)).signal.abs().sum()
    no_volume = feats.signals(round2.MomentumRule(20, 200, False, 4, 3., 5., 4.)).signal.abs().sum()
    assert no_trend >= strict and no_volume >= strict and no_trend+no_volume > 2*strict
    eight = feats.signals(round2.MomentumRule(20, 200, True, 8, 3., 5., 4.))
    assert eight.signal.abs().sum() > 0 and set(eight.loc[eight.signal != 0, 'timestamp'].dt.hour) <= {7, 15, 23}

from dataclasses import asdict, replace
import json

import pandas as pd

from backtesting.alternative_strategies import SignalRule, simulate
from backtesting.numbered_research import exit_candidates, initial_screen
from backtesting.optimize import baseline
from backtesting.regime_filters import RegimeFilter, apply_filter, prepare_features
from test_dvs import candles
from test_trend_research import metrics


def test_exit_grid_preserves_entry_settings_and_has_one_parent_control():
    parent=SignalRule('channel_breakout',lookback=96,slow=150,stop_atr=1.5,reward_r=4.5,trail_atr=3.)
    filters=RegimeFilter(min_rvol=2.4,min_trend_gap_bps=200.)
    rows=exit_candidates(parent,filters)
    assert len(rows)==36 and rows[0]['rule']==asdict(parent)
    assert len({json.dumps(row['rule'],sort_keys=True) for row in rows})==36
    for row in rows:
        rule=SignalRule(**row['rule'])
        assert replace(rule,stop_atr=parent.stop_atr,reward_r=parent.reward_r,trail_atr=parent.trail_atr)==parent
        assert row['filters']==asdict(filters)


def test_exit_feature_cache_reproduces_fresh_signals_and_real_broker_outcomes():
    # Use active signals/trades; an empty filtered sample would hide cache errors.
    bars=candles(5000)
    parent=SignalRule('channel_breakout',lookback=20,slow=50,stop_atr=1.5,reward_r=4.5,trail_atr=3.)
    filters=RegimeFilter()
    cfg=replace(baseline(),risk_includes_costs=True)
    cached=apply_filter(prepare_features(bars,parent),filters)
    for rule in [parent,replace(parent,stop_atr=1.25,reward_r=4.,trail_atr=2.5),replace(parent,stop_atr=1.75,reward_r=5.,trail_atr=4.)]:
        fresh=apply_filter(prepare_features(bars,rule),filters)
        pd.testing.assert_frame_equal(cached,fresh)
        m,t,e=simulate(bars,rule,cfg,signals=cached)
        m2,t2,e2=simulate(bars,rule,cfg,signals=fresh)
        assert m==m2 and len(t)>0
        pd.testing.assert_frame_equal(t,t2)
        pd.testing.assert_frame_equal(e,e2)


def test_initial_screen_uses_exact_profit_and_parent_drawdown():
    parent={'main':metrics(10799.669772006622,345,.03565506280963821)}
    assert not initial_screen(metrics(10799.66,350),parent,10799.669772006622)
    assert not initial_screen(metrics(12000,350,.036),parent,10799.669772006622)
    assert initial_screen(metrics(12000,350,.035),parent,10799.669772006622)

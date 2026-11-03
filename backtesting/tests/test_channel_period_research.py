from dataclasses import asdict, replace
import json

import pandas as pd

from backtesting.alternative_strategies import SignalRule
from backtesting.channel_period_research import period_candidates
from backtesting.regime_filters import RegimeFilter, apply_filter, prepare_features
from test_dvs import candles


def test_period_grid_preserves_exit_geometry_filters_and_one_parent_control():
    parent=SignalRule('channel_breakout',lookback=96,slow=150,stop_atr=1.5,reward_r=4.5,trail_atr=3.)
    filters=RegimeFilter(min_rvol=2.4,min_trend_gap_bps=200.)
    rows=period_candidates(parent,filters)
    assert len(rows)==12 and rows[0]['rule']==asdict(parent)
    assert len({json.dumps(row['rule'],sort_keys=True) for row in rows})==12
    for row in rows:
        r=SignalRule(**row['rule'])
        assert replace(r,lookback=parent.lookback,slow=parent.slow)==parent
        assert row['filters']==asdict(filters)


def test_changed_periods_recompute_signals_gap_and_warmup_causally():
    bars=candles(5000)
    parent=SignalRule('channel_breakout',lookback=96,slow=150)
    changed=replace(parent,lookback=72,slow=250)
    a=prepare_features(bars,parent)
    b=prepare_features(bars,changed)
    assert not a.trend_gap_bps.equals(b.trend_gap_bps)
    assert not a.signal.equals(b.signal)
    assert b.iloc[:250*12-1].signal.eq(0).all()
    settings=RegimeFilter(min_trend_gap_bps=200.)
    first=apply_filter(b,settings)
    mutated=bars.copy()
    mutated.loc[4000:,['open','high','low','close','volume']]*=1.5
    second=apply_filter(prepare_features(mutated,changed),settings)
    pd.testing.assert_frame_equal(first.iloc[:4000],second.iloc[:4000])

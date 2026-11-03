from dataclasses import replace
import json
from pathlib import Path

import pandas as pd
import pytest

from backtesting.alternative_strategies import SignalRule
from backtesting.campaign_research import PreparedSignals, candidates, protected_profiles
from backtesting.numbered_research import exit_candidates
from backtesting.regime_filters import RegimeFilter, prepare_features, apply_filter
from test_dvs import candles


def test_exit_campaign_matches_frozen_geometry_grid_without_changing_risk_or_filters():
    rule=SignalRule('channel_breakout',lookback=72,slow=250,stop_atr=1.5,reward_r=4.5,trail_atr=3.)
    filters=RegimeFilter(min_rvol=2.4,min_trend_gap_bps=200.)
    campaign=json.loads((Path(__file__).resolve().parents[1]/'configs/research_campaigns/v1_8_exit_geometry.json').read_text())
    actual=candidates(rule,filters,campaign)
    expected=exit_candidates(rule,filters)
    assert len(actual)==36
    assert [(r['rule'],r['filters']) for r in actual]==[(r['rule'],r['filters']) for r in expected]
    with pytest.raises(ValueError,match='may not override'): candidates(rule,filters,{**campaign,'execution':{'risk_usd':200}})
    with pytest.raises(ValueError,match='only signal rules'): candidates(rule,filters,{'rule_dimensions':{'risk_usd':[200]}})


def test_prepared_signals_change_periods_and_filters_and_never_mutate_cached_raw_features():
    bars=candles(5000)
    cache=PreparedSignals(bars)
    parent=SignalRule('channel_breakout',lookback=20,slow=50)
    settings=RegimeFilter()
    first=cache.get(parent,settings)
    assert first.signal.ne(0).any()
    first['signal']=0
    for rule,filters in [(parent,settings),(replace(parent,stop_atr=1.25),settings),
                         (replace(parent,lookback=30,slow=70),RegimeFilter(min_trend_gap_bps=200.))]:
        pd.testing.assert_frame_equal(cache.get(rule,filters),apply_filter(prepare_features(bars,rule),filters))


def test_filter_campaign_keeps_every_exit_and_period_fixed():
    rule=SignalRule('channel_breakout',lookback=72,slow=250,stop_atr=1.5,reward_r=4.5,trail_atr=3.)
    settings=RegimeFilter(min_rvol=2.4,min_trend_gap_bps=200.)
    campaign=json.loads((Path(__file__).resolve().parents[1]/'configs/research_campaigns/v1_8_entry_filters.json').read_text())
    rows=candidates(rule,settings,campaign)
    assert len(rows)==24
    assert len({json.dumps(r['filters'],sort_keys=True) for r in rows})==24
    for row in rows:
        assert SignalRule(**row['rule'])==rule
        assert replace(RegimeFilter(**row['filters']),min_rvol=2.4,min_trend_gap_bps=200.)==settings


def test_frozen_profile_inventory_does_not_expand_after_saving_a_new_version(tmp_path):
    old=tmp_path/'configs/eth_strategy_v1_8.json'
    old.parent.mkdir()
    old.write_text('saved parent')
    manifest=tmp_path/'manifest.json'
    initial=protected_profiles(tmp_path,manifest)
    assert initial==[old]
    manifest.write_text(json.dumps({'protected_profile_hashes':{'configs/eth_strategy_v1_8.json':'original_hash'}}))
    (old.parent/'eth_strategy_v1_9.json').write_text('new improvement')
    assert protected_profiles(tmp_path,manifest)==initial

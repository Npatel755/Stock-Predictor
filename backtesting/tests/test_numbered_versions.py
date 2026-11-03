from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import pytest

from backtesting.alternative_strategies import SignalRule
from backtesting.entry_neighborhood import candidates, eligible
from backtesting.regime_filters import RegimeFilter
from backtesting.save_numbered import save
from backtesting.versioned_profiles import load_profile
from test_trend_research import metrics
from test_v15 import write_selection


def test_neighborhood_is_unique_preserves_parent_and_changes_only_two_filters():
    rule=SignalRule('channel_breakout',lookback=96,slow=150,stop_atr=1.5,reward_r=4.5,trail_atr=3.)
    parent=RegimeFilter(min_rvol=2.,min_trend_gap_bps=200.)
    rows=candidates(rule,parent)
    assert len(rows)==18 and rows[0]['filters']==asdict(parent)
    assert len({json.dumps(r['filters'],sort_keys=True) for r in rows})==18
    for row in rows:
        assert row['rule']==asdict(rule)
        assert {k:v for k,v in row['filters'].items() if k not in {'min_rvol','min_trend_gap_bps'}}=={
            k:v for k,v in asdict(parent).items() if k not in {'min_rvol','min_trend_gap_bps'}}


def test_neighborhood_rejects_weak_half_cost_failure_even_with_higher_total():
    parent=dict(main=metrics(10089.86981444979,367,.0376),stress4=metrics(8963.46),stress8=metrics(6888.4))
    checks={k:metrics(1000) for k in ['2025_h1','2025_h2','2026_h1','2026_h2','2026_h1_4bp','earlier_2020_2022']}
    checks.update(full_4bp=metrics(9000),full_8bp=metrics(7000))
    assert eligible(metrics(10500,350),checks,parent,10089.86981444979)
    checks['2026_h1_4bp']=metrics(-.01)
    assert not eligible(metrics(10500,350),checks,parent,10089.86981444979)


def test_next_numbered_save_preserves_prior_version_and_rejects_overwrite_and_skip(tmp_path):
    config=tmp_path/'configs'
    config.mkdir()
    old=config/'eth_strategy_v1_6.json'
    old.write_text('preserve this saved profile')
    target=dict(requested_net_profit_usd=10089.86981444979,prior_reference_net_profit_usd=10089.86981444979,prior_reference='ETH v1.6')
    (config/'research_baseline.json').write_text(json.dumps(target))
    experiment=tmp_path/'experiment'
    selection=write_selection(experiment,net=10500.)
    selection['candidate']['filters']['min_trend_gap_bps']=200.
    (experiment/'selection.json').write_text(json.dumps(selection))
    with pytest.raises(ValueError,match='consecutive'): save(experiment,'v1.8',tmp_path)
    save(experiment,'v1.7',tmp_path)
    _,_,meta,pine=load_profile(tmp_path,'v1.7')
    assert meta['same_period_net_usd']==10500. and meta['entry_filters']['min_trend_gap_bps']==200.
    assert 'ETH v1.7' in pine.read_text()
    assert pine.read_bytes()==(tmp_path/'downloads/ETH_Strategy_v1_7.txt').read_bytes()
    assert 'ETH_Strategy_v1_7.pine -text' in (tmp_path/'reference/.gitattributes').read_text()
    assert old.read_text()=='preserve this saved profile'
    assert json.loads((config/'research_baseline.json').read_text())['reference_version']=='v1.7'
    assert json.loads((config/'research_baseline.json').read_text())['requested_net_profit_usd']==10500.
    with pytest.raises(ValueError,match='immutable'): save(experiment,'v1.7',tmp_path)


def test_new_version_cannot_promote_a_lower_profit_or_failed_gate(tmp_path):
    config=tmp_path/'configs'
    config.mkdir()
    (config/'eth_strategy_v1_6.json').write_text('preserved')
    (config/'research_baseline.json').write_text(json.dumps(dict(requested_net_profit_usd=10089.86981444979,prior_reference_net_profit_usd=10089.86981444979)))
    experiment=tmp_path/'experiment'
    selection=write_selection(experiment,net=10089.)
    with pytest.raises(ValueError,match='exact current baseline'): save(experiment,'v1.7',tmp_path)
    selection['passed_predeclared_validation_gate']=False
    (experiment/'selection.json').write_text(json.dumps(selection))
    with pytest.raises(ValueError,match='gate must pass'): save(experiment,'v1.7',tmp_path)
    assert not (config/'eth_strategy_v1_7.json').exists()


def test_restored_v15_and_v16_are_separate_verified_real_profiles():
    root=Path(__file__).resolve().parents[1]
    _,_,old,_=load_profile(root,'v1.5')
    _,_,new,pine=load_profile(root,'v1.6')
    assert old['same_period_net_usd']==pytest.approx(9971.427110129662)
    assert new['same_period_net_usd']==pytest.approx(10089.86981444979)
    assert old['entry_filters']['min_trend_gap_bps']==0
    assert new['entry_filters']['min_trend_gap_bps']==200
    archived=root/'reference/revisions/13e35043f30af183'
    assert (root/'reference/ETH_Strategy_v1_5.pine').read_bytes()==(archived/'ETH_Strategy_v1_5.pine').read_bytes()
    assert hashlib.sha256(pine.read_bytes()).hexdigest()==new['pine_sha256']

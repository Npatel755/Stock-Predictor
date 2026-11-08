"""Risk scaling, strict improvement, and parameter/execution identity guards."""
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import e57_refinement_parameters as parameters
import e57_training_refinement as study
import mass_research as engine

PARENT=dict(instrument='MNQ',family='momentum',lookback=16,threshold=1.5,stop_atr=1.,target_r=4.,hold_bars=12,session_start=585,session_end=945,max_contracts=1,trailing_atr=2.)


def test_scaling_preserves_hard_stops_and_models_real_budgets():
    original=engine.execution_cfg(PARENT)
    assert parameters.scaled_cfg(original,PARENT)==original
    c=dict(PARENT,max_contracts=3,risk_scale=3.)
    cfg=parameters.scaled_cfg(engine.execution_cfg(c),c)
    assert (cfg['risk_per_trade'],cfg['max_open_risk'],cfg['daily_loss'])==(450,450,900)
    assert (cfg['hard_drawdown'],cfg['funded_drawdown'],cfg['funded_cap'])==(1800,2000,50100)
    assert cfg['impact_ticks']==.5 and cfg['maxqty']==3


def test_execution_scope_restores_original_even_on_failure():
    original=engine.execution_cfg
    with pytest.raises(RuntimeError):
        with parameters.execution_scope(engine):
            assert engine.execution_cfg(dict(PARENT,risk_scale=2.))['risk_per_trade']==300
            raise RuntimeError('synthetic failure')
    assert engine.execution_cfg is original


def test_market_or_metadata_rename_does_not_manufacture_unique_strategy():
    a=parameters.fingerprint(PARENT)
    assert a==parameters.fingerprint(dict(PARENT,instrument='MES',experiment_order=123,config_id='tag',risk_scale=1.))
    assert a!=parameters.fingerprint(dict(PARENT,risk_scale=2.))


def test_registered_controls_precede_any_search_and_manifest_deduplicates():
    excluded={parameters.fingerprint(PARENT)}
    rows=parameters.universe(PARENT,excluded,target=1000,seed=123)
    keys={parameters.fingerprint(c) for c in rows}
    assert len(keys)==1000 and keys.isdisjoint(excluded)
    assert all(c['pure_scaling_control'] for c in rows[:7])
    assert sum(c['pure_scaling_control'] for c in rows)==7


def test_improvement_cannot_trade_more_drawdown_for_profit():
    baseline=dict(net_pnl=4935.5,realized_drawdown=446.5,max_drawdown=480,intrabar_drawdown=533.25)
    good=dict(baseline,qualified=True,net_pnl=5000)
    assert study.dominates(good,baseline)
    assert not study.dominates(dict(good,intrabar_drawdown=534),baseline)
    assert not study.dominates(dict(good,realized_drawdown=447),baseline)
    assert not study.dominates(dict(good,net_pnl=4935.5),baseline)

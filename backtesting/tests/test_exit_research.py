from dataclasses import asdict, replace
import json

import pytest

from backtesting.config import StrategyConfig
from backtesting.exit_research import candidates, freeze, passes_gate, training_score, validation_score
from backtesting.export_candidate import export, render_candidate
from backtesting.optimize import baseline


def metrics(net, entries=30, drawdown=300):
    return dict(initial_capital=50000., final_equity=50000.+net, entries=entries,
                max_closed_equity_drawdown_usd=drawdown, margin_call_events=0)


def test_exit_candidates_preserve_risk_costs_and_signal_rules():
    parent = replace(baseline(), reward_r=4.5, stop_atr=.4, min_atr_bps=10., risk_includes_costs=True)
    universe = candidates(parent)
    assert len(universe) == 24
    assert len({json.dumps(c['config'], sort_keys=True) for c in universe}) == len(universe)
    assert universe[0]['config'] == asdict(parent)
    for row in universe:
        cfg = StrategyConfig(**row['config'])
        assert (cfg.risk_usd, cfg.initial_capital, cfg.max_leverage) == (100, 50000, 5)
        assert (cfg.commission_bps, cfg.slippage_bps, cfg.swap_daily_bps) == (4, 2, 3.3)
        assert cfg.entry_timing == 'next_open' and cfg.intrabar_policy == 'stop_first'
        assert cfg.breakout_rvol == parent.breakout_rvol and cfg.entry_rvol == parent.entry_rvol


def test_exit_gate_requires_old_regime_survival_and_validation_improvement():
    train = [metrics(1000)]*5
    valid = [metrics(200, entries=15)]*2
    parent_train = [metrics(500)]*5
    parent_valid = [metrics(100, entries=15)]*2
    assert passes_gate(train, valid, parent_train, parent_valid)
    assert not passes_gate([metrics(-1000)]*2+train[:3], valid, parent_train, parent_valid)
    assert not passes_gate(train, [metrics(-1, entries=15), metrics(1000, entries=15)], parent_train, parent_valid)
    assert not passes_gate(train, parent_valid, parent_train, parent_valid)
    assert training_score([metrics(10000, entries=1)]*5) == -1e9
    assert validation_score([metrics(10000, entries=5)]*2) == -1e9


def test_frozen_protocol_rejects_mutation(tmp_path):
    path = tmp_path/'manifest.json'
    freeze(path, {'candidates': [1, 2]})
    freeze(path, {'candidates': [1, 2]})
    with pytest.raises(ValueError, match='differs'):
        freeze(path, {'candidates': [1, 3]})


def test_v13_export_keeps_v12_files_intact(tmp_path, monkeypatch):
    import backtesting.export_candidate as module
    (tmp_path/'configs').mkdir()
    old_cfg = tmp_path/'configs/dvs_eth_v1_2.json'
    old_meta = tmp_path/'configs/dvs_eth_v1_2.metadata.json'
    old_cfg.write_text('original config')
    old_meta.write_text('original metadata')
    experiment = tmp_path/'experiment'
    experiment.mkdir()
    cfg = replace(baseline(), breakeven_r=1.5, trail_atr=2.)
    (experiment/'selection.json').write_text(json.dumps(dict(candidate=dict(label='trial', config=asdict(cfg)), passed_predeclared_validation_gate=False)))
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    output = tmp_path/'reference/DVS_ETH_v1_3.pine'
    export(experiment, output, version='v1.3')
    assert 'DVS ETH v1.3 | Research candidate' in output.read_text(encoding='utf-8')
    assert old_cfg.read_text() == 'original config' and old_meta.read_text() == 'original metadata'
    meta = json.loads((tmp_path/'configs/dvs_eth_v1_3.metadata.json').read_text())
    assert meta['strategy_name'] == 'DVS ETH v1.3' and not meta['ready_for_funded_trading']
    assert 'breakevenR = input.float(1.5' in output.read_text(encoding='utf-8')
    with pytest.raises(ValueError, match='Unsupported'):
        render_candidate(cfg, version='../v1.3')

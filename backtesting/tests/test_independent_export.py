from dataclasses import asdict, replace
import hashlib
import json

import pytest

from backtesting.alternative_strategies import SignalRule
from backtesting.export_independent import export, render
from backtesting.optimize import baseline


def test_independent_export_embeds_actual_rule_and_execution_limits():
    rule = SignalRule('channel_breakout', lookback=80, slow=200, stop_atr=2., reward_r=3., trail_atr=3.)
    cfg = replace(baseline(), risk_includes_costs=True)
    text, payload, digest = render(rule, cfg)
    assert text.startswith('//@version=6\n') and '{{' not in text
    assert 'ETH v1.3 | Channel Breakout research' in text
    assert 'length = input.int(80,' in text and 'rewardR = input.float(3.0,' in text
    assert 'trailATR = input.float(3.0,' in text
    assert 'commission_value=0.04' in text and 'slippage=2' in text
    assert 'hourClosed = time_close == time_close("60")' in text
    assert 'validChart and hourClosed and hourLong' in text
    assert 'barstate.isconfirmed and strategy.position_size == 0' in text
    assert 'previousHourATR' in text and 'lookahead=barmerge.lookahead_on' in text
    assert 'financing' in text and 'unverified' in text
    assert payload['rule'] == asdict(rule)
    assert hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest() == digest
    with pytest.raises(ValueError, match='cost-aware'):
        render(rule, baseline())


def test_independent_export_preserves_v12_and_archives_changed_v13(tmp_path, monkeypatch):
    import backtesting.export_independent as module
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    configs = tmp_path/'configs'
    configs.mkdir()
    old = configs/'dvs_eth_v1_2.json'
    old.write_text('saved v1.2')
    experiment = tmp_path/'experiment'
    experiment.mkdir()
    cfg = replace(baseline(), risk_includes_costs=True)
    rule = SignalRule('channel_breakout', lookback=80, slow=200, reward_r=3., trail_atr=3.)
    selection = dict(candidate=dict(label='frozen_rule', rule=asdict(rule)), execution_config=asdict(cfg), passed_predeclared_validation_gate=True)
    path = experiment/'selection.json'
    path.write_text(json.dumps(selection))
    export(experiment)
    pine = tmp_path/'reference/ETH_Strategy_v1_3.pine'
    original = pine.read_bytes()
    assert original == (tmp_path/'downloads/ETH_Strategy_v1_3.txt').read_bytes()
    meta = json.loads((configs/'eth_strategy_v1_3.metadata.json').read_text())
    assert meta['passed_predeclared_validation_gate'] is True
    assert meta['ready_for_funded_trading'] is False and meta['pine_compilation_verified'] is False
    assert meta['pine_sha256'] == hashlib.sha256(original).hexdigest()
    export(experiment)
    assert not (tmp_path/'reference/revisions').exists()
    selection['candidate']['rule']['lookback'] = 55
    path.write_text(json.dumps(selection))
    export(experiment)
    archives = list((tmp_path/'reference/revisions').iterdir())
    assert len(archives) == 1
    assert (archives[0]/pine.name).read_bytes() == original
    assert old.read_text() == 'saved v1.2'

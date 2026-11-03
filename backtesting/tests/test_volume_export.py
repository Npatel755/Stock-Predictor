from dataclasses import asdict, replace
import hashlib
import json

import pytest

from backtesting.alternative_strategies import SignalRule
from backtesting.export_volume_candidate import export, render_volume
from backtesting.optimize import baseline
from backtesting.regime_filters import RegimeFilter


def test_volume_export_implements_prior_hour_volume_and_utc_weekend_filters():
    rule = SignalRule('channel_breakout', lookback=96, slow=150, stop_atr=1.5, reward_r=4.5, trail_atr=3.)
    cfg = replace(baseline(), risk_includes_costs=True)
    settings = RegimeFilter(min_rvol=2., weekends=False)
    text, payload, digest = render_volume(rule, cfg, settings)
    assert 'strategy("ETH Volume Research | Experimental candidate"' in text
    assert 'ETH v1.4 |' not in text
    assert 'minHourlyRVOL = input.float(2.0,' in text
    assert 'allowWeekends = input.bool(false,' in text
    assert 'priorMeanVolume = ta.sma(volume[1], 20)' in text
    assert 'ready and longSignal and volumeOK' in text and 'ready and shortSignal and volumeOK' in text
    assert 'utcDay = dayofweek(time, "UTC")' in text
    assert 'hourLong and weekdayOK' in text and 'hourShort and weekdayOK' in text
    assert 'hourClosed = time_close == time_close("60")' in text
    assert 'process_orders_on_close=false' in text and 'financing' in text
    assert 'including 2026; no independent forward validation' in text
    assert hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest() == digest
    assert payload['filters'] == asdict(settings)
    with pytest.raises(ValueError, match='supports only'):
        render_volume(rule, cfg, replace(settings, min_trend_gap_bps=50))


def test_preview_requires_gate_and_never_changes_saved_v14(tmp_path, monkeypatch):
    import backtesting.export_volume_candidate as module
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    experiment = tmp_path/'experiment'
    experiment.mkdir()
    protected = tmp_path/'configs/eth_strategy_v1_4.json'
    protected.parent.mkdir()
    protected.write_text('protected profile')
    candidate = dict(label='volume_trial', rule=asdict(SignalRule('channel_breakout')), filters=asdict(RegimeFilter(min_rvol=2.5)))
    selection = dict(candidate=candidate, execution_config=asdict(replace(baseline(), risk_includes_costs=True)), passed_predeclared_validation_gate=False)
    selected = experiment/'selection.json'
    selected.write_text(json.dumps(selection))
    with pytest.raises(ValueError, match='failed'):
        export(experiment)
    assert not (tmp_path/'reference').exists()
    selection['passed_predeclared_validation_gate'] = True
    selected.write_text(json.dumps(selection))
    export(experiment)
    pine = tmp_path/'reference/experimental/ETH_Volume_Research.pine'
    meta = json.loads(pine.with_suffix('.metadata.json').read_text())
    assert meta['pine_sha256'] == hashlib.sha256(pine.read_bytes()).hexdigest()
    assert meta['filters_exported']['min_rvol'] == 2.5
    assert not meta['ready_for_funded_trading'] and not meta['pine_compilation_verified']
    assert pine.read_bytes() == (tmp_path/'downloads/ETH_Volume_Research.txt').read_bytes()
    assert protected.read_text() == 'protected profile'

from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path

import pytest

from backtesting.alternative_strategies import SignalRule
from backtesting.independent_profile import load_profile
from backtesting.optimize import baseline
from backtesting.search_results import overview_rows, search_status, training_overview


def metrics(net=10):
    return dict(initial_capital=50000., final_equity=50000.+net, entries=2, max_intrabar_drawdown=.01)


def test_modern_search_status_reads_independent_and_folded_training(tmp_path):
    (tmp_path/'manifest.json').write_text(json.dumps(dict(candidates=[{}, {}])))
    assert search_status(tmp_path)['manifest']['candidate_count'] == 2
    assert overview_rows(dict(evaluation={'audit': metrics()}))[0]['net_pnl'] == 10
    assert overview_rows(dict(evaluation={'parent': {'audit': metrics(-10)}}))[0]['scenario'] == 'parent / audit'
    assert overview_rows(dict(full_history={'baseline': metrics()}))[0]['trades'] == 2
    assert training_overview(dict(label='trial', folds=[metrics(10), metrics(-2)], score=1))['training_pnl'] == 8
    assert training_overview(dict(label='legacy', metrics=metrics(20), score=1))['entries'] == 2


def exported_profile(tmp_path, monkeypatch):
    import backtesting.export_independent as exporter
    monkeypatch.setattr(exporter, 'ROOT', tmp_path)
    directory = tmp_path/'artifacts/optimization/independent_trial'
    directory.mkdir(parents=True)
    rule = SignalRule('channel_breakout', lookback=80, slow=200, reward_r=3., trail_atr=3.)
    cfg = replace(baseline(), risk_includes_costs=True)
    selection = dict(candidate=dict(label='channel_trial', rule=asdict(rule)), execution_config=asdict(cfg),
                     passed_predeclared_validation_gate=True, validation={})
    (directory/'selection.json').write_text(json.dumps(selection))
    exporter.export(directory)
    return directory, rule, cfg, selection


def test_profile_loader_rejects_modified_pine_or_rules(tmp_path, monkeypatch):
    _, rule, cfg, _ = exported_profile(tmp_path, monkeypatch)
    assert load_profile(tmp_path)[:2] == (rule, cfg)
    pine = tmp_path/'reference/ETH_Strategy_v1_3.pine'
    original = pine.read_bytes()
    pine.write_bytes(original+b'\n// altered')
    with pytest.raises(ValueError, match='does not match'):
        load_profile(tmp_path)
    pine.write_bytes(original)
    config = tmp_path/'configs/eth_strategy_v1_3.json'
    raw = json.loads(config.read_text())
    raw['rule']['lookback'] = 55
    config.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match='does not match'):
        load_profile(tmp_path)


def test_dashboard_shows_modern_experiment_and_runs_independent_profile(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    import backtesting.paths as paths
    from backtesting.market_data import clean_candles
    from test_date_ranges import history
    directory, rule, cfg, selection = exported_profile(tmp_path, monkeypatch)
    (directory/'manifest.json').write_text(json.dumps(dict(candidates=[{'rule': asdict(rule)}], training=[['2020-01-01', '2025-01-01']])))
    (directory/'summary.json').write_text(json.dumps(dict(selection=selection, evaluation={'audit_2026': metrics(-100)})))
    bars, quality = clean_candles(history())
    data = tmp_path/'candles.parquet'
    bars.to_parquet(data, index=False)
    quality['parquet_sha256'] = hashlib.sha256(data.read_bytes()).hexdigest()
    data.with_suffix('.quality.json').write_text(json.dumps(quality))
    monkeypatch.setattr(paths, 'ROOT', tmp_path)
    monkeypatch.setattr(paths, 'PARQUET', data)
    monkeypatch.setattr(paths, 'RUNS', tmp_path/'artifacts/dvs')
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'dashboard.py'), default_timeout=30).run()
    assert not app.exception and not app.error
    assert any(tab.label == 'ETH v1.3' for tab in app.tabs)
    assert not any('Could not read this experiment' in msg.value for msg in app.warning)
    assert not any(b.label == 'Backtest experimental candidate on selected dates' for b in app.button)
    next(b for b in app.button if b.label == 'Run independent v1.3 on selected dates').click().run()
    assert not app.exception and not app.error
    result = app.session_state['independent_v13_result']
    assert result['metrics']['initial_capital'] == cfg.initial_capital
    assert 'equity' in result and len(app.get('plotly_chart')) >= 2
    assert result['equity'].equity.iloc[-1] == result['metrics']['final_equity']
    assert (tmp_path/'artifacts/independent/v1_3_dashboard/equity.parquet').exists()
    # A browser session holding the earlier table-only result upgrades from
    # its original event ledger when the dashboard reruns.
    older = {k: v for k, v in result.items() if k not in {'equity', 'rule', 'execution'}}
    app.session_state['independent_v13_result'] = older
    app.run()
    assert not app.exception and not app.error
    assert 'equity' in app.session_state['independent_v13_result']
    saved = json.loads((tmp_path/'artifacts/independent/v1_3_dashboard/results.json').read_text())
    assert saved['rule'] == asdict(rule) and saved['execution'] == asdict(cfg)
    assert app.sidebar.selectbox[0].value == 'v1.1'
    picker = lambda: next(s for s in app.sidebar.selectbox if s.label == 'Pine strategy version')
    assert 'v1.3' in picker().options
    picker().set_value('v1.3').run()
    assert not app.exception and not app.error
    assert app.sidebar.radio[0].value.startswith('B') and app.sidebar.radio[0].disabled
    assert next(w for w in app.sidebar.number_input if w.label == 'Reward / risk').value == 3.
    assert all(w.disabled for w in app.sidebar.number_input)
    assert any(tab.label == 'v1.3 backtest' for tab in app.tabs)
    assert not any(b.label == 'Run DVS backtest' for b in app.button)
    next(b for b in app.button if b.label == 'Run v1.3 backtest').click().run()
    assert not app.exception and not app.error
    assert any('Completed run' in h.value and 'v1.3' in h.value for h in app.subheader)
    saved = json.loads((tmp_path/'artifacts/independent/v1_3_dashboard/results.json').read_text())
    assert saved['rule'] == asdict(rule) and saved['execution'] == asdict(cfg)
    assert 'dvs_result' not in app.session_state
    # A refined profile cannot silently relabel a previous browser replay.
    import backtesting.export_independent as exporter
    selection['candidate']['rule']['lookback'] = 64
    selection['selection_is_historical_profit_optimization'] = True
    (directory/'selection.json').write_text(json.dumps(selection))
    exporter.export(directory)
    app.run()
    assert not app.exception and not app.error
    assert any('refined since this replay' in w.value for w in app.warning)
    assert app.session_state['independent_v13_result']['rule']['lookback'] == 80
    next(b for b in app.sidebar.button if b.label == 'Run v1.3 backtest').click().run()
    assert not app.exception and not app.error
    assert not any('refined since this replay' in w.value for w in app.warning)
    assert app.session_state['independent_v13_result']['rule']['lookback'] == 64
    picker().set_value('v1.1').run()
    assert not app.exception and not app.error
    assert any(b.label == 'Run DVS backtest' for b in app.button)
    assert not app.sidebar.radio[0].disabled
    # v1.4 has a distinct selector route, ledger directory and session result.
    selection['candidate']['rule'].update(lookback=96, slow=150, stop_atr=1.5, reward_r=4.5)
    (directory/'selection.json').write_text(json.dumps(selection))
    exporter.export(directory, version='v1.4')
    app.run()
    assert 'v1.4' in picker().options
    picker().set_value('v1.4').run()
    assert not app.exception and not app.error
    assert next(w for w in app.sidebar.number_input if w.label == 'Reward / risk').value == 4.5
    next(b for b in app.sidebar.button if b.label == 'Run v1.4 backtest').click().run()
    assert not app.exception and not app.error
    assert app.session_state['independent_v14_result']['rule']['lookback'] == 96
    assert app.session_state['independent_v13_result']['rule']['lookback'] == 64
    assert (tmp_path/'artifacts/independent/v1_4_dashboard/results.json').exists()
    assert any('Completed run' in h.value and 'v1.4' in h.value for h in app.subheader)
    picker().set_value('v1.3').run()
    assert not app.exception and not app.error
    assert app.session_state['independent_v13_result']['rule']['lookback'] == 64


def test_research_display_handles_older_cached_checkpoint_module(tmp_path, monkeypatch):
    import backtesting.search_results as cached
    from backtesting.research_display import search_status, overview_rows, training_overview
    for name in ['overview_rows', 'training_overview', 'search_status']:
        monkeypatch.delattr(cached, name)
    (tmp_path/'manifest.json').write_text(json.dumps(dict(candidates=[{}, {}])))
    assert search_status(tmp_path)['manifest']['candidate_count'] == 2
    assert overview_rows(dict(evaluation={'audit': metrics(50)}))[0]['net_pnl'] == 50
    assert training_overview(dict(label='trial', folds=[metrics()], score=1))['entries'] == 2

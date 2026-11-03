from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path

import pandas as pd

from backtesting.alternative_strategies import SignalRule, simulate
from backtesting.filtered_replay import replay
from backtesting.optimize import baseline
from backtesting.regime_filters import RegimeFilter, apply_filter, prepare_features
from test_dvs import candles


def test_filtered_dashboard_replay_matches_filtered_broker_and_saves_exact_equity(tmp_path):
    bars = candles(7000)
    bars['available_at'] = bars.timestamp+pd.Timedelta(minutes=5)
    rule = SignalRule('channel_breakout', lookback=20, slow=50)
    filters = RegimeFilter(min_rvol=1.2, weekends=False)
    cfg = replace(baseline(), risk_includes_costs=True)
    candidate = dict(label='test_filtered', rule=asdict(rule), filters=asdict(filters))
    expected, trades, events = simulate(bars, rule, cfg, signals=apply_filter(prepare_features(bars, rule), filters))
    result = replay(bars, candidate, asdict(cfg), tmp_path)
    assert len(trades) > 0 and result['metrics'] == expected
    pd.testing.assert_frame_equal(result['trades'], trades)
    pd.testing.assert_frame_equal(result['events'], events)
    assert abs(result['equity'].equity.iloc[-1]-expected['final_equity']) < 1e-7
    saved = json.loads((tmp_path/'results.json').read_text())
    assert saved['candidate']['filters'] == asdict(filters)
    assert saved['independent_validation'] is False
    pd.testing.assert_frame_equal(pd.read_parquet(tmp_path/'equity.parquet'), result['equity'])


def test_dashboard_filtered_research_keeps_numbered_profiles_separate(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    import backtesting.paths as paths
    from backtesting.market_data import clean_candles
    from test_independent_dashboard import exported_profile
    directory, rule, cfg, selection = exported_profile(tmp_path, monkeypatch)
    selection['candidate']['filters'] = asdict(RegimeFilter(min_rvol=1.5))
    selection['selection_is_historical_profit_optimization'] = True
    (directory/'manifest.json').write_text(json.dumps(dict(candidates=[selection['candidate']], historical_profit_selection=True, selection_window=['2023-01-01', '2026-10-28'])))
    (directory/'summary.json').write_text(json.dumps(dict(selection=selection, evaluation={})))
    profile = tmp_path/'configs/eth_strategy_v1_3.json'
    before = profile.read_bytes()
    bars, quality = clean_candles(candles(3000))
    data = tmp_path/'candles.parquet'
    bars.to_parquet(data, index=False)
    quality['parquet_sha256'] = hashlib.sha256(data.read_bytes()).hexdigest()
    data.with_suffix('.quality.json').write_text(json.dumps(quality))
    monkeypatch.setattr(paths, 'ROOT', tmp_path)
    monkeypatch.setattr(paths, 'PARQUET', data)
    monkeypatch.setattr(paths, 'RUNS', tmp_path/'artifacts/dvs')
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'dashboard.py'), default_timeout=30).run()
    assert not app.exception and not app.error
    next(b for b in app.button if b.label == 'Backtest filtered research candidate on selected dates').click().run()
    assert not app.exception and not app.error
    result = app.session_state[f'filtered_research_{directory.name}']
    assert result['candidate']['filters']['min_rvol'] == 1.5
    assert len(app.get('plotly_chart')) >= 2
    assert 'independent_v13_result' not in app.session_state
    assert profile.read_bytes() == before
    assert any('including 2026' in line.value for line in app.markdown)

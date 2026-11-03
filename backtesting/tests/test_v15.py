from dataclasses import asdict, replace
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import zipfile

import pandas as pd
import pytest

from backtesting.alternative_strategies import SignalRule, simulate
from backtesting.optimize import baseline
from backtesting.regime_filters import RegimeFilter
from backtesting.save_v15 import save
from backtesting.spot_proxy_data import parse_archive, validate_proxy, TICKER
from backtesting.versioned_profiles import load_profile
from test_dvs import candles


def test_proxy_preserves_ticker_and_reports_actual_gaps():
    raw = candles(5)
    raw['ticker'] = TICKER
    frame, quality = validate_proxy(raw.drop(index=2))
    assert frame.ticker.eq(TICKER).all() and quality['missing_bars'] == 1
    with pytest.raises(ValueError, match='Only'):
        validate_proxy(candles(5))
    with pytest.raises(ValueError, match='Only'):
        simulate(raw, SignalRule('ema_cross'), baseline())


def test_audit_manifests_are_not_misrepresented_as_candidate_searches(tmp_path):
    from backtesting.research_inventory import search_manifests
    for name, plan in [('native_audit', {'scenarios': {}}), ('empty', {'candidate_count': 0}),
                       ('old_search', {'candidate_count': 2}), ('new_search', {'candidates': [{}]})]:
        folder=tmp_path/'artifacts/optimization'/name
        folder.mkdir(parents=True)
        (folder/'manifest.json').write_text(json.dumps(plan))
    assert {p.parent.name for p in search_manifests(tmp_path)}=={'old_search','new_search'}


def test_proxy_parser_excludes_off_grid_source_candles_without_time_shifting():
    base = int(pd.Timestamp('2018-02-01', tz='UTC').timestamp()*1000)
    times = [base, base+300000, base+600000+14800, base+900000]
    rows = [[t,100,101,99,100,100,t+299999,10000,10,50,5000,0] for t in times]
    content = '\n'.join(','.join(map(str, row)) for row in rows)
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        archive.writestr('ETHUSDT-5m-2018-02.csv', content)
    frame = parse_archive(output.getvalue())
    assert frame.attrs['excluded_off_grid_rows'] == 1
    assert frame.timestamp.tolist() == list(pd.to_datetime([times[0],times[1],times[3]],unit='ms',utc=True))
    assert validate_proxy(frame)[1]['missing_bars'] == 1


def test_explicit_proxy_validator_changes_no_default_native_execution(monkeypatch):
    # Reproduce the preserved pre-extension simulator, not a second call to the
    # same implementation. Optional input validation must leave broker logic exact.
    source = Path(__file__).resolve().parents[1]/'reference/source_revisions/c994eb5e6b112cca256e7a7ab46c790e1ecf63f7728399acb220284b74894006/alternative_strategies.py'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source.parent.name
    spec = importlib.util.spec_from_file_location('backtesting._frozen_proxy_control', source)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    bars = candles(5000)
    rule = SignalRule('channel_breakout', lookback=20, slow=50)
    cfg = replace(baseline(), risk_includes_costs=True)
    old, old_trades, old_events = module.simulate(bars, rule, cfg)
    new, trades, events = simulate(bars, rule, cfg)
    assert old == new and len(trades) > 0
    pd.testing.assert_frame_equal(old_trades, trades)
    pd.testing.assert_frame_equal(old_events, events)
    proxy = bars.copy()
    proxy['ticker'] = TICKER
    proxy_metrics, proxy_trades, proxy_events = simulate(proxy, rule, cfg, validator=validate_proxy)
    assert proxy_metrics == new
    pd.testing.assert_frame_equal(proxy_trades, trades)
    pd.testing.assert_frame_equal(proxy_events, events)
    assert proxy.ticker.eq(TICKER).all()


def write_selection(directory, net=9971.43):
    directory.mkdir(parents=True)
    rule = SignalRule('channel_breakout',lookback=96,slow=150,stop_atr=1.5,reward_r=4.5,trail_atr=3.)
    cfg = replace(baseline(), risk_includes_costs=True)
    filters = RegimeFilter(min_rvol=2.)
    chosen = dict(candidate=dict(label='volume_winner',rule=asdict(rule),filters=asdict(filters)),execution_config=asdict(cfg),passed_predeclared_validation_gate=True)
    (directory/'selection.json').write_text(json.dumps(chosen))
    (directory/'summary.json').write_text(json.dumps(dict(evaluation=dict(full_period=dict(initial_capital=50000.,final_equity=50000.+net)))))
    return chosen


def test_v15_saves_actual_filters_baseline_and_separate_version(tmp_path,monkeypatch):
    import backtesting.save_v15 as module
    monkeypatch.setattr(module,'ROOT',tmp_path)
    directory=tmp_path/'experiment'
    chosen=write_selection(directory)
    old=tmp_path/'configs/eth_strategy_v1_4.json'
    old.parent.mkdir()
    old.write_text('protected v1.4')
    save(directory)
    rule,cfg,meta,pine=load_profile(tmp_path,version='v1.5')
    assert rule.lookback==96 and cfg.risk_usd==100
    assert meta['baseline_net_usd']==6000 and meta['baseline_period']==['2023-01-01','2026-10-28']
    assert meta['entry_filters']['min_rvol']==2.
    assert meta['same_period_net_usd']==pytest.approx(9971.43)
    assert 'strategy("ETH v1.5 | Volume filtered channel research"' in pine.read_text()
    assert 'minHourlyRVOL = input.float(2.0' in pine.read_text()
    assert pine.read_bytes()==(tmp_path/'downloads/ETH_Strategy_v1_5.txt').read_bytes()
    assert old.read_text()=='protected v1.4'
    meta_path=tmp_path/'configs/eth_strategy_v1_5.metadata.json'
    meta['entry_filters']['min_rvol']=0.
    meta_path.write_text(json.dumps(meta))
    with pytest.raises(ValueError,match='filters'):
        load_profile(tmp_path,version='v1.5')


def test_v15_save_rejects_results_below_baseline_and_risk_inflation(tmp_path,monkeypatch):
    import backtesting.save_v15 as module
    monkeypatch.setattr(module,'ROOT',tmp_path)
    directory=tmp_path/'experiment'
    chosen=write_selection(directory,net=5999)
    with pytest.raises(ValueError,match='exceed'):
        save(directory)
    (directory/'summary.json').write_text(json.dumps(dict(evaluation=dict(full_period=dict(initial_capital=50000.,final_equity=60000.)))))
    chosen['execution_config']['risk_usd']=200
    (directory/'selection.json').write_text(json.dumps(chosen))
    with pytest.raises(ValueError,match='unchanged'):
        save(directory)


def test_v15_refinement_must_beat_exact_current_reference_and_export_its_trend_filter(tmp_path,monkeypatch):
    import backtesting.save_v15 as module
    monkeypatch.setattr(module,'ROOT',tmp_path)
    folder=tmp_path/'configs'
    folder.mkdir()
    baseline_path=folder/'research_baseline.json'
    baseline=dict(requested_net_profit_usd=9900.,prior_reference_net_profit_usd=9971.427110129662)
    baseline_path.write_text(json.dumps(baseline))
    experiment=tmp_path/'experiment'
    selection=write_selection(experiment,net=9950.)
    with pytest.raises(ValueError,match='exact saved reference'):
        save(experiment)
    selection['candidate']['filters']['min_trend_gap_bps']=200.
    selection['requested_baseline']=9900.
    selection['exact_reference_net']=9971.427110129662
    (experiment/'selection.json').write_text(json.dumps(selection))
    (experiment/'summary.json').write_text(json.dumps(dict(evaluation=dict(full_period=dict(initial_capital=50000.,final_equity=60089.87)))))
    save(experiment)
    _,_,meta,pine=load_profile(tmp_path,version='v1.5')
    assert meta['entry_filters']['min_trend_gap_bps']==200.
    assert meta['baseline_net_usd']==9900.
    assert 'Volume + trend research' in pine.read_text()
    assert 'minHourlyTrendBps = input.float(200.0' in pine.read_text()
    # Re-exporting the exact same selection after raising the reference is
    # idempotent and does not rewrite its historical comparison benchmark.
    baseline['prior_reference_net_profit_usd']=10089.87
    baseline_path.write_text(json.dumps(baseline))
    baseline['requested_net_profit_usd']=10799.67
    baseline_path.write_text(json.dumps(baseline))
    preserved={p:p.read_bytes() for p in [tmp_path/'configs/eth_strategy_v1_5.json',tmp_path/'configs/eth_strategy_v1_5.metadata.json',pine,tmp_path/'downloads/ETH_Strategy_v1_5.txt']}
    save(experiment)
    _,_,again,_=load_profile(tmp_path,version='v1.5')
    assert again['exact_reference_at_selection']==9971.427110129662
    assert all(p.read_bytes()==content for p,content in preserved.items())
    selection['candidate']['filters']['min_rvol']=2.4
    (experiment/'selection.json').write_text(json.dumps(selection))
    with pytest.raises(ValueError,match='immutable'):
        save(experiment)
    assert all(p.read_bytes()==content for p,content in preserved.items())


def test_dashboard_v15_selector_applies_filters_and_retains_v14(tmp_path,monkeypatch):
    import backtesting.paths as paths
    import backtesting.save_v15 as exporter
    from streamlit.testing.v1 import AppTest
    from backtesting.market_data import clean_candles
    monkeypatch.setattr(exporter,'ROOT',tmp_path)
    directory=tmp_path/'experiment'
    chosen=write_selection(directory)
    chosen['candidate']['filters']['min_trend_gap_bps']=200.
    (directory/'selection.json').write_text(json.dumps(chosen))
    save(directory)
    bars,quality=clean_candles(candles(5000))
    data=tmp_path/'candles.parquet'
    bars.to_parquet(data,index=False)
    quality['parquet_sha256']=hashlib.sha256(data.read_bytes()).hexdigest()
    data.with_suffix('.quality.json').write_text(json.dumps(quality))
    monkeypatch.setattr(paths,'ROOT',tmp_path)
    monkeypatch.setattr(paths,'PARQUET',data)
    monkeypatch.setattr(paths,'RUNS',tmp_path/'artifacts/dvs')
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'dashboard.py'),default_timeout=30).run()
    assert not app.exception and not app.error
    picker=next(s for s in app.sidebar.selectbox if s.label=='Pine strategy version')
    assert 'v1.5' in picker.options
    picker.set_value('v1.5').run()
    next(b for b in app.sidebar.button if b.label=='Run v1.5 backtest').click().run()
    assert not app.exception and not app.error
    result=app.session_state['independent_v15_result']
    assert result['filters']['min_rvol']==2.
    assert result['filters']['min_trend_gap_bps']==200.
    saved=json.loads((tmp_path/'artifacts/independent/v1_5_dashboard/results.json').read_text())
    assert saved['filters']['min_rvol']==2.
    assert saved['filters']['min_trend_gap_bps']==200.
    assert 'independent_v14_result' not in app.session_state
    assert any('baseline applies' in line.value for line in app.caption)

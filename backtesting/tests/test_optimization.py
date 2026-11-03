from dataclasses import asdict
import json
import pandas as pd
import pytest

from backtesting.config import StrategyConfig
from backtesting.optimize import baseline, candidate_configs, training_score, validation_score
from backtesting.analyze_experiment import paired_week_bootstrap
from backtesting.search_results import checkpoint_rows
from backtesting.export_candidate import render_candidate


def metrics(net, trades=30, drawdown=500):
    return dict(initial_capital=50000, final_equity=50000 + net, entries=trades,
                max_closed_equity_drawdown_usd=drawdown, margin_call_events=0)


def test_candidate_universe_is_reproducible_unique_and_keeps_risk_and_costs_fixed():
    first, second = candidate_configs(256, 1027), candidate_configs(256, 1027)
    assert first == second
    assert len({json.dumps(c["config"], sort_keys=True) for c in first}) == 256
    assert first[0]["config"] == asdict(baseline())
    for candidate in first:
        cfg = StrategyConfig(**candidate["config"])
        assert cfg.mode == "research" and cfg.strategy_version == "v1.1"
        assert cfg.initial_capital == 50000 and cfg.risk_usd == 100 and cfg.max_leverage == 5
        assert cfg.commission_bps == 4 and cfg.slippage_bps == 2 and cfg.swap_daily_bps == 3.3
        assert cfg.entry_timing == "next_open" and cfg.intrabar_policy == "stop_first"


def test_small_samples_and_margin_events_cannot_win_by_luck():
    assert training_score(metrics(10000, trades=5)) == -1e9
    assert validation_score([metrics(10000, trades=4), metrics(10000, trades=30)]) == -1e9
    assert validation_score([metrics(100, trades=10), metrics(100, trades=10)]) == -1e9
    candidate = metrics(10000)
    candidate["margin_call_events"] = 1
    assert training_score(candidate) == -1e9


def test_validation_score_prefers_consistency_over_same_total_with_losing_half():
    steady = validation_score([metrics(500), metrics(500)])
    fragile = validation_score([metrics(1500), metrics(-500)])
    assert steady > fragile
    assert validation_score([metrics(500, drawdown=1000), metrics(500, drawdown=1000)]) < steady


def test_paired_bootstrap_preserves_equal_series_and_constant_paired_difference():
    days = pd.date_range("2025-01-01", periods=28, freq="D", tz="UTC")
    values = pd.Series(range(28), index=days, dtype=float)
    same = paired_week_bootstrap(values, values, samples=100)
    assert same["paired_net_pnl_difference"] == 0
    assert same["conditional_95pct_interval"] == [0, 0]
    positive = paired_week_bootstrap(values + 1, values, samples=100)
    assert positive["conditional_95pct_interval"] == [28, 28]
    with pytest.raises(ValueError, match="matching"):
        paired_week_bootstrap(values.iloc[1:], values, samples=100)


def test_checkpoint_reader_ignores_only_an_unfinished_last_line(tmp_path):
    path = tmp_path / "checkpoint.jsonl"
    path.write_text('{"id": 1}\n{"id":', encoding="utf-8")
    assert checkpoint_rows(path) == [{"id": 1}]
    path.write_text('{"id":}\n{"id": 2}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid checkpoint"):
        checkpoint_rows(path)


def test_pine_derivative_retains_source_license_and_explicit_execution_limits():
    from dataclasses import replace
    cfg = replace(baseline(), reward_r=3., min_stop_bps=80., risk_includes_costs=True)
    text = render_candidate(cfg, "frozen_test_candidate")
    assert "Mozilla Public License" in text
    assert 'strategy("DVS ETH v1.2' in text
    assert "process_orders_on_close=false" in text
    assert "commission_value=0.04" in text
    assert "minStopBps = input.float(80.0" in text
    assert "rewardR      = input.float(3.0" in text
    assert "costRisk = input.bool(true" in text
    assert "riskUSD / ((stopDistance + (costRisk ? estimatedCost : 0))" in text
    assert "NOT a verified TradingView/Python execution match" in text
    assert "financing" in text and "stop_first" in text
    assert text.count("//@version=6") == 1
    with pytest.raises(ValueError):
        render_candidate(StrategyConfig())


def test_dashboard_replays_frozen_candidate_without_mutating_parity_settings(tmp_path, monkeypatch):
    from dataclasses import asdict, replace
    import hashlib
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    import backtesting.paths as paths
    from test_date_ranges import history
    from backtesting.market_data import clean_candles

    bars, quality = clean_candles(history())
    data = tmp_path / "candles.parquet"
    bars.to_parquet(data, index=False)
    quality["parquet_sha256"] = hashlib.sha256(data.read_bytes()).hexdigest()
    data.with_suffix(".quality.json").write_text(json.dumps(quality), encoding="utf-8")
    monkeypatch.setattr(paths, "PARQUET", data)
    monkeypatch.setattr(paths, "RUNS", tmp_path / "artifacts/dvs")
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    directory = tmp_path / "artifacts/optimization/test_run"
    directory.mkdir(parents=True)
    cfg = replace(baseline(), min_stop_bps=80, risk_includes_costs=True)
    (directory / "manifest.json").write_text(json.dumps({"candidate_count": 2}), encoding="utf-8")
    (directory / "summary.json").write_text(json.dumps({
        "selection": {"candidate": {"label": "test candidate", "config": asdict(cfg)},
                      "passed_predeclared_validation_gate": True, "validation": {}},
        "full_history": {}, "audit": {}}), encoding="utf-8")
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "dashboard.py"), default_timeout=30).run()
    assert not app.exception
    next(b for b in app.button if b.label == "Backtest experimental candidate on selected dates").click().run()
    assert not app.exception and not app.error
    assert app.session_state["dvs_result"].config == asdict(cfg)
    assert app.sidebar.radio[0].value.startswith("A")  # run labels identify actual research config
    assert StrategyConfig().mode == "parity" and StrategyConfig().min_stop_bps == 0


def test_v1_2_export_saves_matching_config_and_honest_failed_gate_metadata(tmp_path, monkeypatch):
    import hashlib
    import backtesting.export_candidate as module
    from dataclasses import asdict, replace
    monkeypatch.setattr(module, "ROOT", tmp_path)
    (tmp_path / "configs").mkdir()
    directory = tmp_path / "experiment"
    directory.mkdir()
    cfg = replace(baseline(), reward_r=4, stop_atr=.5, min_atr_bps=10, risk_includes_costs=True)
    selection = {"candidate": {"label": "frozen_v1_2", "config": asdict(cfg)},
                 "passed_predeclared_validation_gate": False}
    (directory / "selection.json").write_text(json.dumps(selection), encoding="utf-8")
    output = tmp_path / "reference/DVS_ETH_v1_2.pine"
    module.export(directory, output)
    saved = json.loads((tmp_path / "configs/dvs_eth_v1_2.json").read_text())
    metadata = json.loads((tmp_path / "configs/dvs_eth_v1_2.metadata.json").read_text())
    assert saved == asdict(cfg)
    assert metadata["strategy_name"] == "DVS ETH v1.2"
    assert metadata["passed_predeclared_validation_gate"] is False
    assert metadata["pine_compilation_verified"] is False
    assert metadata["pine_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()


def test_refinement_keeps_baseline_parent_and_deterministic_bounded_neighborhood():
    from dataclasses import replace
    from backtesting.refine import refinement_configs, strict_validation_score
    cfg = replace(baseline(), reward_r=4., min_atr_bps=10., stop_atr=.5, risk_includes_costs=True)
    candidates = refinement_configs(cfg)
    assert len(candidates) == 128
    assert candidates == refinement_configs(cfg)
    assert candidates[0]["config"] == asdict(baseline())
    assert candidates[1]["config"] == asdict(cfg)
    assert strict_validation_score([metrics(-1), metrics(10000)]) == -1e9
    assert strict_validation_score([metrics(500), metrics(500)]) > -1e8

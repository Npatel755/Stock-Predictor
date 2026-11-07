import json
import numpy as np
import pandas as pd
import pytest
from quant_futures.cli import synthetic_fixture
from quant_futures.config import ResearchConfig
from quant_futures.research import run_research, code_identity, json_write, load_dataset
from quant_futures.paper import PaperSession, compare_paper_backtest
from quant_futures.backtest import run_backtest
from quant_futures.strategies import baseline
from quant_futures.features import build_features


def receipt(tmp_path):
    path = tmp_path/"tests.json"
    json_write(path, dict(passed=True, source_hash=code_identity()["source_hash"]))
    return path


def test_full_synthetic_pipeline_and_holdout_exclusion(tmp_path):
    path = synthetic_fixture(tmp_path/"fixture.parquet", sessions=2, bars_per_session=240)
    cfg = ResearchConfig(models=["logistic"], maximum_trials=1, minimum_training_bars=100, validation_bars=80)
    run = run_research(path, cfg, tmp_path/"run")
    summary = json.loads((run/"summary.json").read_text())
    assert summary["synthetic"] and summary["no_deployable_candidate"] and not summary["holdout_evaluated"]
    features = pd.read_parquet(run/"development_features.parquet")
    assert len(features) == int(480*.8)
    assert (run/"frozen_candidate.json").exists()


def test_feature_cache_reuses_only_matching_development_history(tmp_path):
    path = synthetic_fixture(tmp_path/"fixture.parquet", sessions=2, bars_per_session=120)
    cfg = ResearchConfig(models=[], maximum_trials=1, minimum_training_bars=80, validation_bars=40)
    first = run_research(path, cfg, tmp_path/"first")
    second = run_research(path, cfg, tmp_path/"second", feature_cache=first)
    from quant_futures.config import file_hash
    assert file_hash(first/"development_features.parquet") == file_hash(second/"development_features.parquet")
    changed = cfg.model_copy(update={"holdout_fraction": .3})
    with pytest.raises(ValueError, match="boundary mismatch"):
        run_research(path, changed, tmp_path/"wrong", feature_cache=first)


def test_paper_equals_backtest(bars, tmp_path):
    b = bars.iloc[:80]
    cfg = ResearchConfig()
    bundle = dict(candidate=dict(family="baseline", name="ema"), model=None,
        source_hash=code_identity()["source_hash"], config=cfg.model_dump(), synthetic=True)
    session = PaperSession(bundle, tmp_path/"paper", test_receipt=receipt(tmp_path), replay=True)
    for record in b.to_dict("records"):
        session.on_bar(record)
    paper = session.finish()
    expected = run_backtest(b, baseline("ema", b, build_features(b)), cfg)
    assert compare_paper_backtest(paper, expected)["accounting_matches"]
    pd.testing.assert_frame_equal(paper["curve"], expected["curve"])


def test_stale_bar_halts_paper(bars, tmp_path):
    cfg = ResearchConfig()
    bundle = dict(candidate=dict(family="baseline", name="ema"), model=None,
        source_hash=code_identity()["source_hash"], config=cfg.model_dump())
    session = PaperSession(bundle, tmp_path/"paper", test_receipt=receipt(tmp_path))
    with pytest.raises(ValueError, match="Stale"):
        session.on_bar(bars.iloc[0].to_dict(), now="2026-01-06T00:00Z")
    assert session.stopped and session.simulator.risk.killed
    with pytest.raises(PermissionError):
        session.reconnect()


def test_test_receipt_is_mandatory(tmp_path):
    path = tmp_path/"failed.json"
    json_write(path, dict(passed=False, source_hash=code_identity()["source_hash"]))
    with pytest.raises(PermissionError):
        PaperSession({}, tmp_path/"paper", test_receipt=path)


def test_bounded_prediction_matches_full_estimator(bars):
    from quant_futures.models import fit_model
    from quant_futures.labels import future_returns
    features = build_features(bars)
    fitted = fit_model("logistic", features, future_returns(bars), bars, calibration="none")
    repeated = pd.concat([features]*3, ignore_index=True)
    expected = fitted.base.predict_proba(repeated[fitted.columns])[:, 1]
    np.testing.assert_allclose(fitted.raw_probability(repeated), expected, rtol=1e-12, atol=1e-12)


def test_atomic_snapshot_retries_windows_sharing_lock(tmp_path, monkeypatch):
    from pathlib import Path
    original = Path.replace
    calls = []
    def busy_then_replace(self, target):
        calls.append(1)
        if len(calls) < 3:
            raise PermissionError("Simulated Windows sharing violation")
        return original(self, target)
    monkeypatch.setattr(Path, "replace", busy_then_replace)
    output = tmp_path/"state.json"
    json_write(output, {"complete": True})
    assert json.loads(output.read_text())["complete"] and len(calls) == 3

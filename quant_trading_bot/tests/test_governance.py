import json
import numpy as np
import pandas as pd
import pytest
from quant_futures.cli import synthetic_fixture
from quant_futures.config import ResearchConfig
from quant_futures.research import run_research, evaluate_holdout, load_dataset
from quant_futures.data import import_file, canonical, validate, SessionCalendar, resample_complete
from quant_futures.funded import AccountRules, FundedAccount
from quant_futures.optimization import nested_search
from quant_futures.features import build_features
from quant_futures.labels import future_returns


def test_holdout_is_consumed_across_run_directories(tmp_path):
    source = synthetic_fixture(tmp_path/"fixture.parquet", sessions=2)
    cfg = ResearchConfig(models=[], maximum_trials=1, minimum_training_bars=100, validation_bars=80)
    run = run_research(source, cfg, tmp_path/"one")
    report = evaluate_holdout(source, run, tmp_path/"global_governance")
    assert report["synthetic"] and report["single_use"]
    with pytest.raises(FileExistsError):
        evaluate_holdout(source, run, tmp_path/"global_governance")


def test_dataset_tampering_and_adjusted_price_block(bars, tmp_path):
    raw = tmp_path/"raw.parquet"
    bars.iloc[:10].to_parquet(raw, index=False)
    adjusted = tmp_path/"adjusted.parquet"
    import_file(raw, adjusted, provider="test", license_note="test only", timestamp_semantics="bar_open", price_basis="adjusted")
    with pytest.raises(ValueError, match="raw contract"):
        load_dataset(adjusted)
    good = tmp_path/"good.parquet"
    import_file(raw, good, provider="test", license_note="test only", timestamp_semantics="bar_open", price_basis="raw")
    good.write_bytes(b"modified")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_dataset(good)


def test_quote_quality(bars):
    b = bars.iloc[:2].copy()
    b["bid"], b["ask"] = 6000., 5999.
    _, report = validate(b)
    assert report["counts"]["invalid_quote"] == 2
    assert report["counts"]["stale_quote"] == 2


def test_daily_completed_schedule(bars):
    b = bars.iloc[:10].copy()
    schedule = pd.DataFrame(dict(session_id=["2026-01-05"], open_utc=["2026-01-05T14:30Z"], close_utc=["2026-01-05T14:40Z"]))
    result = resample_complete(b, 1440, calendar=SessionCalendar(schedule))
    assert len(result) == 1 and result.available_at.iloc[0] == pd.Timestamp("2026-01-05T14:40Z")
    assert len(resample_complete(b.iloc[:-1], 1440, calendar=SessionCalendar(schedule))) == 0


def test_static_and_intraday_floor():
    static = FundedAccount(AccountRules(method="static"))
    static.mark(53000, session="a")
    assert static.floor == 48000
    trailing = FundedAccount(AccountRules(method="intraday_trailing"))
    trailing.mark(53000, session="a")
    assert trailing.floor == 50100
    trailing.mark(50100, session="a")
    assert trailing.failed
    with pytest.raises(ValueError):
        AccountRules(daily_loss=-1)


def test_nested_search_has_inner_trials_only(bars):
    b = bars.iloc[:400].reset_index(drop=True)
    result = nested_search("logistic", b, build_features(b), future_returns(b), ResearchConfig(), max_trials=1)
    assert len(result["trials"]) == 1 and not result["final_test_accessed"]


def test_optuna_inner_search_when_available(bars):
    import importlib.util
    if importlib.util.find_spec("optuna") is None:
        pytest.skip("Optional Optuna unavailable")
    b = bars.iloc[:400].reset_index(drop=True)
    result = nested_search("logistic", b, build_features(b), future_returns(b), ResearchConfig(), max_trials=1, use_optuna=True)
    assert len(result["trials"]) == 1 and not result["final_test_accessed"]

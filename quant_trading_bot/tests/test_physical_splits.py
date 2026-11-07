import json
from pathlib import Path
import pandas as pd
import pytest
from quant_futures.config import file_hash
from quant_futures.splits import partition_catalog
from quant_futures.research import load_dataset


def make_catalog(tmp_path, bars):
    root = tmp_path/"market"
    root.mkdir()
    path = root/"MES.parquet"
    b = bars.iloc[:9].copy()
    b["timestamp_utc"] = pd.to_datetime([f"{day}T14:{minute:02d}Z" for day in ("2023-12-29", "2024-01-02", "2026-01-02") for minute in (30, 31, 32)])
    from quant_futures.data import canonical
    b = canonical(b)
    b.to_parquet(path, index=False)
    manifest = dict(dataset_version=file_hash(path), path=str(path), provider="functional fixture", license_note="test", coverage=dict(rows=9))
    path.with_suffix(".manifest.json").write_text(json.dumps(manifest))
    catalog = dict(active_job="test-job", dataset_version="test-version", active_root=str(root), synthetic=True,
        instruments=dict(MES=manifest))
    file = tmp_path/"catalog.json"
    file.write_text(json.dumps(catalog))
    return file, b, path


def test_physical_splits_are_disjoint_and_preserve_every_row(tmp_path, bars):
    catalog, original, old = make_catalog(tmp_path, bars)
    result = partition_catalog(catalog)
    parts = result["instruments"]["MES"]["splits"]
    assert [parts[x]["coverage"]["rows"] for x in ("train", "validation", "test")] == [3, 3, 3]
    combined = pd.concat([pd.read_parquet(parts[x]["path"]) for x in ("train", "validation", "test")], ignore_index=True)
    pd.testing.assert_frame_equal(original, combined)
    assert not old.exists()
    assert not combined.timestamp_utc.duplicated().any()
    development, manifest, _ = load_dataset(result["instruments"]["MES"]["path"])
    assert len(development) == 6 and development.timestamp_utc.max() < pd.Timestamp("2026-01-01T00:00Z")
    aggregated, _, _ = load_dataset(result["instruments"]["MES"]["path"], minutes=2)
    assert len(aggregated) == 2
    assert (aggregated.available_at == aggregated.timestamp_utc+pd.Timedelta(minutes=2)).all()
    with pytest.raises(PermissionError, match="Reserved test"):
        load_dataset(parts["test"]["path"])


def test_split_manifest_is_reproducible_and_never_random(tmp_path, bars):
    catalog, _, _ = make_catalog(tmp_path, bars)
    first = partition_catalog(catalog)
    second = partition_catalog(catalog)
    assert first["split_protocol"]["protocol_id"] == second["split_protocol"]["protocol_id"]
    assert first["instruments"]["MES"]["splits"] == second["instruments"]["MES"]["splits"]


def test_governed_research_fits_training_only_and_reserves_test_before_read(tmp_path, bars, monkeypatch):
    import quant_futures.research as research
    from quant_futures.config import ResearchConfig
    from quant_futures.data import canonical
    root = tmp_path/"market"
    root.mkdir()
    original = bars.copy()
    original["timestamp_utc"] = pd.DatetimeIndex(list(pd.date_range("2023-12-28T14:30Z", periods=500, freq="min"))
        + list(pd.date_range("2024-01-02T14:30Z", periods=300, freq="min"))
        + list(pd.date_range("2026-01-02T14:30Z", periods=200, freq="min")))
    source = root/"MES.parquet"
    canonical(original).to_parquet(source, index=False)
    metadata = dict(path=str(source), dataset_version=file_hash(source), provider="fixture", license_note="test", coverage=dict(rows=1000))
    source.with_suffix(".manifest.json").write_text(json.dumps(metadata))
    catalog = tmp_path/"catalog.json"
    catalog.write_text(json.dumps(dict(active_job="fixture", active_root=str(root), dataset_version="fixture", synthetic=True, instruments=dict(MES=metadata))))
    item = partition_catalog(catalog)["instruments"]["MES"]
    fitted_periods, reads = [], []
    real_fit, real_load = research._fit, research.load_dataset
    governance = tmp_path/"governance"
    def checked_fit(candidate, features, labels, training, cfg):
        assert training.timestamp_utc.max() < pd.Timestamp("2024-01-01T00:00Z")
        assert pd.to_datetime(labels.label_end, utc=True).max() < pd.Timestamp("2024-01-01T00:00Z")
        fitted_periods.append((len(training), training.timestamp_utc.max()))
        return real_fit(candidate, features, labels, training, cfg)
    def checked_load(path, *args, **kwargs):
        if str(path) == item["splits"]["test"]["path"]:
            assert kwargs.get("purpose") == "final_test"
            assert len(list(governance.glob("*.json"))) == 1
            reads.append("test")
        return real_load(path, *args, **kwargs)
    monkeypatch.setattr(research, "_fit", checked_fit)
    monkeypatch.setattr(research, "load_dataset", checked_load)
    cfg = ResearchConfig(models=["logistic"], maximum_trials=3, minimum_training_bars=100, validation_bars=80)
    monkeypatch.setattr(research, "BASELINES", [])
    run = research.run_research(item["path"], cfg, tmp_path/"research")
    assert fitted_periods and not reads
    attempts = json.loads((run/"attempts.json").read_text())
    assert next(x for x in attempts if x["candidate_id"] == "ml_logistic")["status"] == "completed"
    assert len(pd.read_parquet(run/"development_features.parquet")) == 800
    research.evaluate_holdout(item["path"], run, governance)
    assert reads == ["test"]
    with pytest.raises(FileExistsError):
        research.evaluate_holdout(item["path"], run, governance)
    assert reads == ["test"]

from pathlib import Path
import json
import pandas as pd
from quant_futures.dataset_catalog import select_schedule, replacement_plan, activate_and_replace
from quant_futures.config import file_hash


def test_roll_selection_cannot_use_current_day_volume():
    frame = pd.DataFrame([dict(instrument="MES", session_id=s, contract=c, volume=v)
        for s, values in zip(["2026-01-05", "2026-01-06", "2026-01-07"], [(100, 10), (10, 100), (10000, 1)])
        for c, v in zip(["MESH26", "MESM26"], values)])
    metadata = {c: dict(first="2026-01-04T23:00Z") for c in ("MESH26", "MESM26")}
    result = select_schedule(frame, metadata)
    assert result.contract.tolist() == ["MESH26", "MESH26", "MESM26"]


def test_replacement_is_scoped_and_only_after_validation(tmp_path):
    project = tmp_path/"quant"
    active = project/"data/market/new"
    active.mkdir(parents=True)
    data = active/"data.parquet"
    data.write_bytes(b"new data")
    old = project/"data/processed/synthetic.parquet"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"old data")
    other = tmp_path/"research/ETH.parquet"
    other.parent.mkdir()
    other.write_bytes(b"preserve")
    (project/"reports").mkdir()
    (project/"runs").mkdir()
    report = dict(status="validated", job_id="test", dataset_version="test-version", source_zip="original.zip")
    (active/"import_report.json").write_text(json.dumps(report))
    selected = {i: dict(path=str(data), dataset_version=file_hash(data)) for i in ("MES", "MNQ")}
    (active/"selected_datasets.json").write_text(json.dumps(selected))
    files, _ = replacement_plan(project, active)
    assert old in files and data not in files
    catalog, history = activate_and_replace(project, active)
    assert not old.exists() and data.exists() and other.exists()
    assert history["status"] == "complete" and catalog["active_job"] == "test"


def test_selected_parquet_is_readable_and_chronological(tmp_path, bars):
    from quant_futures.dataset_catalog import prepare_selected
    root = tmp_path/"market"
    raw = root/"contracts/MES"
    raw.mkdir(parents=True)
    b = bars.iloc[:6].copy()
    b = b.assign(raw_symbol="MESH6", instrument_id=1, publisher_id=1)
    b.to_parquet(raw/"2026.parquet", index=False)
    pd.DataFrame([dict(instrument="MES", session_id="2026-01-05", contract="MESH26", volume=6000)]).to_parquet(root/"session_volumes.parquet")
    (root/"contracts.json").write_text(json.dumps({"MESH26": dict(first=str(b.timestamp_utc.iloc[0]))}))
    (root/"import_report.json").write_text(json.dumps(dict(status="validated", dataset_version="test", job_id="test", license_note="functional test")))
    result = prepare_selected(root)
    out = pd.read_parquet(result["MES"]["path"])
    assert len(out) == 6 and out.timestamp_utc.is_monotonic_increasing
    assert result["MES"]["coverage"]["rows"] == 6

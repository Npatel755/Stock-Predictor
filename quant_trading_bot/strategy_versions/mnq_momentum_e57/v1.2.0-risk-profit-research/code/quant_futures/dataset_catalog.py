"""Versioned data catalog, causal front-contract selection and scoped replacement."""
from datetime import datetime, timezone
from pathlib import Path
import json
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from .config import file_hash, digest
from .contracts import expiration


def resolve_dataset(value, catalog_path=None):
    instrument, separator, role = str(value).partition(":")
    if instrument in ("MES", "MNQ", "ES", "NQ"):
        catalog_path = Path(catalog_path) if catalog_path else Path(__file__).resolve().parents[2]/"data/catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        item = catalog["instruments"][instrument]
        if separator:
            if role not in ("train", "validation", "test"):
                raise ValueError("Split must be train, validation or test")
            return Path(item["splits"][role]["path"])
        return Path(item["path"])
    return Path(value)


def select_schedule(volumes, contract_metadata):
    """Use preceding completed session volume; never the current session's volume.

    Explicit expiry prevents rolling backward. Missing selected-contract bars are
    left missing rather than replaced using the day's future realized liquidity.
    """
    schedules = []
    for instrument, group in volumes.groupby("instrument", sort=True):
        pivot = group.pivot_table(index="session_id", columns="contract", values="volume", aggfunc="sum", fill_value=0).sort_index()
        contracts = sorted(pivot.columns, key=expiration)
        current = None
        previous = None
        for session, today in pivot.iterrows():
            session_date = pd.Timestamp(session).date()
            eligible = [c for c in contracts if expiration(c) >= session_date]
            if not eligible:
                continue
            if current is None:
                first_time = min(pd.Timestamp(contract_metadata[c]["first"]) for c in eligible)
                observed = [c for c in eligible if pd.Timestamp(contract_metadata[c]["first"]) <= first_time]
                current = min(observed, key=expiration)
            elif expiration(current) < session_date:
                current = eligible[0]
            if previous is not None:
                candidates = [c for c in eligible if expiration(c) > expiration(current)]
                if candidates:
                    next_contract = candidates[0]
                    if previous.get(next_contract, 0) > previous.get(current, 0):
                        current = next_contract
            schedules.append(dict(instrument=instrument, session_id=session, contract=current,
                selection_rule="previous_completed_session_volume_with_expiry_guard"))
            previous = today
    return pd.DataFrame(schedules)


def prepare_selected(dataset_root):
    import duckdb
    from .databento_import import PARQUET_SCHEMA
    from .research import json_write
    root = Path(dataset_root).resolve()
    report = json.loads((root/"import_report.json").read_text())
    if report["status"] != "validated":
        raise ValueError("Raw archive requires quality review before selection")
    volumes = pd.read_parquet(root/"session_volumes.parquet")
    contract_metadata = json.loads((root/"contracts.json").read_text())
    schedule = select_schedule(volumes, contract_metadata)
    schedule.to_parquet(root/"roll_schedule.parquet", index=False)
    connection = duckdb.connect()
    connection.execute("SET threads=1")
    connection.execute("SET memory_limit='128MB'")
    connection.execute("SET enable_progress_bar=false")
    connection.register("selection", schedule)
    datasets = {}
    try:
        for instrument in ("MES", "MNQ", "ES", "NQ"):
            raw_files = sorted((root/"contracts"/instrument).glob("*.parquet"))
            if not raw_files:
                continue
            output = root/"selected"/f"{instrument}_1m.parquet"
            output.parent.mkdir(parents=True, exist_ok=True)
            # A single-threaded scan preserves the source ordering, but the explicit
            # sort makes downstream chronological guarantees independent of that.
            query = """SELECT r.* FROM read_parquet(?) r
                       INNER JOIN selection s ON r.instrument=s.instrument
                       AND r.session_id=s.session_id AND r.contract=s.contract
                       ORDER BY r.timestamp_utc"""
            rebuild = not output.exists()
            if output.exists() and output.with_suffix(".manifest.json").exists():
                previous = json.loads(output.with_suffix(".manifest.json").read_text())
                if previous["source_version"] != report["dataset_version"] or previous["dataset_version"] != file_hash(output):
                    raise ValueError("Existing selected data has different provenance")
                rebuild = previous.get("selector_version") != 2
            if rebuild:
                partial = output.with_suffix(".parquet.partial")
                # Sort one year at a time to bound RAM and temporary disk. A global
                # multi-million-row ORDER BY can otherwise exhaust a nearly full drive.
                with pq.ParquetWriter(partial, PARQUET_SCHEMA, compression="zstd", compression_level=6) as writer:
                    previous_contract = None
                    for raw_file in raw_files:
                        table = connection.from_query(query, params=[[str(raw_file)]]).to_arrow_table().select(PARQUET_SCHEMA.names).cast(PARQUET_SCHEMA)
                        if not len(table):
                            continue
                        contracts = table.column("contract").combine_chunks()
                        before = pa.concat_arrays([pa.array([previous_contract or contracts[0].as_py()], type=pa.string()), contracts.slice(0, len(contracts)-1)])
                        flags = pc.not_equal(contracts, before)
                        table = table.set_column(table.schema.get_field_index("is_roll_period"), "is_roll_period", flags)
                        previous_contract = contracts[-1].as_py()
                        writer.write_table(table, row_group_size=100000)
                partial.replace(output)
            stats = connection.execute("SELECT COUNT(*), CAST(MIN(timestamp_utc) AS VARCHAR), CAST(MAX(timestamp_utc) AS VARCHAR), COUNT(DISTINCT contract), SUM(CASE WHEN data_quality_flag<>'' THEN 1 ELSE 0 END) FROM read_parquet(?)", [str(output)]).fetchall()[0]
            duplicate = connection.execute("SELECT COUNT(*) FROM (SELECT timestamp_utc FROM read_parquet(?) GROUP BY timestamp_utc HAVING COUNT(*)>1)", [str(output)]).fetchall()[0][0]
            if duplicate:
                raise ValueError("Selected data contains duplicate decision timestamps")
            manifest = dict(dataset_version=file_hash(output), source_version=report["dataset_version"],
                source_job_id=report["job_id"], provider="User-provided Databento GLBX.MDP3 export",
                synthetic=False, raw_contract_prices=True, timestamp_semantics="bar_open", timeframe_minutes=1,
                license_note=report["license_note"], instrument=instrument,
                coverage=dict(rows=stats[0], start=str(stats[1]), end=str(stats[2]), contracts=stats[3], flagged_rows=stats[4]),
                roll_schedule_hash=file_hash(root/"roll_schedule.parquet"),
                selection_rule="previous completed session volume; forward expiries only; no price filling or back adjustment",
                selector_version=2,
                role="primary_micro_futures" if instrument in ("MES", "MNQ") else "mini_reference_or_explicit_proxy_only")
            json_write(output.with_suffix(".manifest.json"), manifest)
            datasets[instrument] = dict(path=str(output), **manifest)
            print(f"Prepared {instrument}: {stats[0]:,} selected one-minute bars", flush=True)
    finally:
        connection.close()
    json_write(root/"selected_datasets.json", datasets)
    return datasets


def replacement_plan(project_root, dataset_root):
    project = Path(project_root).resolve()
    active = Path(dataset_root).resolve()
    if not active.is_relative_to(project/"data"):
        raise ValueError("Replacement must stay inside the futures project's data directory")
    files, directories = [], []
    for path in (project/"data/processed", project/"data/raw/provider_samples"):
        if path.exists():
            files.extend(p for p in path.rglob("*") if p.is_file())
            directories.extend(p for p in path.rglob("*") if p.is_dir())
            directories.append(path)
    for path in (project/"data/market").glob("*"):
        if path != active and path.is_dir() and (path/"FAILED.json").exists():
            files.extend(p for p in path.rglob("*") if p.is_file())
            directories.extend(p for p in path.rglob("*") if p.is_dir())
            directories.append(path)
    for path in (project/"runs").glob("*"):
        if not path.is_dir():
            continue
        experiment, state = path/"experiment.json", path/"state.json"
        synthetic = experiment.exists() and json.loads(experiment.read_text()).get("synthetic") is True
        synthetic_paper = state.exists() and json.loads(state.read_text()).get("synthetic_model") is True
        if synthetic or synthetic_paper:
            files.extend(p for p in path.rglob("*") if p.is_file())
            directories.extend(p for p in path.rglob("*") if p.is_dir())
            directories.append(path)
    # Only this project's disposable pytest fixtures, never the repository's other experiments.
    for pattern in (".pytest_tmp*", ".pytest_*", ".test-tmp-*"):
        for path in project.glob(pattern):
            if path.is_dir() and path.name != ".pytest_cache":
                files.extend(p for p in path.rglob("*") if p.is_file())
                directories.extend(p for p in path.rglob("*") if p.is_dir())
                directories.append(path)
    files = sorted(set(files))
    for path in files:
        resolved = path.resolve()
        if not resolved.is_relative_to(project) or resolved.is_relative_to(active) or ".venv" in resolved.parts or ".clean-check" in resolved.parts:
            raise ValueError("Unsafe cleanup target")
    return files, sorted(set(directories), key=lambda p: len(p.parts), reverse=True)


def activate_and_replace(project_root, dataset_root):
    """Commit verified new data, then remove only authorized superseded generated data."""
    from .research import json_write
    project, root = Path(project_root).resolve(), Path(dataset_root).resolve()
    report = json.loads((root/"import_report.json").read_text())
    selected = json.loads((root/"selected_datasets.json").read_text())
    if report["status"] != "validated" or not {"MES", "MNQ"}.issubset(selected):
        raise ValueError("Validated replacement micro datasets required before cleanup")
    for instrument, item in selected.items():
        if str(item["path"]).endswith(".dataset.json"):
            descriptor = json.loads(Path(item["path"]).read_text())
            if descriptor["dataset_version"] != item["dataset_version"] or any(file_hash(p) != checksum for p, checksum in descriptor["file_hashes"].items()):
                raise ValueError("Prepared development partitions changed before activation")
        elif file_hash(item["path"]) != item["dataset_version"]:
            raise ValueError("Prepared dataset changed before activation")
    files, directories = replacement_plan(project, root)
    prior_path = project/"reports/data_replacement_history.json"
    prior = json.loads(prior_path.read_text()) if prior_path.exists() else {}
    if prior.get("new_job") != report["job_id"] or prior.get("new_root") != str(root):
        prior = {}
    history = dict(created_at=datetime.now(timezone.utc).isoformat(), new_job=report["job_id"], new_root=str(root),
        planned_files=prior.get("planned_files", [])+[dict(path=str(p.relative_to(project)), bytes=p.stat().st_size) for p in files],
        removed_files=list(prior.get("removed_files", [])), retained_directories=[],
        scope="Only generated futures-project data, synthetic runs and disposable test fixtures; original ETH/BNB research and user source ZIP untouched",
        old_summaries={**prior.get("old_summaries", {}), **{p.parent.name: json.loads(p.read_text()) for p in (project/"runs").glob("*/summary.json")}},
        environment_cleanup_blocked_by_automatic_review=True)
    json_write(project/"reports/data_replacement_history.json", history)
    catalog = dict(active_job=report["job_id"], active_root=str(root), dataset_version=report["dataset_version"],
        synthetic=False, source_zip=report["source_zip"], instruments=selected,
        supersedes="All earlier synthetic and public-sample futures data", created_at=datetime.now(timezone.utc).isoformat())
    existing_catalog = project/"data/catalog.json"
    if existing_catalog.exists():
        previous_catalog = json.loads(existing_catalog.read_text())
        if previous_catalog.get("active_job") == report["job_id"] and "split_protocol" in previous_catalog:
            catalog["split_protocol"] = previous_catalog["split_protocol"]
    json_write(project/"data/catalog.json", catalog)
    # The user explicitly requested replacement. The allowlist is resolved and
    # recorded above before deleting individual files; no broad recursive shell delete.
    try:
        for path in files:
            path.unlink()
            history["removed_files"].append(str(path.relative_to(project)))
        for path in directories:
            try:
                if path.exists() and not any(path.iterdir()):
                    path.rmdir()
            except PermissionError:
                history["retained_directories"].append(str(path.relative_to(project)))
        history["status"] = "complete"
    except OSError as error:
        history.update(status="cleanup_incomplete", error=str(error))
        json_write(project/"reports/data_replacement_history.json", history)
        raise
    json_write(project/"reports/data_replacement_history.json", history)
    return catalog, history

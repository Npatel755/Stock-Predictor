from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import uuid
import numpy as np
import pandas as pd
from .config import load_config, file_hash
from .data import canonical, import_file, validate, resample_complete, SessionCalendar
from .features import build_features
from .research import run_research, evaluate_holdout, load_dataset, json_write, code_identity

ROOT = Path(__file__).resolve().parents[2]


def synthetic_fixture(output, instrument="MES", sessions=6, bars_per_session=240, seed=20261106):
    """Deliberately artificial, uncalibrated random walk: functional tests only."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError("Do not overwrite fixture versions")
    rng = np.random.default_rng(seed)
    all_bars = []
    level = 6000 if instrument == "MES" else 21000
    for day in pd.bdate_range("2026-01-05", periods=sessions):
        n = bars_per_session
        close = level+np.cumsum(rng.choice([-2, -1, 0, 1, 2], n))*.25
        opening = np.r_[level, close[:-1]]
        high = np.maximum(opening, close)+rng.integers(1, 5, n)*.25
        low = np.minimum(opening, close)-rng.integers(1, 5, n)*.25
        times = pd.date_range(day.tz_localize("America/New_York").replace(hour=9, minute=30), periods=n, freq="1min").tz_convert("UTC")
        all_bars.append(pd.DataFrame(dict(timestamp_utc=times, instrument=instrument, contract=instrument+"H26",
            open=opening, high=high, low=low, close=close, volume=rng.integers(100, 2000, n))))
        level = float(close[-1])
    bars = canonical(pd.concat(all_bars, ignore_index=True))
    bars.to_parquet(output, index=False)
    report = validate(bars)[1]
    json_write(output.with_suffix(".manifest.json"), dict(dataset_version=file_hash(output), synthetic=True,
        provider="synthetic_fixture", license_note="Locally generated functional test; not market data",
        timestamp_semantics="bar_open", raw_contract_prices=True, seed=seed, coverage=report, instrument=instrument))
    json_write(output.with_suffix(".quality.json"), report)
    return output


def doctor(output):
    root = ROOT.parent
    files = []
    for sub in ("research/codex_eth_bnb/data", "backtesting/data", "instance"):
        location = root/sub
        if location.exists():
            for p in location.rglob("*"):
                if p.is_file() and p.suffix in (".parquet", ".csv", ".db"):
                    files.append(dict(path=str(p.relative_to(root)), bytes=p.stat().st_size))
    packages = ["numpy", "pandas", "sklearn", "lightgbm", "xgboost", "torch", "gymnasium", "optuna", "duckdb", "streamlit", "plotly"]
    available = {name: importlib.util.find_spec(name) is not None for name in packages}
    gpu = dict(available=False)
    if available["torch"]:
        import torch
        gpu = dict(available=torch.cuda.is_available(), cuda_version=torch.version.cuda,
            device=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)
    processes = []
    try:
        import psutil
        for p in psutil.process_iter(["pid", "name"]):
            if any(k in (p.info["name"] or "").lower() for k in ("python", "node", "wsl")):
                processes.append(p.info)
    except (ImportError, OSError):
        pass
    active_path = ROOT/"data/catalog.json"
    active_catalog = json.loads(active_path.read_text(encoding="utf-8")) if active_path.exists() else None
    result = dict(platform=platform.platform(), python=sys.version, packages=available, gpu=gpu,
        free_disk_bytes=shutil.disk_usage(ROOT).free, active_processes=processes,
        existing_data=files, existing_data_license="Not established for pre-existing crypto/equity datasets; not reused as MES/MNQ",
        futures_market_history_found=active_catalog is not None, active_market_job=None if active_catalog is None else active_catalog["active_job"],
        isolation_directory=str(ROOT), **code_identity())
    json_write(output, result)
    return result


def selftest(receipt):
    import pytest
    from threadpoolctl import threadpool_limits
    temp = ROOT/f".test-tmp-{uuid.uuid4().hex[:8]}"
    # Run in this process: duplicating imported numerical libraries in a child
    # exhausted Windows commit memory when the system drive could not grow its pagefile.
    with threadpool_limits(limits=1):
        return_code = int(pytest.main(["-q", "-p", "no:cacheprovider", "--basetemp", str(temp), str(ROOT/"tests")]))
    result = dict(passed=return_code == 0, source_hash=code_identity()["source_hash"],
        completed_at=datetime.now(timezone.utc).isoformat(), return_code=return_code,
        command="python -m pytest -q -p no:cacheprovider")
    Path(receipt).parent.mkdir(parents=True, exist_ok=True)
    json_write(receipt, result)
    if return_code:
        raise RuntimeError("Tests failed; paper trading stays blocked")
    return result


def parser():
    p = argparse.ArgumentParser(description="MES/MNQ research and paper-only tools")
    sub = p.add_subparsers(dest="command", required=True)
    doc = sub.add_parser("doctor")
    doc.add_argument("--output", default="reports/environment.json")
    test = sub.add_parser("selftest")
    test.add_argument("--receipt", default="reports/test_receipt.json")
    fixture = sub.add_parser("fixture")
    fixture.add_argument("--output", required=True)
    fixture.add_argument("--instrument", choices=["MES", "MNQ"], default="MES")
    fixture.add_argument("--sessions", type=int, default=6)
    ingest = sub.add_parser("import")
    ingest.add_argument("source")
    ingest.add_argument("output")
    ingest.add_argument("--provider", required=True)
    ingest.add_argument("--license-note", required=True)
    ingest.add_argument("--source-timezone")
    ingest.add_argument("--price-basis", required=True, choices=["raw", "adjusted", "unknown"])
    ingest.add_argument("--synthetic", action="store_true")
    check = sub.add_parser("validate")
    check.add_argument("dataset")
    check.add_argument("--schedule")
    check.add_argument("--output", default="reports/data_quality.json")
    feature = sub.add_parser("features")
    feature.add_argument("dataset")
    feature.add_argument("--output", required=True)
    feature.add_argument("--config", default="configs/research.yaml")
    rs = sub.add_parser("resample")
    rs.add_argument("dataset")
    rs.add_argument("--minutes", type=int, choices=[1, 2, 5, 15, 30, 60, 1440], required=True)
    rs.add_argument("--schedule")
    rs.add_argument("--output", required=True)
    for name in ("research", "baseline", "stress", "train", "walk-forward"):
        r = sub.add_parser(name)
        r.add_argument("dataset")
        r.add_argument("--config", default="configs/research.yaml")
        r.add_argument("--output", required=True)
        r.add_argument("--rules", default="configs/lucidflex.yaml")
    hold = sub.add_parser("holdout")
    hold.add_argument("dataset")
    hold.add_argument("--frozen", required=True)
    hold.add_argument("--governance", default="data/manifests/final_tests")
    for name in ("paper-replay", "paper-stream"):
        paper = sub.add_parser(name)
        paper.add_argument("source")
        paper.add_argument("--artifact", required=True)
        paper.add_argument("--output", required=True)
        paper.add_argument("--test-receipt", default="reports/test_receipt.json")
        if name == "paper-stream":
            paper.add_argument("--resume", action="store_true")
    cost = sub.add_parser("estimate-data-cost")
    cost.add_argument("--symbols", nargs="+", required=True)
    cost.add_argument("--start", required=True)
    cost.add_argument("--end", required=True)
    sub.add_parser("datasets")
    dbn = sub.add_parser("import-databento")
    dbn.add_argument("archive")
    dbn.add_argument("--output", required=True)
    dbn.add_argument("--replace-generated-data", action="store_true")
    split = sub.add_parser("split-data")
    split.add_argument("--train-end", default="2024-01-01T00:00:00Z")
    split.add_argument("--test-start", default="2026-01-01T00:00:00Z")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    command = args.command
    if command in ("doctor", "validate"):
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    if command == "doctor":
        result = doctor(args.output)
    elif command == "selftest":
        result = selftest(args.receipt)
    elif command == "fixture":
        result = dict(path=str(synthetic_fixture(args.output, args.instrument, args.sessions)), synthetic=True)
    elif command == "import":
        result = import_file(args.source, args.output, provider=args.provider, license_note=args.license_note,
            timestamp_semantics="bar_open", price_basis=args.price_basis, synthetic=args.synthetic, source_timezone=args.source_timezone)
    elif command == "validate":
        bars, _, _ = load_dataset(args.dataset, purpose="quality")
        calendar = SessionCalendar(pd.read_csv(args.schedule)) if args.schedule else None
        _, result = validate(bars, calendar=calendar)
        json_write(args.output, result)
    elif command == "features":
        bars, manifest, _ = load_dataset(args.dataset)
        cfg = load_config(args.config)
        governed = manifest.get("split_role") in ("train", "development")
        cutoff = len(bars) if governed else int(len(bars)*(1-cfg.holdout_fraction))
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            raise FileExistsError("Choose a new feature cache version")
        f = build_features(bars.iloc[:cutoff], cfg.timeframe_minutes)
        f.to_parquet(output, index=False)
        json_write(output.with_suffix(".manifest.json"), dict(dataset_version=manifest["dataset_version"],
            synthetic=manifest["synthetic"], rows=len(f), final_holdout_excluded=True,
            holdout_start=manifest.get("test_start_inclusive") if governed else str(bars.timestamp_utc.iloc[cutoff]), source_hash=code_identity()["source_hash"]))
        result = dict(output=str(output), rows=len(f), final_holdout_excluded=True)
    elif command == "resample":
        bars, _, _ = load_dataset(args.dataset)
        calendar = SessionCalendar(pd.read_csv(args.schedule)) if args.schedule else None
        out = resample_complete(bars, args.minutes, calendar=calendar)
        out.to_parquet(args.output, index=False)
        result = dict(rows=len(out), note="Import this version with provenance before research; bar availability timestamps retained")
    elif command in ("research", "baseline", "stress", "train", "walk-forward"):
        cfg = load_config(args.config)
        if command == "baseline":
            cfg = cfg.model_copy(update={"models": []})
        result = dict(output=str(run_research(args.dataset, cfg, args.output, args.rules)))
    elif command == "holdout":
        result = evaluate_holdout(args.dataset, args.frozen, args.governance)
    elif command in ("paper-replay", "paper-stream"):
        import joblib
        from .paper import PaperSession, ReplayAdapter, JsonLinesAdapter
        from .durable_paper import DurablePaperSession, watchdog_stream
        bundle = joblib.load(args.artifact)
        replay = command == "paper-replay"
        session = PaperSession(bundle, args.output, test_receipt=args.test_receipt, replay=True) if replay else DurablePaperSession(bundle, args.output, test_receipt=args.test_receipt, resume=args.resume)
        source_file = None
        if replay:
            bars, _, _ = load_dataset(args.source, minutes=session.cfg.timeframe_minutes)
            adapter = ReplayAdapter(bars)
        else:
            source_file = sys.stdin if args.source == "-" else open(args.source, encoding="utf-8")
            adapter = JsonLinesAdapter(source_file)
        try:
            adapter.connect()
            for record in (adapter.stream() if replay else watchdog_stream(adapter, session)):
                session.on_bar(record)
            results = session.finish()
            result = dict(output=args.output, mode="paper-replay" if replay else "paper",
                **(dict(trades=len(results["trades"])) if replay else results))
        except Exception:
            session.stop("adapter_or_inference_failure")
            raise
        finally:
            adapter.close()
            if source_file and source_file is not sys.stdin:
                source_file.close()
    elif command == "estimate-data-cost":
        from .providers import databento_cost_estimate
        result = databento_cost_estimate(args.symbols, args.start, args.end)
    elif command == "datasets":
        result = json.loads((ROOT/"data/catalog.json").read_text(encoding="utf-8"))
    elif command == "split-data":
        from .splits import partition_catalog
        catalog = partition_catalog(ROOT/"data/catalog.json", args.train_end, args.test_start)
        result = {name: {role: part["coverage"] for role, part in item["splits"].items()} for name, item in catalog["instruments"].items()}
    elif command == "import-databento":
        from .databento_import import ingest_zip
        from .dataset_catalog import prepare_selected, activate_and_replace
        imported = ingest_zip(args.archive, args.output)
        selected = prepare_selected(args.output)
        result = dict(import_report=imported, selected=selected)
        if args.replace_generated_data:
            catalog, history = activate_and_replace(ROOT, args.output)
            result = dict(active_catalog=catalog, removed_files=len(history["removed_files"]))
    else:
        raise ValueError(command)
    print(json.dumps(result, default=str, indent=2))


if __name__ == "__main__":
    main()

"""One explicitly requested, disclosed reused-test evaluation; never a search."""
import os
for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import pandas as pd
from threadpoolctl import threadpool_limits
from quant_futures.config import digest, file_hash
from quant_futures.research import code_identity, json_write, load_dataset
from quant_futures.transfer import morning_indexes
from quant_futures.validation import freeze_candidate

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_ID = "follow_cf9f62ca20"


def archived_execution(directory):
    strategy = Path(directory)/"strategy"
    sys.path.insert(0,str(strategy))
    spec = importlib.util.spec_from_file_location("frozen_saved_execution",strategy/"profit_drawdown_followup.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare():
    saved_path = ROOT/"reports/saved_candidates"/CANDIDATE_ID/"candidate.json"
    saved = json.loads(saved_path.read_text(encoding="utf-8"))
    row = saved["candidate"]
    if row["candidate_id"] != CANDIDATE_ID or row["metrics"]["net_pnl"] != 6622:
        raise ValueError("Requested saved version changed")
    source = Path(saved["source_run"]).resolve()
    if not source.is_relative_to(ROOT):
        raise ValueError("Archived source must remain within this project")
    parent = json.loads((source/"results.json").read_text())
    identity = code_identity()
    if parent["source_hash"] != identity["source_hash"]:
        raise ValueError("Core execution source changed since the saved version")
    directory = ROOT/"runs"/("reused_test_"+CANDIDATE_ID)
    directory.mkdir(exist_ok=False)
    strategy = directory/"strategy"
    strategy.mkdir()
    for filename, expected in parent["script_hashes"].items():
        original = source/filename
        if file_hash(original) != expected:
            raise ValueError("Archived strategy identity mismatch: "+filename)
        shutil.copyfile(original,strategy/filename)
    execution = archived_execution(directory)
    parameters = row["candidate"]
    cfg = execution.engine.base.configuration("MNQ",parameters)
    catalog = json.loads((ROOT/"data/catalog.json").read_text(encoding="utf-8"))
    test = catalog["instruments"]["MNQ"]["splits"]["test"]
    warmup = catalog["instruments"]["MNQ"]["splits"]["validation"]
    original = ROOT/"data/manifests/final_tests"/(digest(dict(test_partition=test["dataset_version"]))+".json")
    if not original.exists():
        raise ValueError("Expected original consumed test record missing")
    frozen = dict(candidate_id=CANDIDATE_ID,parameters=parameters,configuration=cfg.model_dump(),
        **identity,strategy_hashes=parent["script_hashes"],saved_candidate_sha256=file_hash(saved_path),
        original_reservation_path=str(original),original_reservation_sha256=file_hash(original),
        original_test_report_sha256=file_hash(ROOT/"reports/final_candidate_test.json"),
        test_partition=test,warmup_partition=warmup,warmup_start="2025-10-01T00:00Z",
        runner_sha256=file_hash(__file__),
        user_authorization="Explicit user request: test this saved version on test data WITHOUT tuning against it.",
        period_role="reused_test_diagnostic",independent_confirmation=False,
        selection_history="This exact version was selected using reused 2024–2025 validation results; 2026 was consumed by an earlier candidate.",
        evaluation_protocol="One base-cost replay of the exact frozen saved version. No fitting, parameter search, cost variants, selection feedback, or subsequent retuning from this outcome. Prior complete sessions provide causal warmup only.",
        failure_policy="A reserved failed attempt is retained and cannot silently reset the reservation.",
        predeclared_metrics=["net_pnl","max_drawdown","max_intraday_drawdown_bound","trades","permanent_risk_lock","uncertainty"],
        deployment_eligible=False)
    freeze_candidate(directory/"frozen_candidate.json",frozen)
    shutil.copyfile(__file__,directory/"test_runner.py")
    json_write(directory/"preflight.json",dict(passed=True,test_price_columns_read=False,
        parameters_frozen=True,exact_archived_strategy_verified=True,independent_confirmation=False))
    print(json.dumps(dict(prepared=str(directory),candidate_id=CANDIDATE_ID,test_loaded=False)))
    return directory


def verify_freeze(directory):
    directory = Path(directory)
    manifest = json.loads((directory/"frozen_candidate.json").read_text())
    frozen = manifest["candidate"]
    if digest(frozen) != manifest["candidate_hash"] or frozen["candidate_id"] != CANDIDATE_ID:
        raise ValueError("Frozen candidate identity changed")
    if code_identity()["source_hash"] != frozen["source_hash"] or file_hash(__file__) != frozen["runner_sha256"]:
        raise ValueError("Frozen execution or runner changed")
    for filename, expected in frozen["strategy_hashes"].items():
        if file_hash(directory/"strategy"/filename) != expected:
            raise ValueError("Frozen strategy source changed")
    if file_hash(frozen["original_reservation_path"]) != frozen["original_reservation_sha256"]:
        raise ValueError("Original consumed reservation was altered")
    if file_hash(ROOT/"reports/final_candidate_test.json") != frozen["original_test_report_sha256"]:
        raise ValueError("Original test report was altered")
    return manifest,frozen


def reserve(directory,manifest,frozen):
    # Dedicated reused-test record; the original holdout reservation is never
    # deleted, overwritten or relabeled as an untouched test.
    key = digest(dict(dataset=frozen["test_partition"]["dataset_version"],
        candidate_id=CANDIDATE_ID,parameters=frozen["parameters"]))
    path = ROOT/"data/manifests/reused_tests"/(key+".json")
    path.parent.mkdir(parents=True,exist_ok=True)
    record = dict(reserved_at=datetime.now(timezone.utc).isoformat(),candidate_id=CANDIDATE_ID,
        frozen_candidate_hash=manifest["candidate_hash"],dataset_version=frozen["test_partition"]["dataset_version"],
        path=str(directory),period_previously_consumed=True,independent_confirmation=False,
        no_tuning=True,state="reserved; failure also consumes this frozen-version evaluation")
    with path.open("x",encoding="utf-8") as stream:
        json.dump(record,stream,indent=2)
    return path


def evaluate(directory):
    directory = Path(directory)
    manifest,frozen = verify_freeze(directory)
    reservation = reserve(directory,manifest,frozen)
    json_write(directory/"evaluation_state.json",dict(state="reserved",test_price_columns_read=False))
    execution = archived_execution(directory)
    test = frozen["test_partition"]
    actual,metadata,quality = load_dataset(test["path"],purpose="final_test",minutes=1)
    if metadata["dataset_version"] != test["dataset_version"] or metadata.get("split_role") != "test":
        raise ValueError("Frozen test partition mismatch")
    if not (actual.instrument.eq("MNQ").all() and actual.timestamp_utc.ge(pd.Timestamp("2026-01-01T00:00Z")).all()
            and actual.timestamp_utc.lt(pd.Timestamp("2027-01-01T00:00Z")).all()):
        raise PermissionError("Unexpected test symbol or time bounds")
    warmup = frozen["warmup_partition"]
    if warmup["split_role"] != "validation" or file_hash(warmup["path"]) != warmup["dataset_version"]:
        raise ValueError("Warmup partition mismatch")
    warm = pd.read_parquet(warmup["path"],filters=[("timestamp_utc",">=",pd.Timestamp(frozen["warmup_start"]))])
    if not warm.timestamp_utc.lt(actual.timestamp_utc.iloc[0]).all():
        raise PermissionError("Warmup must precede the evaluated test bars")
    combined = pd.concat([warm,actual],ignore_index=True)
    active = morning_indexes(actual)
    signal = execution.signals_for(combined,frozen["parameters"]).iloc[len(warm):].iloc[active].reset_index(drop=True)
    bars = actual.iloc[active].reset_index(drop=True)
    del actual,warm,combined
    result = execution.replay(bars,signal,frozen["parameters"],"MNQ")
    measured = execution.engine.base.measured(result,"MNQ")
    result["curve"].to_parquet(directory/"test_equity.parquet",index=False)
    result["trades"].to_parquet(directory/"test_trades.parquet",index=False)
    json_write(directory/"test_events.json",result["events"])
    checks = dict(positive_net=measured["net_pnl"] > 0,
        closing_drawdown_under_2000=measured["max_drawdown"] < 2000,
        intrabar_drawdown_under_2000=measured["max_intraday_drawdown_bound"] < 2000,
        no_permanent_shutdown=not measured["permanent_risk_lock"],
        enough_trades=measured["trades"] >= 30,
        positive_confidence=measured["uncertainty"]["mean_ci"][0] is not None and measured["uncertainty"]["mean_ci"][0] > 0)
    report = dict(completed_at=datetime.now(timezone.utc).isoformat(),path=str(directory),
        candidate_id=CANDIDATE_ID,candidate_parameters=frozen["parameters"],
        frozen_candidate_hash=manifest["candidate_hash"],source_hash=frozen["source_hash"],
        test_dataset_version=metadata["dataset_version"],coverage=metadata["coverage"],metrics=measured,checks=checks,
        period_role="reused_test_diagnostic",period_previously_consumed=True,independent_confirmation=False,
        no_tuning=True,parameter_variants_evaluated=1,cost_variants_evaluated=1,
        original_test_reservation_preserved=file_hash(frozen["original_reservation_path"]) == frozen["original_reservation_sha256"],
        original_test_report_preserved=file_hash(ROOT/"reports/final_candidate_test.json") == frozen["original_test_report_sha256"],
        reservation=str(reservation),deployment_eligible=False,
        next_step_policy="Report this exact outcome. Do not adjust parameters or evaluate follow-up variants using this period. New independent confirmation requires new forward observations.")
    json_write(directory/"test_results.json",report)
    json_write(ROOT/"reports/saved_version_reused_test.json",report)
    json_write(directory/"evaluation_state.json",dict(state="completed; no retuning",completed_at=report["completed_at"]))
    print(json.dumps(dict(candidate_id=CANDIDATE_ID,
        metrics={key:measured[key] for key in ("net_pnl","max_drawdown","max_intraday_drawdown_bound","trades","permanent_risk_lock")},
        checks=checks,no_tuning=True),indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare",action="store_true")
    parser.add_argument("--evaluate")
    args = parser.parse_args()
    with threadpool_limits(limits=1):
        if args.prepare:
            prepare()
        elif args.evaluate:
            evaluate(args.evaluate)
        else:
            parser.error("Choose --prepare or --evaluate FROZEN_DIRECTORY")

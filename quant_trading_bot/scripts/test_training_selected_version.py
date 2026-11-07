"""One user-authorized test of the exact already validated training selection."""
import os
for key in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"):
    os.environ[key] = "1"
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
import pandas as pd
from threadpoolctl import threadpool_limits
import evaluate_saved_frozen_version as archive
from quant_futures.config import digest,file_hash
from quant_futures.research import code_identity,json_write,load_dataset
from quant_futures.transfer import morning_indexes
from quant_futures.validation import freeze_candidate

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = "train_725a5b5da1"
DIRECTORY = ROOT/"runs/reused_test_train_725a5b5da1"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def prepare():
    source = ROOT/"runs/training_only_selection_v1"
    original = read(source/"frozen_candidate.json")
    trained = original["candidate"]
    validation_path = ROOT/"reports/training_selected_validation.json"
    validation = read(validation_path)
    if digest(trained) != original["candidate_hash"] or trained["candidate_id"] != CANDIDATE:
        raise ValueError("Training freeze changed")
    if validation["candidate_id"] != CANDIDATE or validation["candidate"] != trained["parameters"] or validation["frozen_candidate_hash"] != original["candidate_hash"]:
        raise ValueError("Validation is not the exact frozen training version")
    identity = code_identity()
    if identity["source_hash"] != trained["source_hash"]:
        raise ValueError("Core simulator changed since validation")
    DIRECTORY.mkdir(exist_ok=False)
    (DIRECTORY/"strategy").mkdir()
    for filename,expected in trained["script_hashes"].items():
        path = source/filename
        if file_hash(path) != expected:
            raise ValueError("Frozen strategy archive mismatch: "+filename)
        shutil.copyfile(path,DIRECTORY/"strategy"/filename)
    dependency = ROOT/"scripts/overnight_study.py"
    shutil.copyfile(dependency,DIRECTORY/"strategy"/dependency.name)
    execution = archive.archived_execution(DIRECTORY)
    cfg = execution.engine.base.configuration("MNQ",trained["parameters"])
    catalog = read(ROOT/"data/catalog.json")
    test = catalog["instruments"]["MNQ"]["splits"]["test"]
    preserve = [ROOT/"reports/final_candidate_test.json",ROOT/"reports/saved_version_reused_test.json",validation_path,
        source/"frozen_candidate.json",source/"validation_equity.parquet",source/"validation_trades.parquet"]
    preserve += list((ROOT/"data/manifests/final_tests").glob("*.json"))
    preserve += list((ROOT/"data/manifests/reused_tests").glob("*.json"))
    frozen = dict(candidate_id=CANDIDATE,parameters=trained["parameters"],configuration=cfg.model_dump(),
        **identity,training_freeze_hash=original["candidate_hash"],
        strategy_hashes={**trained["script_hashes"],dependency.name:file_hash(dependency)},
        preserved_files={str(path):file_hash(path) for path in preserve},
        test_partition=test,warmup_partition=catalog["instruments"]["MNQ"]["splits"]["validation"],
        warmup_start="2025-10-01T00:00Z",runner_sha256=file_hash(__file__),
        user_authorization="Test this exact version on testing and validation splits without tuning; preserve its already-completed validation evaluation.",
        protocol="One fixed candidate and one base-cost test replay. No fitting, parameter search, cost variants, alternate candidates or post-result retuning. Use preceding complete sessions for causal warmup only.",
        period_role="reused_test_diagnostic",independent_confirmation=False,
        historical_contamination=trained["historical_contamination"],training_qualified=trained["training_qualified"],
        failure_consumes_reservation=True,deployment_eligible=False)
    freeze_candidate(DIRECTORY/"frozen_candidate.json",frozen)
    shutil.copyfile(__file__,DIRECTORY/"test_runner.py")
    json_write(DIRECTORY/"preflight.json",dict(passed=True,parameters_equal_training_and_validation=True,
        test_prices_opened=False,validation_replayed=False))
    print(json.dumps(dict(prepared=str(DIRECTORY),candidate_id=CANDIDATE,test_prices_opened=False)))


def verify():
    manifest = read(DIRECTORY/"frozen_candidate.json")
    frozen = manifest["candidate"]
    if digest(frozen) != manifest["candidate_hash"] or frozen["candidate_id"] != CANDIDATE:
        raise ValueError("Frozen candidate changed")
    if file_hash(__file__) != frozen["runner_sha256"] or code_identity()["source_hash"] != frozen["source_hash"]:
        raise ValueError("Runner/core source changed")
    for filename,expected in frozen["strategy_hashes"].items():
        if file_hash(DIRECTORY/"strategy"/filename) != expected:
            raise ValueError("Frozen strategy changed")
    for path,expected in frozen["preserved_files"].items():
        if file_hash(path) != expected:
            raise ValueError("Prior result changed: "+path)
    return manifest,frozen


def reserve(manifest,frozen):
    key = digest(dict(candidate_id=CANDIDATE,parameters=frozen["parameters"],dataset=frozen["test_partition"]["dataset_version"]))
    path = ROOT/"data/manifests/reused_tests"/(key+".json")
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x",encoding="utf-8") as stream:
        json.dump(dict(candidate_id=CANDIDATE,candidate_hash=manifest["candidate_hash"],
            dataset_version=frozen["test_partition"]["dataset_version"],reserved_at=datetime.now(timezone.utc).isoformat(),
            no_tuning=True,failure_consumes_reservation=True,period_previously_consumed=True),stream,indent=2)
    return path


def evaluate():
    manifest,frozen = verify()
    reservation = reserve(manifest,frozen)
    json_write(DIRECTORY/"evaluation_state.json",dict(state="reserved; failure consumes this version"))
    execution = archive.archived_execution(DIRECTORY)
    partition = frozen["test_partition"]
    actual,metadata,_ = load_dataset(partition["path"],purpose="final_test",minutes=1)
    if metadata["dataset_version"] != partition["dataset_version"] or metadata["split_role"] != "test":
        raise ValueError("Frozen test dataset mismatch")
    if not (actual.instrument.eq("MNQ").all() and actual.timestamp_utc.ge(pd.Timestamp("2026-01-01T00:00Z")).all()
            and actual.timestamp_utc.lt(pd.Timestamp("2027-01-01T00:00Z")).all()):
        raise PermissionError("Unexpected instrument/date boundary")
    warmup = frozen["warmup_partition"]
    if warmup["split_role"] != "validation" or file_hash(warmup["path"]) != warmup["dataset_version"]:
        raise ValueError("Causal warmup provenance mismatch")
    warm = pd.read_parquet(warmup["path"],filters=[("timestamp_utc",">=",pd.Timestamp(frozen["warmup_start"]))])
    if not warm.timestamp_utc.lt(actual.timestamp_utc.iloc[0]).all():
        raise PermissionError("Warmup must precede test")
    combined = pd.concat([warm,actual],ignore_index=True)
    active = morning_indexes(actual)
    signals = execution.signals_for(combined,frozen["parameters"]).iloc[len(warm):].iloc[active].reset_index(drop=True)
    bars = actual.iloc[active].reset_index(drop=True)
    del warm,actual,combined
    result = execution.replay(bars,signals,frozen["parameters"],"MNQ",retain_events=False)
    metrics = execution.engine.base.measured(result,"MNQ")
    result["curve"].to_parquet(DIRECTORY/"test_equity.parquet",index=False)
    result["trades"].to_parquet(DIRECTORY/"test_trades.parquet",index=False)
    checks = dict(positive_net=bool(metrics["net_pnl"] > 0),
        closing_drawdown_under_2000=bool(metrics["max_drawdown"] < 2000),
        intrabar_drawdown_under_2000=bool(metrics["max_intraday_drawdown_bound"] < 2000),
        no_permanent_shutdown=not metrics["permanent_risk_lock"],enough_trades=metrics["trades"] >= 30,
        positive_confidence=bool(metrics["uncertainty"]["mean_ci"][0] is not None and metrics["uncertainty"]["mean_ci"][0] > 0))
    preserved = all(file_hash(path) == expected for path,expected in frozen["preserved_files"].items())
    if not preserved:
        raise ValueError("An earlier frozen artifact changed")
    report = dict(path=str(DIRECTORY),completed_at=datetime.now(timezone.utc).isoformat(),candidate_id=CANDIDATE,
        candidate=frozen["parameters"],metrics=metrics,checks=checks,coverage=metadata["coverage"],
        frozen_candidate_hash=manifest["candidate_hash"],training_freeze_hash=frozen["training_freeze_hash"],
        training_qualified=frozen["training_qualified"],test_dataset_version=metadata["dataset_version"],
        no_tuning=True,parameter_variants_evaluated=1,cost_variants_evaluated=1,validation_replayed=False,
        prior_artifacts_preserved=preserved,period_previously_consumed=True,independent_confirmation=False,
        reservation=str(reservation),deployment_eligible=False,
        next_step="Report as observed. Do not tune against this outcome or evaluate follow-up variants on this period.")
    json_write(DIRECTORY/"test_result.json",report)
    json_write(ROOT/"reports/training_selected_test.json",report)
    json_write(DIRECTORY/"evaluation_state.json",dict(state="completed; no tuning",completed_at=report["completed_at"]))
    print(json.dumps(dict(candidate_id=CANDIDATE,net=metrics["net_pnl"],drawdown=metrics["max_drawdown"],
        intrabar=metrics["max_intraday_drawdown_bound"],trades=metrics["trades"],checks=checks),indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare",action="store_true")
    group.add_argument("--evaluate",action="store_true")
    args = parser.parse_args()
    with threadpool_limits(limits=1):
        prepare() if args.prepare else evaluate()

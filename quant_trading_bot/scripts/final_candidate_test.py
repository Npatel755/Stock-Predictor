"""Freeze one research candidate and evaluate the 2026 market test once.

No parameter search is performed here. Failed attempts consume the reservation.
The observed result cannot authorize live execution or guarantee future risk.
"""
import os
for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import shutil
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from adaptive_opening_study import adaptive_config, adaptive_replay, known_atr
from opening_range_study import opening_intents
from quant_futures.transfer import morning_indexes, guarded_partition
from quant_futures.research import load_dataset, code_identity, json_write
from quant_futures.config import digest, file_hash
from quant_futures.metrics import summarize
from quant_futures.validation import freeze_candidate, reserve_holdout

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_ID = "adaptive_5e8e9edd3e"


def replay(bars, parameters, prefix=None):
    complete = bars if prefix is None else pd.concat([prefix, bars], ignore_index=True)
    start = 0 if prefix is None else len(prefix)
    atr = known_atr(complete).shift().iloc[start:].reset_index(drop=True)
    intents = opening_intents(complete, parameters["opening"], parameters["long_only"]).iloc[start:].reset_index(drop=True)
    active = morning_indexes(bars)
    b, s, a = bars.iloc[active].reset_index(drop=True), intents.iloc[active].reset_index(drop=True), atr.iloc[active].reset_index(drop=True)
    cfg = adaptive_config("MNQ")
    result = adaptive_replay(b, s, cfg, a, parameters["multiple"], parameters["payoff"])
    return result, b, s, a, cfg


def prepare():
    study = json.loads((ROOT/"reports/latest_adaptive_opening_study.json").read_text())
    identity = code_identity()
    if study["source_hash"] != identity["source_hash"]:
        raise ValueError("Core source changed since the candidate study")
    parent = Path(study["path"])
    strategy_file = ROOT/"scripts/adaptive_opening_study.py"
    if file_hash(strategy_file) != study["script_sha256"] or file_hash(strategy_file) != file_hash(parent/"study_script.py"):
        raise ValueError("Strategy script changed since validation")
    candidate = next(row for row in study["pairs"]["NQ->MNQ"]["validation_results"] if row["candidate_id"] == CANDIDATE_ID)
    frozen_training = json.loads((parent/"NQ_frozen_selection.json").read_text())
    if not any(row["candidate_id"] == CANDIDATE_ID and row["candidate"] == candidate["candidate"] for row in frozen_training["selected"]):
        raise ValueError("Candidate was not frozen before micro validation")
    validation, metadata, _ = guarded_partition("MNQ", "validation", minutes=1)
    result, _, _, _, cfg = replay(validation, candidate["candidate"])
    measured = summarize(result, cfg.initial_balance, trials=1024)
    for field in ("net_pnl", "max_drawdown", "max_intraday_drawdown_bound", "trades"):
        if not np.isclose(measured[field], candidate["metrics"][field], rtol=0, atol=1e-8):
            raise ValueError(f"Validation reproduction failed: {field}")
    catalog = json.loads((ROOT/"data/catalog.json").read_text())
    test = catalog["instruments"]["MNQ"]["splits"]["test"]
    frozen = dict(candidate_id=CANDIDATE_ID, parameters=candidate["candidate"], instrument="MNQ", timeframe_minutes=1,
        training_reference="NQ 2010–2023", model_selection="Reference training screen and 2024–2025 actual MNQ validation",
        selection_reason="Highest observed positive micro validation net among the registered drawdown-constrained reference studies; remained positive at 1.5x/2x/3x costs. This selection uses validation as intended; final test never used for selection.",
        unresolved_validation_checks=candidate["checks"], validation_metrics=measured,
        caveats="Earlier reference training economics and validation confidence checks failed. This one-time final evaluation is diagnostic; it cannot erase those failures or grant deployment eligibility.",
        configuration=cfg.model_dump(), **identity,
        strategy_script_sha256=file_hash(strategy_file), opening_intents_script_sha256=file_hash(ROOT/"scripts/opening_range_study.py"),
        test_runner_sha256=file_hash(__file__), source_validation_version=metadata["dataset_version"],
        test_partition=test, split_protocol_id=catalog["split_protocol"]["protocol_id"],
        predeclared_test_checks=["positive net P&L", "maximum close and adverse-intrabar drawdown below $2000", "trade sample", "session block-bootstrap interval", "1.5x/2x/3x cost stress"],
        failure_policy="No tuning or second candidate on the same 2026 market period. A failed runtime attempt also consumes the reservation.", deployment_eligible=False)
    directory = ROOT/"runs"/("final_test_"+CANDIDATE_ID)
    directory.mkdir(exist_ok=False)
    freeze_candidate(directory/"frozen_candidate.json", frozen)
    shutil.copyfile(__file__, directory/"test_runner.py")
    for script in (strategy_file, ROOT/"scripts/opening_range_study.py"):
        shutil.copyfile(script, directory/script.name)
    json_write(directory/"preflight.json", dict(passed=True, source_hash=identity["source_hash"], validation_reproduced=True,
        validation_metrics=measured, test_price_columns_read=False))
    print(json.dumps(dict(preflight="passed", frozen=str(directory), validation_pnl=measured["net_pnl"], test_loaded=False)))
    return directory


def evaluate(directory):
    directory = Path(directory)
    manifest = json.loads((directory/"frozen_candidate.json").read_text())
    candidate = manifest["candidate"]
    if digest(candidate) != manifest["candidate_hash"] or code_identity()["source_hash"] != candidate["source_hash"]:
        raise ValueError("Frozen candidate/source identity changed")
    for path, key in ((ROOT/"scripts/adaptive_opening_study.py", "strategy_script_sha256"),
                      (ROOT/"scripts/opening_range_study.py", "opening_intents_script_sha256"),
                      (Path(__file__), "test_runner_sha256")):
        if file_hash(path) != candidate[key]:
            raise ValueError("Frozen strategy/test implementation changed")
    partition = candidate["test_partition"]
    key = digest(dict(test_partition=partition["dataset_version"]))
    # Reserve globally before reading a single test price column.
    reserve_holdout(ROOT/"data/manifests/final_tests"/f"{key}.json", dataset_version=partition["dataset_version"],
        dates=[partition["coverage"]["start"], partition["coverage"]["end"]], model_version=manifest["candidate_hash"],
        code_commit=candidate["code_commit"], config_hash=digest(candidate["configuration"]), source_hash=candidate["source_hash"])
    json_write(directory/"evaluation_state.json", dict(state="reserved; failure also consumes test", reserved_at=datetime.now(timezone.utc).isoformat()))
    actual, metadata, _ = load_dataset(partition["path"], purpose="final_test", minutes=1)
    if metadata["dataset_version"] != partition["dataset_version"]:
        raise ValueError("Frozen test partition changed")
    validation, _, _ = guarded_partition("MNQ", "validation", minutes=1)
    result, bars, intents, atr, cfg = replay(actual, candidate["parameters"], prefix=validation.iloc[-500:])
    measured = summarize(result, cfg.initial_balance, trials=1024)
    result["curve"].to_parquet(directory/"test_equity.parquet", index=False)
    result["trades"].to_parquet(directory/"test_trades.parquet", index=False)
    json_write(directory/"test_events.json", result["events"])
    stress = {}
    for factor in (1.5, 2, 3):
        stress[str(factor)] = summarize(adaptive_replay(bars, intents,
            cfg.model_copy(update={"costs": cfg.costs.scaled(factor)}), atr,
            candidate["parameters"]["multiple"], candidate["parameters"]["payoff"]), cfg.initial_balance, trials=1024)
    target = measured["net_pnl"] > 0 and measured["max_drawdown"] < 2000 and measured["max_intraday_drawdown_bound"] < 2000
    report = dict(completed_at=datetime.now(timezone.utc).isoformat(), candidate_id=CANDIDATE_ID,
        candidate_parameters=candidate["parameters"], frozen_candidate_hash=manifest["candidate_hash"],
        source_hash=candidate["source_hash"], test_dataset_version=metadata["dataset_version"],
        single_use=True, period_role="final_test", actual_instrument="MNQ", timeframe_minutes=1,
        coverage=metadata["coverage"], metrics=measured, stress=stress,
        meets_user_historical_profit_and_drawdown_target=target,
        statistically_supported=measured["uncertainty"]["mean_ci"][0] is not None and measured["uncertainty"]["mean_ci"][0] > 0,
        deployment_eligible=False, no_future_profit_or_drawdown_guarantee=True,
        original_validation_failures=candidate["unresolved_validation_checks"],
        protocol_after_evaluation="2026 market period is consumed for this candidate selection. No retuning/second candidate may be reported as an untouched 2026 test. MES prices remain unread, but correlated market information has now been observed.")
    json_write(directory/"test_results.json", report)
    json_write(ROOT/"reports/final_candidate_test.json", dict(path=str(directory), **report))
    json_write(directory/"evaluation_state.json", dict(state="completed; test consumed", completed_at=report["completed_at"]))
    print(json.dumps(dict(candidate=CANDIDATE_ID, pnl=measured["net_pnl"], drawdown=measured["max_drawdown"], intrabar_drawdown=measured["max_intraday_drawdown_bound"], meets_historical_target=target, trades=measured["trades"]), indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--evaluate")
    args = parser.parse_args()
    with threadpool_limits(limits=1):
        if args.prepare:
            prepare()
        elif args.evaluate:
            evaluate(args.evaluate)
        else:
            parser.error("Choose --prepare or --evaluate FROZEN_DIRECTORY")

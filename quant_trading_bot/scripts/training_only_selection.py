"""Select on NQ training only, freeze once, then evaluate one MNQ validation case."""
import os
for key in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"):
    os.environ[key] = "1"
import argparse
from datetime import datetime, timezone
import gc
import json
from pathlib import Path
import shutil
import pandas as pd
from threadpoolctl import threadpool_limits
import profit_drawdown_followup as execution
import neighborhood_refinement_study as cache
from quant_futures.config import digest,file_hash
from quant_futures.data import canonical
from quant_futures.dataset_catalog import resolve_dataset
from quant_futures.research import code_identity,json_write
from quant_futures.transfer import morning_indexes
from quant_futures.validation import freeze_candidate

ROOT = execution.ROOT
PARENT = ROOT/"runs/neighborhood_refinement_20261107T015835Z"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rank(row):
    """Fixed objective consuming training metrics only."""
    base,stress = row["base"],row["stress_2x"]
    years = [value for m in (base,stress) for value in m["annual_pnl"].values()]
    no_locks = not base["permanent_risk_lock"] and not stress["permanent_risk_lock"]
    positive = min(base["net_pnl"],stress["net_pnl"]) > 0
    worst_dd = max(m[key] for m in (base,stress) for key in ("max_drawdown","max_intraday_drawdown_bound"))
    qualified = no_locks and positive and worst_dd < 20000 and len(years) == 4 and min(years) > 0 and min(base["trades"],stress["trades"]) >= 60 and row["earlier_screen_net"] > 0
    # First prefer all checks, then full-period risk survival, then positive
    # economics. Compare actual NQ dollars, never relabel them as micro P&L.
    score = min(base["net_pnl"],stress["net_pnl"])/(1+worst_dd)
    return qualified,no_locks,positive,score,row["candidate_id"]


def source_paths():
    return [Path(__file__),Path(execution.__file__),Path(cache.__file__),Path(execution.engine.__file__),
        Path(cache.BASE.__file__),Path(cache.BASE.gap.__file__),Path(cache.BASE.windows_engine.__file__)]


def prepare():
    # Only reference training artifacts are opened. No prior MNQ metrics,
    # validation partition metadata or test reports feed this procedure.
    parent_protocol = read(PARENT/"protocol.json")
    if parent_protocol["followup_stage"] != "neighborhood":
        raise ValueError("Unexpected fixed pre-test protocol")
    for filename,expected in parent_protocol["script_hashes"].items():
        if file_hash(PARENT/filename) != expected:
            raise ValueError("Pre-test protocol source archive changed")
    candidates = read(PARENT/"frozen_selection.json")["selected"]
    prior = read(PARENT/"NQ_training_attempts.json")
    screens = read(PARENT/"NQ_screen_attempts.json")
    if {digest(c) for c in candidates} != {digest(row["candidate"]) for row in prior}:
        raise ValueError("Frozen reference shortlist changed")
    source = resolve_dataset("NQ:train")
    meta = read(source.with_suffix(".manifest.json"))
    if meta["split_role"] != "train" or meta["instrument"] != "NQ" or file_hash(source) != meta["dataset_version"]:
        raise PermissionError("Only verified NQ training allowed")
    folder = ROOT/"runs"/"training_only_selection_v1"
    folder.mkdir(exist_ok=False)
    protocol = dict(created_at=datetime.now(timezone.utc).isoformat(),**code_identity(),
        training_only_selection=True,validation_read_before_freeze=False,test_prices_accessed=False,
        historical_contamination="The inherited design was influenced by older validation-guided work. This run cannot undo that history or restore an independent holdout.",
        design="Use the eight candidates shortlisted from the 36-case NQ screen before the latest test evaluation. No new parameters. Exact continuous NQ 2022–2023 base and 2x-cost runs; prior 2010–2021 reference screening supplies older-history context.",
        selection_rule="Lexicographically prefer training qualification, no base/2x shutdown, positive base/2x profit, then worst-cost net divided by worst closing/intrabar drawdown, then candidate id. Qualification: positive 2010–2021 approximate NQ screen; positive 2022 and 2023 in both cost cases; >=60 trades per cost case; base/2x closing/intrabar DD <20000 actual NQ dollars; no shutdown. Freeze exactly one, even if none qualifies, as a disclosed diagnostic; never promote failure as a qualifying strategy.",
        evaluation_rule="After all training selection is complete, freeze parameters, source, training results and rank. Evaluate that one candidate on actual MNQ 2024–2025 once at base costs. No validation-driven alternatives, fitting, cost variants, ranking or retuning. Never load test data.",
        training_dataset_version=meta["dataset_version"],training_source=str(source),
        inherited_protocol_sha256=file_hash(PARENT/"protocol.json"),
        inherited_shortlist_sha256=file_hash(PARENT/"frozen_selection.json"),
        inherited_screen_sha256=file_hash(PARENT/"NQ_screen_attempts.json"),
        candidates=candidates,script_hashes={path.name:file_hash(path) for path in source_paths()})
    for path in source_paths():
        shutil.copyfile(path,folder/path.name)
    for filename in ("protocol.json","frozen_selection.json","NQ_screen_attempts.json","NQ_training_attempts.json"):
        shutil.copyfile(PARENT/filename,folder/("inherited_"+filename))
    json_write(folder/"protocol.json",protocol)
    training = canonical(pd.read_parquet(source,filters=[("timestamp_utc",">=",pd.Timestamp("2021-10-01T00:00Z"))]))
    if not training.instrument.eq("NQ").all() or not training.timestamp_utc.lt(pd.Timestamp("2024-01-01T00:00Z")).all():
        raise PermissionError("Training crossed an instrument/date boundary")
    active = morning_indexes(training)
    active = active[training.timestamp_utc.iloc[active].ge(pd.Timestamp("2022-01-01T00:00Z")).to_numpy()]
    bars = training.iloc[active].reset_index(drop=True)
    signals = {clock:execution.signals_for(training,dict(candidates[0],exit_minute=clock)).iloc[active].reset_index(drop=True)
        for clock in sorted({c["exit_minute"] for c in candidates})}
    del training
    gc.collect()
    rows = []
    for c in candidates:
        candidate_id = "train_"+digest(c)[:10]
        base_result = execution.replay(bars,signals[c["exit_minute"]],c,"NQ",retain_events=False)
        base = cache.BASE.measured(base_result,"NQ")
        old = next(r["metrics"] for r in prior if r["candidate"] == c)
        for key in ("net_pnl","max_drawdown","max_intraday_drawdown_bound","trades","permanent_risk_lock"):
            if base[key] != old[key]:
                raise ValueError("Training reproduction mismatch: "+key)
        base_result["curve"].to_parquet(folder/f"{candidate_id}_training_equity.parquet",index=False)
        base_result["trades"].to_parquet(folder/f"{candidate_id}_training_trades.parquet",index=False)
        del base_result
        stress = cache.BASE.measured(execution.replay(bars,signals[c["exit_minute"]],c,"NQ",2,retain_events=False),"NQ")
        screen = next(row for row in screens if row["candidate"] == c)
        row = dict(candidate_id=candidate_id,candidate=c,base=base,stress_2x=stress,
            earlier_screen_net=screen["earlier_2010_2021_net"])
        row["training_qualified"] = bool(rank(row)[0])
        rows.append(row)
        json_write(folder/"NQ_training_selection_attempts.json",rows)
        print(candidate_id,"NQ base",base["net_pnl"],"2x",stress["net_pnl"],"qualified",row["training_qualified"],flush=True)
        gc.collect()
    ranked = sorted(rows,key=rank,reverse=True)
    chosen = ranked[0]
    json_write(folder/"training_ranking.json",ranked)
    frozen = dict(candidate_id=chosen["candidate_id"],parameters=chosen["candidate"],
        source_hash=protocol["source_hash"],script_hashes=protocol["script_hashes"],
        training_dataset_version=meta["dataset_version"],training_qualified=chosen["training_qualified"],
        training_result=chosen,training_results_sha256=file_hash(folder/"NQ_training_selection_attempts.json"),
        training_ranking_sha256=file_hash(folder/"training_ranking.json"),
        selection_basis="NQ training only; deterministic frozen rank; no validation/test observations read by this run.",
        validation_read_before_freeze=False,test_prices_accessed=False,
        historical_contamination=protocol["historical_contamination"],
        runner_sha256=file_hash(__file__),deployment_eligible=False)
    freeze_candidate(folder/"frozen_candidate.json",frozen)
    json_write(ROOT/"reports/training_only_selection.json",dict(path=str(folder),protocol=protocol,
        selected=chosen,ranked_candidate_ids=[r["candidate_id"] for r in ranked],selection_completed=True,
        validation_read_before_freeze=False,test_prices_accessed=False))
    print(json.dumps(dict(frozen=str(folder),candidate_id=chosen["candidate_id"],training_qualified=chosen["training_qualified"],validation_opened=False)))


def evaluate():
    folder = ROOT/"runs/training_only_selection_v1"
    manifest = read(folder/"frozen_candidate.json")
    frozen = manifest["candidate"]
    if digest(frozen) != manifest["candidate_hash"] or code_identity()["source_hash"] != frozen["source_hash"]:
        raise ValueError("Frozen source/parameters changed")
    for path in source_paths():
        if file_hash(path) != frozen["script_hashes"][path.name] or file_hash(folder/path.name) != frozen["script_hashes"][path.name]:
            raise ValueError("Frozen implementation changed")
    if file_hash(folder/"training_ranking.json") != frozen["training_ranking_sha256"] or file_hash(folder/"NQ_training_selection_attempts.json") != frozen["training_results_sha256"]:
        raise ValueError("Training selection changed after freeze")
    # Exclusive reservation before reading validation prices or metrics.
    reservation = ROOT/"data/manifests/validation_once/training_only_selection_v1.json"
    reservation.parent.mkdir(parents=True,exist_ok=True)
    with reservation.open("x",encoding="utf-8") as stream:
        json.dump(dict(reserved_at=datetime.now(timezone.utc).isoformat(),candidate_hash=manifest["candidate_hash"],
            candidate_id=frozen["candidate_id"],no_tuning=True,failure_consumes_reservation=True),stream,indent=2)
    source = resolve_dataset("MNQ:validation")
    meta = read(source.with_suffix(".manifest.json"))
    bars,actual_meta,quality = cache.bounded_micro(meta["dataset_version"])
    signals = cache.cached_signals(bars,frozen["parameters"])
    bars = bars.drop(columns=["refined_side","refined_gap","refined_momentum"])
    result = execution.replay(bars,signals,frozen["parameters"],"MNQ",retain_events=False)
    metrics = cache.BASE.measured(result,"MNQ")
    result["curve"].to_parquet(folder/"validation_equity.parquet",index=False)
    result["trades"].to_parquet(folder/"validation_trades.parquet",index=False)
    checks = dict(positive_net=bool(metrics["net_pnl"] > 0),closing_drawdown_under_2000=bool(metrics["max_drawdown"] < 2000),
        intrabar_drawdown_under_2000=bool(metrics["max_intraday_drawdown_bound"] < 2000),
        no_permanent_shutdown=not metrics["permanent_risk_lock"],enough_trades=metrics["trades"] >= 100,
        positive_confidence=bool(metrics["uncertainty"]["mean_ci"][0] > 0))
    report = dict(path=str(folder),completed_at=datetime.now(timezone.utc).isoformat(),
        candidate_id=frozen["candidate_id"],candidate=frozen["parameters"],metrics=metrics,checks=checks,
        frozen_candidate_hash=manifest["candidate_hash"],training_qualified=frozen["training_qualified"],
        selection_used_validation=False,selection_used_test=False,test_prices_accessed=False,
        validation_candidates_evaluated=1,validation_cost_cases=1,validation_dataset_version=actual_meta["dataset_version"],
        validation_role="previously_reused_2024_2025_period",independent_confirmation=False,
        historical_contamination=frozen["historical_contamination"],
        no_retuning_after_validation=True,deployment_eligible=False)
    json_write(folder/"validation_result.json",report)
    json_write(ROOT/"reports/training_selected_validation.json",report)
    print(json.dumps(dict(candidate_id=report["candidate_id"],net=metrics["net_pnl"],drawdown=metrics["max_drawdown"],
        intrabar=metrics["max_intraday_drawdown_bound"],trades=metrics["trades"],checks=checks),indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare",action="store_true")
    parser.add_argument("--evaluate",action="store_true")
    args = parser.parse_args()
    with threadpool_limits(limits=1):
        if args.prepare and not args.evaluate:
            prepare()
        elif args.evaluate and not args.prepare:
            evaluate()
        else:
            parser.error("Choose exactly one of --prepare or --evaluate")

"""Disclosed second research stage: combine longer exit with larger positions."""
import os
for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"
from pathlib import Path
from datetime import datetime, timezone
import json
import shutil
import gc
import pandas as pd
from threadpoolctl import threadpool_limits
import risk_expansion_study as engine
from quant_futures.config import digest, file_hash
from quant_futures.research import json_write, code_identity
from quant_futures.transfer import guarded_partition, morning_indexes
from quant_futures.dataset_catalog import resolve_dataset
from quant_futures.data import canonical


def main():
    root = engine.ROOT
    parent = json.loads((root/"reports/latest_risk_expansion_study.json").read_text())
    if parent.get("followup_stage"):
        raise RuntimeError("This exact follow-up has already completed; do not silently repeat selection")
    folder = root/"runs"/datetime.now(timezone.utc).strftime("risk_expansion_followup_%Y%m%dT%H%M%SZ")
    folder.mkdir(exist_ok=False)
    parent_folder = Path(parent["path"])
    selected = [dict(name=engine.NAME+("_drawdown_taper" if sizing == "drawdown_taper" else ""),
        stop_points=stop, payoff=3, exit_minute=690, contracts=quantity, sizing=sizing, risk_stop=1900,
        **(dict(taper_thresholds=[400, 800]) if sizing == "drawdown_taper" else {}))
        for stop in (40, 50) for quantity in (2, 3) for sizing in ("fixed", "drawdown_taper")]
    protocol = dict(created_at=datetime.now(timezone.utc).isoformat(), **code_identity(), followup_stage=True,
        post_final_test_research=True, final_test_accessed=False, parent_path=str(parent_folder),
        parent_result_sha256=file_hash(parent_folder/"results.json"),
        design="Second exploratory stage after viewing the first risk study: combine its longer 11:30 exit with 40/50-point stops, 2/3 maximum contracts, fixed or causal 400/800-dollar drawdown taper. Eight combinations declared before these micro replays. Reuses the same 2024–2025 selection period; no independent-test claim.",
        risk_protocol="$1900 internal kill retains $100 room below the $2000 measured close/intrabar rejection ceiling. $125 times maximum-contract trade/open risk, $600 daily stop. Permanent shutdown invalidates selection. Both base and 2x-cost drawdown must stay below $2000 without permanent lock.",
        rationale="The first study improved one-contract profit with the 11:30 exit; combining that exit with larger size is additional validation-informed research. The full 2010–2023 NQ screening cache is reused with matching data identity, not re-counted as a new completed search.",
        script_hashes={Path(p).name:file_hash(p) for p in (__file__, engine.__file__, engine.gap.__file__, engine.windows_engine.__file__)},
        sources=parent["sources"], selected_candidates=selected)
    for path in (__file__, engine.__file__, engine.gap.__file__, engine.windows_engine.__file__):
        shutil.copyfile(path, folder/Path(path).name)
    json_write(folder/"protocol.json", protocol)
    json_write(folder/"frozen_selection.json", dict(frozen_at=datetime.now(timezone.utc).isoformat(), candidates=selected,
        basis="Explicit second-stage reused-validation research. Frozen before replaying these eight candidate settings."))
    source = resolve_dataset("NQ:train")
    meta = json.loads(source.with_suffix(".manifest.json").read_text())
    if meta["split_role"] != "train" or meta["instrument"] != "NQ" or file_hash(source) != parent["source_training_dataset_version"]:
        raise ValueError("Parent reference screen data identity mismatch")
    attempts = json.loads((parent_folder/"NQ_screen_attempts.json").read_text())
    json_write(folder/"reference_screen_reuse.json", dict(path=str(parent_folder/"NQ_screen_attempts.json"),
        sha256=file_hash(parent_folder/"NQ_screen_attempts.json"), cases=len(attempts), source_version=meta["dataset_version"]))
    training = canonical(pd.read_parquet(source, filters=[("timestamp_utc", ">=", pd.Timestamp("2021-10-01T00:00Z"))]))
    indexes = morning_indexes(training)
    indexes = indexes[training.timestamp_utc.iloc[indexes].ge(pd.Timestamp("2022-01-01T00:00Z")).to_numpy()]
    signals = engine.signals_for(training, dict(exit_minute=690)).iloc[indexes].reset_index(drop=True)
    reference = training.iloc[indexes].reset_index(drop=True)
    verified = {}
    for candidate in selected:
        cid = "risk_"+digest(candidate)[:10]
        verified[cid] = engine.measured(engine.replay(reference, signals, candidate, "NQ"), "NQ")
        print("Followup NQ", cid, round(verified[cid]["net_pnl"], 2), flush=True)
    json_write(folder/"NQ_event_training_verification.json", verified)
    json_write(folder/"NQ_training_attempts.json", [dict(candidate_id="risk_"+digest(candidate)[:10], candidate=candidate,
        status="completed", metrics=verified["risk_"+digest(candidate)[:10]]) for candidate in selected])
    del training, reference, signals
    gc.collect()
    bars, val_meta, quality = guarded_partition("MNQ", "validation", minutes=1)
    if val_meta["dataset_version"] != parent["validation_dataset_version"]:
        raise ValueError("Parent micro validation identity mismatch")
    warm = canonical(pd.read_parquet(resolve_dataset("MNQ:train"), filters=[("timestamp_utc", ">=", pd.Timestamp("2023-10-01T00:00Z"))]))
    indexes = morning_indexes(bars)
    signals = engine.signals_for(pd.concat([warm, bars], ignore_index=True), dict(exit_minute=690)).iloc[len(warm):].iloc[indexes].reset_index(drop=True)
    micro = bars.iloc[indexes].reset_index(drop=True)
    del bars, warm
    outcomes = []
    for candidate in selected:
        cid = "risk_"+digest(candidate)[:10]
        result = engine.replay(micro, signals, candidate, "MNQ")
        metrics = engine.measured(result, "MNQ")
        result["curve"].to_parquet(folder/f"MNQ_{cid}_validation_equity.parquet", index=False)
        result["trades"].to_parquet(folder/f"MNQ_{cid}_validation_trades.parquet", index=False)
        del result
        stress = {str(factor):engine.measured(engine.replay(micro, signals, candidate, "MNQ", factor), "MNQ") for factor in (1.5, 2, 3)}
        years = engine.annual(metrics)
        checks = dict(profitable=metrics["net_pnl"] > 0, drawdown_below_2000=metrics["max_drawdown"] < 2000,
            intrabar_drawdown_below_2000=metrics["max_intraday_drawdown_bound"] < 2000,
            no_permanent_lock=not metrics["permanent_risk_lock"], both_selection_years_positive=len(years) == 2 and all(value > 0 for value in years.values()),
            enough_trades=metrics["trades"] >= 100, stress_2x_profitable=stress["2"]["net_pnl"] > 0,
            stress_2x_drawdown=stress["2"]["max_drawdown"] < 2000 and stress["2"]["max_intraday_drawdown_bound"] < 2000,
            stress_2x_no_lock=not stress["2"]["permanent_risk_lock"])
        matching = next((row for row in attempts if row["candidate"]["stop_points"] == candidate["stop_points"] and
            row["candidate"]["payoff"] == 3 and row["candidate"]["exit_minute"] == 690 and row["candidate"]["contracts"] == candidate["contracts"]), None)
        evidence = dict(training_verified=bool(candidate["sizing"] == "fixed" and matching and matching["screen_qualified"] and not verified[cid]["permanent_risk_lock"]),
            positive_confidence=metrics["uncertainty"]["mean_ci"][0] > 0)
        row = dict(candidate_id=cid, candidate=candidate, metrics=metrics, annual_pnl=years, stress=stress, checks=checks,
            evidence_checks=evidence, selection_qualified=all(checks.values()), economic_research_qualified=all(checks.values()) and all(evidence.values()),
            independent_final_confirmation=False, deployment_eligible=False)
        outcomes.append(row)
        json_write(folder/"MNQ_validation_results.json", outcomes)
        print("Followup MNQ", candidate["stop_points"], candidate["contracts"], candidate["sizing"], "net", round(metrics["net_pnl"], 2),
            "DD", round(metrics["max_drawdown"], 2), "passes", row["selection_qualified"], flush=True)
        gc.collect()
    # Carry forward exact verified prior candidates without counting new trials.
    carried = {row["candidate_id"]:row for row in (parent["baseline"], parent["best_selected"])}
    for cid, row in carried.items():
        for suffix in ("equity", "trades"):
            filename = f"MNQ_{cid}_validation_{suffix}.parquet"
            shutil.copyfile(parent_folder/filename, folder/filename)
        outcomes.append(dict(row, reused_parent_result=True))
    json_write(folder/"MNQ_validation_results.json", outcomes)
    eligible = [row for row in outcomes if row["selection_qualified"]]
    best = max(eligible, key=lambda row:row["metrics"]["net_pnl"])
    report = dict(**protocol, path=str(folder), completed_at=datetime.now(timezone.utc).isoformat(),
        source_training_dataset_version=meta["dataset_version"], validation_dataset_version=val_meta["dataset_version"],
        calendar_verified=quality["calendar_verified"], screen_attempts=0, reused_screen_cases=len(attempts), selected_replays=len(selected),
        reused_parent_result_records=len(carried), baseline=parent["baseline"], best_selected=best,
        pnl_improvement=best["metrics"]["net_pnl"]-parent["baseline"]["metrics"]["net_pnl"], validation_results=outcomes)
    json_write(folder/"results.json", report)
    json_write(root/"reports/latest_risk_expansion_study.json", report)


if __name__ == "__main__":
    with threadpool_limits(limits=1):
        main()

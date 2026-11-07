"""Validation-informed sizing follow-up to the explicitly saved MNQ candidates."""
import os
for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"
from datetime import datetime, timezone
import argparse
from functools import partial
from pathlib import Path
import gc
import json
import shutil
import pandas as pd
from threadpoolctl import threadpool_limits
import pareto_refinement_study as engine
from quant_futures.backtest import Simulator
from quant_futures.config import digest, file_hash
from quant_futures.data import canonical, validate
from quant_futures.dataset_catalog import resolve_dataset
from quant_futures.research import code_identity, json_write
from quant_futures.transfer import guarded_partition, morning_indexes

ROOT = engine.base.ROOT


def signals_for(bars, candidate):
    return engine.base.windows_engine.intents(bars, candidate,
        windows={engine.NAME:(585, candidate["exit_minute"])},
        context_fn=engine.base.gap.context, history_value=engine.base.gap.history_value,
        side_fn=partial(engine.side_for, candidate))


def replay(bars, signals, candidate, symbol, factor=1, retain_events=True):
    cfg = engine.base.configuration(symbol, candidate, factor)
    bars, quality = validate(bars, minutes=1)
    if quality["fatal"] or len(bars) != len(signals):
        raise ValueError("Valid aligned bars required")
    sim = Simulator(cfg)
    position_key, favorable = None, 0.
    previous_quantity, requested = None, []
    scale = 10 if symbol == "NQ" else 1
    for bar, signal in zip(bars.itertuples(index=False), signals):
        prior_equity = sim.curve[-1]["equity"] if sim.curve else cfg.initial_balance
        quantity = engine.base.requested_size(candidate, max(0, sim.risk.peak-prior_equity)/scale)
        if quantity != previous_quantity:
            limits = cfg.risk.model_copy(update={"max_contracts": quantity})
            sim.cfg = cfg.model_copy(update={"risk": limits})
            sim.risk.limits = limits
            previous_quantity = quantity
        requested.append(quantity)
        if sim.position is not None and sim.previous is not None:
            p = sim.position
            if position_key != p.entry_index:
                position_key, favorable = p.entry_index, 0.
            favorable = max(favorable, p.side*(sim.previous.close-p.entry))
            proposed = sim.spec.round_price(p.entry+p.side*engine.protected_distance(candidate, favorable))
            p.stop = max(p.stop, proposed) if p.side > 0 else min(p.stop, proposed)
        else:
            position_key, favorable = None, 0.
        sim.step(bar, signal)
        if not retain_events:
            sim.broker.events.clear()
    result = sim.finish()
    result["curve"]["requested_contracts"] = requested
    result.update(permanent_risk_lock=bool(sim.risk.killed), risk_reason=sim.risk.reason)
    return result


def goal_checks(metrics, stress, annual):
    return dict(profit_above_saved=metrics["net_pnl"] > 5779.5,
        drawdown_below_saved=metrics["max_drawdown"] < 1920,
        intrabar_below_saved=metrics["max_intraday_drawdown_bound"] < 1920,
        below_user_2000_limit=metrics["max_drawdown"] < 2000 and metrics["max_intraday_drawdown_bound"] < 2000,
        full_period_without_shutdown=not metrics["permanent_risk_lock"],
        both_years_positive=len(annual) == 2 and all(value > 0 for value in annual.values()),
        enough_trades=metrics["trades"] >= 100,
        stress_2x_profitable=stress["2"]["net_pnl"] > 0,
        stress_2x_drawdown=stress["2"]["max_drawdown"] < 2000 and stress["2"]["max_intraday_drawdown_bound"] < 2000,
        stress_2x_no_lock=not stress["2"]["permanent_risk_lock"])


def main(stage="sizing"):
    raise PermissionError("Validation-guided refinement is retired: select parameters on training data only. See AGENTS.md.")
    parent = json.loads((ROOT/"reports/latest_pareto_refinement.json").read_text())
    if stage == "exits":
        parent = json.loads((ROOT/"reports/latest_profit_drawdown_followup.json").read_text())
    saved = json.loads((ROOT/"reports/saved_candidates/refine_41d93a46b7/candidate.json").read_text())["candidate"]
    lower_dd = json.loads((ROOT/"reports/saved_candidates/refine_1ea7bbf061/candidate.json").read_text())["candidate"]
    grid = [dict(saved["candidate"], risk_stop=1990),
        dict(saved["candidate"], risk_stop=1990, sizing="drawdown_taper", taper_thresholds=[400, 800]),
        dict(lower_dd["candidate"], risk_stop=1990, contracts=3),
        dict(lower_dd["candidate"], risk_stop=1990, contracts=3, sizing="drawdown_taper", taper_thresholds=[400, 800]),
        dict(lower_dd["candidate"], risk_stop=1990, contracts=3, sizing="drawdown_taper", taper_thresholds=[600, 1000]),
        dict(lower_dd["candidate"], risk_stop=1990, contracts=4, sizing="drawdown_taper", taper_thresholds=[400, 800])]
    design = "Six explicitly validation-informed settings frozen before follow-up replay: higher $1990 internal stop; fixed/tapered sizing from the saved high-profit and lower-drawdown anchors. No new entry thresholds, protection triggers or target ratios selected after these replays."
    if stage == "exits":
        grid = [dict(lower_dd["candidate"], payoff=payoff, exit_minute=exit_minute, stop_points=stop)
            for payoff, exit_minute, stop in ((4,690,40), (4,720,40), (3,720,40), (5,720,40),
                                             (3,720,50), (3,690,50), (4,720,30))]
        grid.append(dict(saved["candidate"], contracts=2, exit_minute=720))
        design = "Eight explicitly reused-validation exit/target settings, frozen after the six sizing follow-ups failed to improve the saved anchor. Fixed two-contract sizing, $1900 risk stop, 30/40/50-point stops, 3/4/5R targets and 11:30/noon exits. Original entry filters and 0.75R completed-close protection retained."
    folder = ROOT/"runs"/datetime.now(timezone.utc).strftime("profit_drawdown_followup_%Y%m%dT%H%M%SZ")
    folder.mkdir(exist_ok=False)
    protocol = dict(created_at=datetime.now(timezone.utc).isoformat(), **code_identity(),
        pareto_refinement=True, profit_drawdown_followup=True, parent_path=parent["path"],
        followup_stage=stage,
        post_final_test_research=True, final_test_accessed=False,
        user_goal="Save $5779.50 / $1920 result; seek higher net P&L with decreasing drawdown under $2000.",
        benchmark_net=5779.5, benchmark_drawdown=1920, benchmark_intrabar=1920,
        design=design,
        risk_protocol="Sizing uses preceding completed equity and peak only. Existing positions are never resized retroactively. Internal risk stop is frozen per candidate ($1990 sizing stage; $1900 exit stage); price gaps can exceed it. Report measured close and adverse-intrabar drawdown separately. Base profit/drawdown improvements and cost/evidence qualification remain separate.",
        reference_scope="Continuous NQ 2022–2023 reference verification. Earlier parent 2010–2021 screening remains context; causal taper has no new complete 2010–2021 verification.",
        sources=parent["sources"], candidates=grid,
        script_hashes={Path(p).name:file_hash(p) for p in (__file__, engine.__file__, engine.base.__file__, engine.base.gap.__file__, engine.base.windows_engine.__file__)})
    for path in (__file__, engine.__file__, engine.base.__file__, engine.base.gap.__file__, engine.base.windows_engine.__file__):
        shutil.copyfile(path, folder/Path(path).name)
    json_write(folder/"protocol.json", protocol)
    json_write(folder/"frozen_selection.json", dict(frozen_at=datetime.now(timezone.utc).isoformat(), selected=grid,
        basis="User revised the drawdown limit and saved the observed result. This is disclosed reused-validation follow-up, not independent confirmation."))
    source = resolve_dataset("NQ:train")
    meta = json.loads(source.with_suffix(".manifest.json").read_text())
    if meta["split_role"] != "train" or meta["instrument"] != "NQ" or file_hash(source) != parent["source_training_dataset_version"]:
        raise ValueError("Reference source mismatch")
    training = canonical(pd.read_parquet(source, filters=[("timestamp_utc", ">=", pd.Timestamp("2021-10-01T00:00Z"))]))
    if not training.timestamp_utc.lt(pd.Timestamp("2024-01-01T00:00Z")).all():
        raise PermissionError("Reference future observations")
    indexes = morning_indexes(training)
    indexes = indexes[training.timestamp_utc.iloc[indexes].ge(pd.Timestamp("2022-01-01T00:00Z")).to_numpy()]
    reference = training.iloc[indexes].reset_index(drop=True)
    verified = {}
    signal_cache = {}
    for candidate in grid:
        key = (candidate["gap_high"], candidate["momentum_min"], candidate["exit_minute"])
        if key not in signal_cache:
            signal_cache[key] = signals_for(training, candidate).iloc[indexes].reset_index(drop=True)
        cid = "follow_"+digest(candidate)[:10]
        verified[cid] = engine.base.measured(replay(reference, signal_cache[key], candidate, "NQ"), "NQ")
        print("Follow-up NQ", cid, round(verified[cid]["net_pnl"], 2), flush=True)
    json_write(folder/"NQ_training_attempts.json", [dict(candidate_id="follow_"+digest(c)[:10], candidate=c, status="completed", metrics=verified["follow_"+digest(c)[:10]]) for c in grid])
    del training, reference, signal_cache
    gc.collect()
    bars, val_meta, quality = guarded_partition("MNQ", "validation", minutes=1)
    if val_meta["dataset_version"] != parent["validation_dataset_version"]:
        raise ValueError("Micro source mismatch")
    warm = canonical(pd.read_parquet(resolve_dataset("MNQ:train"), filters=[("timestamp_utc", ">=", pd.Timestamp("2023-10-01T00:00Z"))]))
    combined = pd.concat([warm, bars], ignore_index=True)
    indexes = morning_indexes(bars)
    micro = bars.iloc[indexes].reset_index(drop=True)
    signal_cache = {}
    for candidate in grid:
        key = (candidate["gap_high"], candidate["momentum_min"], candidate["exit_minute"])
        if key not in signal_cache:
            signal_cache[key] = signals_for(combined, candidate).iloc[len(warm):].iloc[indexes].reset_index(drop=True)
    del warm, bars, combined
    gc.collect()
    outcomes = []
    for candidate in grid:
        cid = "follow_"+digest(candidate)[:10]
        signal = signal_cache[(candidate["gap_high"], candidate["momentum_min"], candidate["exit_minute"])]
        result = replay(micro, signal, candidate, "MNQ")
        metrics = engine.base.measured(result, "MNQ")
        result["curve"].to_parquet(folder/f"MNQ_{cid}_validation_equity.parquet", index=False)
        result["trades"].to_parquet(folder/f"MNQ_{cid}_validation_trades.parquet", index=False)
        del result
        stress = {str(factor):engine.base.measured(replay(micro, signal, candidate, "MNQ", factor), "MNQ") for factor in (1.5, 2, 3)}
        annual = engine.base.annual(metrics)
        checks = goal_checks(metrics, stress, annual)
        base_goal = all(checks[key] for key in ("profit_above_saved", "drawdown_below_saved", "intrabar_below_saved", "below_user_2000_limit", "full_period_without_shutdown"))
        evidence = dict(training_verified=False, positive_confidence=metrics["uncertainty"]["mean_ci"][0] > 0,
            reference_2022_2023_profitable=verified[cid]["net_pnl"] > 0 and not verified[cid]["permanent_risk_lock"])
        outcomes.append(dict(candidate_id=cid, candidate=candidate, metrics=metrics, annual_pnl=annual, stress=stress,
            checks=checks, evidence_checks=evidence, base_goal_met=base_goal,
            selection_qualified=all(checks.values()), economic_research_qualified=False,
            independent_final_confirmation=False, deployment_eligible=False))
        json_write(folder/"MNQ_validation_results.json", outcomes)
        print("Follow-up MNQ", cid, "net", round(metrics["net_pnl"], 2), "DD", round(metrics["max_drawdown"], 2), "base goal", base_goal, "stress checks", all(checks.values()), flush=True)
        gc.collect()
    for suffix in ("equity", "trades"):
        filename = f"MNQ_{saved['candidate_id']}_validation_{suffix}.parquet"
        shutil.copyfile(ROOT/"reports/saved_candidates"/saved["candidate_id"]/filename, folder/filename)
    winners = [row for row in outcomes if row["base_goal_met"]]
    best = max(winners, key=lambda row:row["metrics"]["net_pnl"]) if winners else saved
    outcomes.append(dict(saved, reused_parent_result=True))
    json_write(folder/"MNQ_validation_results.json", outcomes)
    report = dict(**protocol, path=str(folder), completed_at=datetime.now(timezone.utc).isoformat(),
        source_training_dataset_version=meta["dataset_version"], validation_dataset_version=val_meta["dataset_version"],
        calendar_verified=quality["calendar_verified"], screen_attempts=0, selected_replays=len(grid),
        baseline=saved, best_selected=best, goal_met=bool(winners), pnl_improvement=best["metrics"]["net_pnl"]-5779.5,
        validation_results=outcomes)
    json_write(folder/"results.json", report)
    json_write(ROOT/f"reports/{stage}_profit_drawdown_followup.json", report)
    json_write(ROOT/"reports/latest_profit_drawdown_followup.json", report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("sizing", "exits"), default="sizing")
    args = parser.parse_args()
    with threadpool_limits(limits=1):
        main(args.stage)

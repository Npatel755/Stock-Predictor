"""Frozen nearby settings, full-history reference screening, then MNQ replay."""
import os
for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"
from datetime import datetime, timezone
from pathlib import Path
import gc
import json
import shutil
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
import profit_drawdown_followup as execution
from quant_futures.config import digest, file_hash
from quant_futures.contracts import SPECS
from quant_futures.data import canonical, validate
from quant_futures.dataset_catalog import resolve_dataset
from quant_futures.execution import Action, PaperBroker
from quant_futures.research import code_identity, json_write
from quant_futures.transfer import validate_partition, morning_indexes

ROOT = execution.ROOT
BASE = execution.engine.base


def retain_session(group, features):
    selected = group.iloc[morning_indexes(group)].copy()
    selected["refined_side"] = 0 if features is None else features["side"]
    selected["refined_gap"] = np.nan if features is None else features["gap"]
    selected["refined_momentum"] = np.nan if features is None else features["momentum"]
    return selected


def cached_signals(bars, candidate):
    local = bars.timestamp_utc.dt.tz_convert("America/New_York")
    minute = (local.dt.hour*60+local.dt.minute).to_numpy()
    signal = np.full(len(bars),Action.HOLD,dtype=object)
    eligible = ((minute == 584) & bars.refined_gap.between(candidate["gap_low"],candidate["gap_high"]).to_numpy()
                & bars.refined_momentum.ge(candidate["momentum_min"]).to_numpy())
    signal[eligible & bars.refined_side.eq(1).to_numpy()] = Action.LONG
    signal[eligible & bars.refined_side.eq(-1).to_numpy()] = Action.SHORT
    signal[(minute >= candidate["exit_minute"]-1) & (minute < 1080)] = Action.EXIT
    return pd.Series(signal)


def bounded_micro(expected_version):
    source = resolve_dataset("MNQ:validation")
    metadata = json.loads(source.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    if metadata.get("split_role") != "validation" or metadata.get("instrument") != "MNQ":
        raise PermissionError("Only actual MNQ validation may be streamed")
    if metadata.get("synthetic") is not False or metadata.get("raw_contract_prices") is not True:
        raise ValueError("Actual raw-contract provenance required")
    if file_hash(source) != metadata["dataset_version"] or metadata["dataset_version"] != expected_version:
        raise ValueError("Micro source mismatch")
    warm_source = resolve_dataset("MNQ:train")
    warm_meta = json.loads(warm_source.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    if warm_meta.get("split_role") != "train" or warm_meta.get("instrument") != "MNQ" or file_hash(warm_source) != warm_meta["dataset_version"]:
        raise ValueError("Micro warmup provenance mismatch")
    warm = canonical(pd.read_parquet(warm_source,filters=[("timestamp_utc",">=",pd.Timestamp("2023-10-01T00:00Z"))]))
    if not warm.timestamp_utc.lt(pd.Timestamp("2024-01-01T00:00Z")).all():
        raise PermissionError("Warmup crossed the validation boundary")
    history = [BASE.gap.history_value(g) for _,g in warm.groupby("session_id",sort=False)]
    del warm
    chunks, previous, rows = [], None, 0
    for group in BASE.session_frames(source):
        group, quality = validate(group,minutes=1)
        validate_partition(group,metadata,quality,"MNQ","validation")
        if quality["fatal"] or group.timestamp_utc.duplicated().any() or (previous is not None and group.timestamp_utc.iloc[0] <= previous):
            raise ValueError("Invalid or unordered micro observations")
        previous = group.timestamp_utc.iloc[-1]
        rows += len(group)
        features = execution.engine.entry(BASE.gap.context(group,history))
        chunks.append(retain_session(group,features))
        history.append(BASE.gap.history_value(group))
    if rows != metadata["coverage"]["rows"]:
        raise ValueError("Incomplete streamed validation partition")
    return canonical(pd.concat(chunks,ignore_index=True)),metadata,dict(calendar_verified=False,streamed_source_rows=rows)


def screen(c, features, candidate, cfg, broker):
    """Approximate independent trade; full account replay is mandatory later."""
    if not execution.engine.passes(features, candidate):
        return None
    decision, side = features["decision"], features["side"]
    start = decision+1
    ends = np.flatnonzero((c["minute"] == candidate["exit_minute"]) & (np.arange(len(c["minute"])) > start))
    quantity = min(candidate["contracts"], int(c["volume"][decision]*cfg.execution.participation))
    if not quantity or start >= len(c["minute"]) or c["minute"][start] != 585 or not len(ends):
        return None
    end, spec = ends[0], SPECS["NQ"]
    price = broker.market_price(c["open"][start], side, "NQ")
    ids = np.arange(start, end)
    previous_closes = side*(np.r_[price, c["close"][ids[:-1]]]-price)
    favorable = np.maximum.accumulate(np.maximum(previous_closes, 0))
    distances = np.array([execution.engine.protected_distance(candidate, value) for value in favorable])
    stops = np.round((price+side*distances)/spec.tick)*spec.tick
    target = price+side*candidate["stop_points"]*candidate["payoff"]
    opening_stop = side*(c["open"][ids]-stops) <= 0
    stopped = c["low"][ids] <= stops if side > 0 else c["high"][ids] >= stops
    targeted = c["high"][ids] >= target+spec.tick if side > 0 else c["low"][ids] <= target-spec.tick
    gaps = np.diff(c["time"][start-1:end]) > 5*60*10**9
    rolls = c["contract"][ids] != c["contract"][decision]
    hits = np.flatnonzero(opening_stop | stopped | targeted | gaps | rolls)
    limit = False
    if len(hits):
        offset, bar = hits[0], ids[hits[0]]
        if rolls[offset]:
            return None
        if gaps[offset]:
            reference = c["open"][bar]
        elif opening_stop[offset] or stopped[offset]:
            reference = min(c["open"][bar], stops[offset]) if side > 0 else max(c["open"][bar], stops[offset])
        else:
            reference, limit = target, True
    else:
        reference = c["open"][end]
    exit_price = spec.round_price(reference) if limit else broker.market_price(reference, -side, "NQ")
    return dict(net_pnl=side*quantity*(exit_price-price)*spec.multiplier-2*quantity*cfg.costs.fee,
        year=c["date"].year, session=c["session"])


def checks_for(metrics, stress, annual, benchmark):
    bm = benchmark["metrics"]
    checks = dict(profit_above_saved=metrics["net_pnl"] > bm["net_pnl"],
        drawdown_below_saved=metrics["max_drawdown"] < bm["max_drawdown"],
        intrabar_below_saved=metrics["max_intraday_drawdown_bound"] < bm["max_intraday_drawdown_bound"],
        below_user_2000_limit=max(metrics["max_drawdown"], metrics["max_intraday_drawdown_bound"]) < 2000,
        full_period_without_shutdown=not metrics["permanent_risk_lock"],
        both_years_positive=len(annual) == 2 and all(value > 0 for value in annual.values()),
        enough_trades=metrics["trades"] >= 100,
        stress_2x_profitable=stress["2"]["net_pnl"] > 0,
        stress_2x_drawdown=max(stress["2"]["max_drawdown"], stress["2"]["max_intraday_drawdown_bound"]) < 2000,
        stress_2x_no_lock=not stress["2"]["permanent_risk_lock"])
    return checks


def main():
    raise PermissionError("This mixed-period runner is retired. Preserve its completed NQ training results; do not run MNQ validation tuning. See AGENTS.md.")
    parent = json.loads((ROOT/"reports/latest_profit_drawdown_followup.json").read_text())
    benchmark = json.loads((ROOT/"reports/saved_candidates/follow_cf9f62ca20/candidate.json").read_text(encoding="utf-8"))["candidate"]
    if benchmark["metrics"]["net_pnl"] != 6622 or benchmark["metrics"]["max_drawdown"] != 1386:
        raise ValueError("Declared benchmark mismatch")
    grid = [dict(benchmark["candidate"], stop_points=stop, payoff=payoff, exit_minute=clock, protection=policy)
        for stop in (25,30,35) for payoff in (3,4,5) for clock in (705,720) for policy in ("entry_075", "entry_1")]
    folder = ROOT/"runs"/datetime.now(timezone.utc).strftime("neighborhood_refinement_%Y%m%dT%H%M%SZ")
    folder.mkdir(exist_ok=False)
    paths = (__file__, execution.__file__, execution.engine.__file__, BASE.__file__, BASE.gap.__file__, BASE.windows_engine.__file__)
    protocol = dict(created_at=datetime.now(timezone.utc).isoformat(), **code_identity(),
        pareto_refinement=True, profit_drawdown_followup=True, neighborhood_refinement=True,
        followup_stage="neighborhood", parent_path=parent["path"],
        post_final_test_research=True, final_test_accessed=False,
        benchmark_net=6622, benchmark_drawdown=1386, benchmark_intrabar=1419,
        user_goal="Higher net than $6622 with lower closing/intrabar drawdown; retain disclosed alternatives below $2000.",
        design="Frozen 36-case NQ 2010–2023 independent-trade screen: two contracts; 25/30/35-point stops; 3/4/5R targets; 11:45/noon exits; prior-completed-close protection at 0.75R/1R. Fixed gap 0.1–0.6 and minimum opening momentum 0.05. Select top six reference-ranked new settings plus predeclared 25/35-point 4R/noon/0.75R anchors; reproduce the carried $6622 benchmark as an engineering parity check, without counting a new selection trial.",
        memory_protocol="Stream complete sessions before retaining morning rows, validate every micro source row and exact dataset hashes, verify cached signals against complete-session construction, and discard unused simulator event logs. Full equity/trade artifacts remain retained. Exact saved-benchmark reproduction must pass before new micro settings.",
        screening="Earlier 2010–2021 positivity and positive 2022/2023 years precede internal net/drawdown ranking. Approximate independent trades omit continuous account risk. Selected settings require full continuous NQ 2022–2023 verification before MNQ replay. This is still validation-informed neighborhood optimization on reused 2024–2025 data.",
        reference_scope="Full 2010–2023 approximate screen and continuous 2022–2023 selected-reference replay; no complete continuous 2010–2021 evidence.",
        risk_protocol="Two integer contracts, inherited fees/impact/volume participation, $1900 internal stop, no risk shutdown allowed for a full-period improvement. Strict goal needs profit >6622, close DD <1386 and intrabar DD <1419; all candidates additionally report the user's <2000 ceiling and 2x/3x cost stress. No 2026 prices.",
        sources=parent["sources"], candidates=grid,
        script_hashes={Path(p).name:file_hash(p) for p in paths})
    for path in paths:
        shutil.copyfile(path, folder/Path(path).name)
    json_write(folder/"protocol.json", protocol)
    source = resolve_dataset("NQ:train")
    meta = json.loads(source.with_suffix(".manifest.json").read_text())
    if meta["split_role"] != "train" or meta["instrument"] != "NQ" or file_hash(source) != parent["source_training_dataset_version"]:
        raise ValueError("Reference source mismatch")
    configs = [BASE.configuration("NQ", c) for c in grid]
    brokers = [PaperBroker(cfg.costs) for cfg in configs]
    outcomes, history, recent = [[] for _ in grid], [], []
    for count, group in enumerate(BASE.session_frames(source), 1):
        if not group.timestamp_utc.lt(pd.Timestamp("2024-01-01T00:00Z")).all():
            raise PermissionError("Reference source contains future observations")
        context = BASE.gap.context(group, history)
        features = execution.engine.entry(context)
        for i, candidate in enumerate(grid):
            outcome = screen(context, features, candidate, configs[i], brokers[i])
            if outcome:
                outcomes[i].append(outcome)
        if group.timestamp_utc.iloc[-1] >= pd.Timestamp("2021-10-01T00:00Z"):
            # Context is built from complete source sessions before retaining
            # morning bars, so previous regular-session features stay exact.
            recent.append(retain_session(group,features))
        history.append(BASE.gap.history_value(group))
        if count % 750 == 0:
            print("Neighborhood reference sessions", count, flush=True)
    attempts = []
    for candidate, rows in zip(grid, outcomes):
        values = [r["net_pnl"] for r in rows if r["year"] >= 2022]
        curve = np.r_[0, np.cumsum(values)]
        dd = float(np.max(np.maximum.accumulate(curve)-curve))
        years = {str(year):sum(r["net_pnl"] for r in rows if r["year"] == year) for year in (2022,2023)}
        earlier = sum(r["net_pnl"] for r in rows if r["year"] < 2022)
        sufficient = all(sum(r["year"] == year for r in rows) >= 30 for year in (2022,2023))
        internal = all(value > 0 for value in years.values()) and dd < 13860 and sufficient
        attempts.append(dict(candidate_id="near_"+digest(candidate)[:10], candidate=candidate,
            earlier_2010_2021_net=earlier, screen_years=years, screen_drawdown=dd,
            screen_net=float(curve[-1]), screen_qualified=earlier > 0 and internal,
            internal_pass=internal, score=float(curve[-1])/(1+dd)))
    attempts.sort(key=lambda r:(r["screen_qualified"],r["internal_pass"],r["score"]),reverse=True)
    json_write(folder/"NQ_screen_attempts.json", attempts)
    selected = [r["candidate"] for r in attempts if r["candidate"] != benchmark["candidate"]][:6]
    selected += [dict(benchmark["candidate"], stop_points=stop) for stop in (25,35)]
    selected = list({digest(c):c for c in selected}.values())
    json_write(folder/"frozen_selection.json", dict(frozen_at=datetime.now(timezone.utc).isoformat(), selected=selected,
        basis="Top six reference rankings plus two predeclared anchors, frozen before MNQ replay. Reused validation remains selection data."))
    del outcomes, history, configs, brokers
    reference = canonical(pd.concat(recent, ignore_index=True))
    reference = reference[reference.timestamp_utc >= pd.Timestamp("2022-01-01T00:00Z")].reset_index(drop=True)
    del recent
    signals = {}
    for candidate in selected:
        clock = candidate["exit_minute"]
        if clock not in signals:
            signals[clock] = cached_signals(reference,candidate)
    reference = reference.drop(columns=["refined_side","refined_gap","refined_momentum"])
    verified = {}
    for candidate in selected:
        cid = "near_"+digest(candidate)[:10]
        verified[cid] = BASE.measured(execution.replay(reference, signals[candidate["exit_minute"]], candidate, "NQ",retain_events=False), "NQ")
        print("Neighborhood NQ", cid, round(verified[cid]["net_pnl"],2), flush=True)
    json_write(folder/"NQ_training_attempts.json", [dict(candidate_id="near_"+digest(c)[:10],candidate=c,status="completed",metrics=verified["near_"+digest(c)[:10]]) for c in selected])
    del reference, signals
    gc.collect()
    micro, val_meta, quality = bounded_micro(parent["validation_dataset_version"])
    signals = {clock:cached_signals(micro,dict(benchmark["candidate"],exit_minute=clock))
               for clock in sorted({c["exit_minute"] for c in selected})}
    micro = micro.drop(columns=["refined_side","refined_gap","refined_momentum"])
    gc.collect()
    reproduced = execution.replay(micro,signals[720],benchmark["candidate"],"MNQ",retain_events=False)
    saved_folder = ROOT/"reports/saved_candidates"/benchmark["candidate_id"]
    for suffix,key in (("equity","curve"),("trades","trades")):
        expected = pd.read_parquet(saved_folder/f"MNQ_{benchmark['candidate_id']}_validation_{suffix}.parquet")
        pd.testing.assert_frame_equal(reproduced[key],expected)
    json_write(folder/"benchmark_reproduction.json",dict(passed=True,candidate_id=benchmark["candidate_id"],
        exact_equity_and_trade_parity=True,source_validation_rows=quality["streamed_source_rows"]))
    del reproduced,expected
    gc.collect()
    print("Exact $6622 benchmark reproduction passed",flush=True)
    results = []
    for candidate in selected:
        cid = "near_"+digest(candidate)[:10]
        signal = signals[candidate["exit_minute"]]
        result = execution.replay(micro,signal,candidate,"MNQ",retain_events=False)
        metrics = BASE.measured(result,"MNQ")
        for suffix, key in (("equity","curve"),("trades","trades")):
            result[key].to_parquet(folder/f"MNQ_{cid}_validation_{suffix}.parquet",index=False)
        del result
        stress = {str(f):BASE.measured(execution.replay(micro,signal,candidate,"MNQ",f,retain_events=False),"MNQ") for f in (1.5,2,3)}
        annual = BASE.annual(metrics)
        checks = checks_for(metrics,stress,annual,benchmark)
        goal = all(checks[k] for k in ("profit_above_saved","drawdown_below_saved","intrabar_below_saved","below_user_2000_limit","full_period_without_shutdown"))
        training = next(r for r in attempts if r["candidate"] == candidate)
        evidence = dict(training_screen_qualified=training["screen_qualified"], training_verified=False,
            reference_2022_2023_profitable=verified[cid]["net_pnl"] > 0 and not verified[cid]["permanent_risk_lock"],
            positive_confidence=metrics["uncertainty"]["mean_ci"][0] > 0)
        results.append(dict(candidate_id=cid,candidate=candidate,metrics=metrics,annual_pnl=annual,stress=stress,
            checks=checks,evidence_checks=evidence,base_goal_met=goal,selection_qualified=all(checks.values()),
            economic_research_qualified=False,independent_final_confirmation=False,deployment_eligible=False))
        json_write(folder/"MNQ_validation_results.json",results)
        print("Neighborhood MNQ",cid,"net",metrics["net_pnl"],"DD",metrics["max_drawdown"],"intrabar",metrics["max_intraday_drawdown_bound"],"goal",goal,flush=True)
        gc.collect()
    for suffix in ("equity","trades"):
        filename = f"MNQ_{benchmark['candidate_id']}_validation_{suffix}.parquet"
        shutil.copyfile(ROOT/"reports/saved_candidates"/benchmark["candidate_id"]/filename,folder/filename)
    winners = [r for r in results if r["base_goal_met"]]
    best = max(winners,key=lambda r:r["metrics"]["net_pnl"]) if winners else benchmark
    alternatives = [r["candidate_id"] for r in results if r["checks"]["profit_above_saved"] and r["checks"]["below_user_2000_limit"] and r["checks"]["full_period_without_shutdown"]]
    results.append(dict(benchmark,reused_parent_result=True))
    json_write(folder/"MNQ_validation_results.json",results)
    report = dict(**protocol,path=str(folder),completed_at=datetime.now(timezone.utc).isoformat(),
        source_training_dataset_version=meta["dataset_version"],validation_dataset_version=val_meta["dataset_version"],
        calendar_verified=quality["calendar_verified"],screen_attempts=len(attempts),selected_replays=len(selected),
        baseline=benchmark,best_selected=best,goal_met=bool(winners),pnl_improvement=best["metrics"]["net_pnl"]-6622,
        higher_profit_under_limit=alternatives,validation_results=results)
    json_write(folder/"results.json",report)
    json_write(ROOT/"reports/latest_neighborhood_refinement.json",report)


if __name__ == "__main__":
    with threadpool_limits(limits=1):
        main()

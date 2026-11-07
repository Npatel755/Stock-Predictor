"""Higher-profit risk/exit research; original 2026 final test remains excluded."""
import os
for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"
from pathlib import Path
from datetime import datetime, timezone
from functools import partial
import gc
import shutil
import json
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
import session_window_study as windows_engine
import gap_structure_study as gap
from overnight_study import session_frames
from quant_futures.transfer import trading_config, guarded_partition, morning_indexes
from quant_futures.backtest import Simulator
from quant_futures.data import canonical, validate
from quant_futures.execution import EventType
from quant_futures.metrics import summarize
from quant_futures.research import code_identity, json_write
from quant_futures.config import digest, file_hash
from quant_futures.dataset_catalog import resolve_dataset

ROOT = Path(__file__).resolve().parents[1]
NAME = "regular_gap_continuation"


def requested_size(candidate, prior_drawdown):
    maximum = candidate["contracts"]
    if candidate["sizing"] == "fixed":
        return maximum
    first, second = candidate["taper_thresholds"]
    return maximum if prior_drawdown < first else max(1, maximum-1) if prior_drawdown < second else 1


def configuration(symbol, candidate, factor=1):
    scale = 10 if symbol == "NQ" else 1
    drawdown_stop = candidate.get("risk_stop", 1800)
    if not 0 < drawdown_stop < 2000:
        raise ValueError("Research risk stop must remain below $2000")
    cfg = trading_config(symbol, candidate["stop_points"]/20, candidate["payoff"], hold=180)
    maximum = candidate["contracts"]
    # Constant conservative impact allowance based on the largest requested size.
    costs = cfg.costs.model_copy(update={"impact_ticks": .25*(maximum-1)}).scaled(factor)
    return cfg.model_copy(update={"timeframe_minutes": 1, "costs": costs,
        "execution": cfg.execution.model_copy(update={"max_gap_minutes": 5}),
        "risk": cfg.risk.model_copy(update={"max_contracts": maximum, "max_correlated_contracts": maximum,
            "max_trade_risk": 125*maximum*scale, "max_open_risk": 125*maximum*scale,
            "max_daily_loss": 600*scale, "max_drawdown": drawdown_stop*scale})})


def replay(bars, signals, candidate, symbol, factor=1):
    cfg = configuration(symbol, candidate, factor)
    bars, quality = validate(bars, minutes=1)
    if quality["fatal"] or len(bars) != len(signals):
        raise ValueError("Valid aligned real bars required")
    sim, requested = Simulator(cfg), []
    prior_quantity = None
    scale = 10 if symbol == "NQ" else 1
    for bar, signal in zip(bars.itertuples(index=False), signals):
        # Only the already completed preceding mark may set the next-bar cap.
        prior_equity = sim.curve[-1]["equity"] if sim.curve else cfg.initial_balance
        prior_dd = max(0, sim.risk.peak-prior_equity)/scale
        quantity = requested_size(candidate, prior_dd)
        if quantity != prior_quantity:
            limits = cfg.risk.model_copy(update={"max_contracts": quantity})
            sim.cfg = cfg.model_copy(update={"risk": limits})
            sim.risk.limits = limits
            prior_quantity = quantity
        requested.append(quantity)
        sim.step(bar, signal)
    result = sim.finish()
    result["curve"]["requested_contracts"] = requested
    result["permanent_risk_lock"] = bool(sim.risk.killed)
    result["risk_reason"] = sim.risk.reason
    return result


def measured(result, symbol, trials=2048):
    metrics = summarize(result, 500000 if symbol == "NQ" else 50000, trials=trials)
    metrics.update(permanent_risk_lock=result["permanent_risk_lock"], final_risk_reason=result["risk_reason"],
        maximum_filled_contracts=int(result["trades"].quantity.max()) if len(result["trades"]) else 0)
    return metrics


def signals_for(bars, candidate):
    return windows_engine.intents(bars, dict(name=NAME), windows={NAME: (585, candidate["exit_minute"])},
        context_fn=gap.context, side_fn=gap.direction, history_value=gap.history_value)


def annual(metrics):
    result = {}
    for day, value in metrics["daily_pnl"].items():
        result[day[:4]] = result.get(day[:4], 0)+value
    return result


def main():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = ROOT/"runs"/f"risk_expansion_{stamp}"
    folder.mkdir(exist_ok=False)
    protocol = dict(created_at=datetime.now(timezone.utc).isoformat(), **code_identity(),
        study="Higher-risk/exit improvement of the existing NQ-to-MNQ gap-continuation candidate",
        post_final_test_research=True, final_test_accessed=False,
        split="Original NQ 2010–2023 reference training; internal 2022–2023 ranking; actual MNQ 2024–2025 reused selection. No 2026 prices.",
        design="Entries unchanged. Screen 20/30/40/50 point stops, 2/3/4 payoff, 11:00/11:30 exit and 1/2/3 contracts. Freeze four top reference configurations plus explicit user-requested 1–4 contract anchors and six causal drawdown-taper policies before micro validation.",
        risk_protocol="One continuous account. $1800 micro risk kill, $2000 close/intrabar rejection threshold, no permanent risk lock permitted for selection. $125 per requested maximum contract trade-risk budget, $600 daily loss ceiling. Actual integer fills and prior-volume 1% participation cap. NQ budgets scale 10x with actual mini economics.",
        costs="Published per-side cash fees NQ $1.75 / MNQ $0.50 plus spread/slippage; an additional 0.25 tick per side for every maximum requested contract beyond one. 1.5x/2x/3x cost stress uses actual reruns; not scaled P&L.",
        sources=["https://support.lucidtrading.com/en/articles/11508978-approved-products-and-commissions"],
        taper="At an entry, size is determined only by preceding completed equity and its preceding high water mark. Existing positions are not resized retroactively. At the two declared drawdown thresholds reduce max size by one and then to one contract.",
        selection="Post-final-test reused-period optimization is exploratory. Rank passing micro candidates by net P&L after requiring no permanent lock, both years positive, minimum 100 trades, base and 2x-cost closing/intrabar DD below $2000, and positive 2x-cost profit. Older-history and bootstrap confidence checks remain separate; no deployment eligibility.")
    for source in (__file__, gap.__file__, windows_engine.__file__):
        shutil.copyfile(source, folder/Path(source).name)
    protocol["script_hashes"] = {Path(p).name: file_hash(p) for p in (__file__, gap.__file__, windows_engine.__file__)}
    json_write(folder/"protocol.json", protocol)
    path = resolve_dataset("NQ:train")
    meta = json.loads(path.with_suffix(".manifest.json").read_text())
    if meta["split_role"] != "train" or meta["instrument"] != "NQ" or file_hash(path) != meta["dataset_version"]:
        raise ValueError("NQ training provenance mismatch")
    exits = [dict(stop_points=stop, payoff=payoff, exit_minute=exit_clock)
        for stop in (20, 30, 40, 50) for payoff in (2, 3, 4) for exit_clock in (660, 690)]
    trades, history = [[] for _ in exits], []
    for count, group in enumerate(session_frames(path), 1):
        if not group.timestamp_utc.lt(pd.Timestamp("2024-01-01T00:00Z")).all():
            raise PermissionError("Reference training extends past 2023")
        c = gap.context(group, history)
        for index, variant in enumerate(exits):
            result = windows_engine.screen(c, dict(name=NAME, width=variant["stop_points"]/20, payoff=variant["payoff"]),
                "NQ", windows={NAME: (585, variant["exit_minute"])}, side_fn=gap.direction)
            if result:
                trades[index].append(result)
        history.append(gap.history_value(group))
        if count % 750 == 0:
            print("NQ risk/exit reference sessions", count, flush=True)
    attempts = []
    for variant, rows in zip(exits, trades):
        for quantity in (1, 2, 3):
            candidate = dict(name=NAME, **variant, contracts=quantity, sizing="fixed")
            outcomes = [row["net_pnl"]*quantity for row in rows if row["year"] >= 2022]
            curve = np.r_[0, np.cumsum(outcomes)]
            dd = float(np.max(np.maximum.accumulate(curve)-curve))
            earlier = sum(row["net_pnl"]*quantity for row in rows if row["year"] < 2022)
            years = {str(year): sum(row["net_pnl"]*quantity for row in rows if row["year"] == year) for year in (2022, 2023)}
            attempts.append(dict(candidate_id="risk_"+digest(candidate)[:10], candidate=candidate, earlier_2010_2021_net=earlier,
                screen_years=years, screen_net=float(curve[-1]), screen_drawdown=dd,
                screen_qualified=earlier > 0 and all(value > 0 for value in years.values()) and dd < 16000,
                score=float(curve[-1]) if dd < 16000 and all(value > 0 for value in years.values()) else -1e9-dd,
                approximation="Reference one-contract independent-trade outcomes scaled for preliminary size ranking only; ignores size-dependent impact/partial fills/risk stops. Full continuous event replay is mandatory."))
    attempts.sort(key=lambda row: (row["screen_qualified"], row["score"]), reverse=True)
    json_write(folder/"NQ_screen_attempts.json", attempts)
    selected = [row["candidate"] for row in attempts[:4]]
    selected += [dict(name=NAME, stop_points=40, payoff=3, exit_minute=660, contracts=q, sizing="fixed") for q in (1, 2, 3, 4)]
    selected += [dict(name=NAME+"_drawdown_taper", stop_points=40, payoff=3, exit_minute=660, contracts=q,
        sizing="drawdown_taper", taper_thresholds=thresholds) for q in (3, 4) for thresholds in ([300, 600], [400, 800], [500, 1000])]
    selected = list({digest(candidate): candidate for candidate in selected}.values())
    json_write(folder/"frozen_selection.json", dict(frozen_at=datetime.now(timezone.utc).isoformat(), candidates=selected,
        reason="Reference-only ranking plus declared sizing anchors/tapers. Frozen before actual MNQ validation access."))
    del trades
    training = canonical(pd.read_parquet(path, filters=[("timestamp_utc", ">=", pd.Timestamp("2021-10-01T00:00Z"))]))
    keep = morning_indexes(training)
    keep = keep[training.timestamp_utc.iloc[keep].ge(pd.Timestamp("2022-01-01T00:00Z")).to_numpy()]
    reference = training.iloc[keep].reset_index(drop=True)
    reference_signals = {clock: signals_for(training, dict(exit_minute=clock)).iloc[keep].reset_index(drop=True) for clock in (660, 690)}
    verified = {}
    for candidate in selected:
        cid = "risk_"+digest(candidate)[:10]
        result = replay(reference, reference_signals[candidate["exit_minute"]], candidate, "NQ")
        verified[cid] = measured(result, "NQ")
        print("Reference verified", cid, round(verified[cid]["net_pnl"], 2), "DD", round(verified[cid]["max_drawdown"], 2), flush=True)
        del result
    json_write(folder/"NQ_event_training_verification.json", verified)
    json_write(folder/"NQ_training_attempts.json", [dict(candidate_id="risk_"+digest(candidate)[:10], candidate=candidate,
        status="completed", metrics=verified["risk_"+digest(candidate)[:10]]) for candidate in selected])
    del training, reference, reference_signals
    gc.collect()
    bars, val_meta, quality = guarded_partition("MNQ", "validation", minutes=1)
    warm = canonical(pd.read_parquet(resolve_dataset("MNQ:train"), filters=[("timestamp_utc", ">=", pd.Timestamp("2023-10-01T00:00Z"))]))
    combined = pd.concat([warm, bars], ignore_index=True)
    keep = morning_indexes(bars)
    micro = bars.iloc[keep].reset_index(drop=True)
    micro_signals = {clock: signals_for(combined, dict(exit_minute=clock)).iloc[len(warm):].iloc[keep].reset_index(drop=True) for clock in (660, 690)}
    del combined, warm, bars
    outcomes = []
    for candidate in selected:
        cid = "risk_"+digest(candidate)[:10]
        signals = micro_signals[candidate["exit_minute"]]
        result = replay(micro, signals, candidate, "MNQ")
        metrics = measured(result, "MNQ")
        result["curve"].to_parquet(folder/f"MNQ_{cid}_validation_equity.parquet", index=False)
        result["trades"].to_parquet(folder/f"MNQ_{cid}_validation_trades.parquet", index=False)
        json_write(folder/f"MNQ_{cid}_event_diagnostics.json", dict(permanent_risk_lock=result["permanent_risk_lock"],
            reasons=sorted({event.get("reason") for event in result["events"] if event.get("event") in (EventType.LOCK, EventType.REJECT) and event.get("reason")})))
        del result
        stress = {}
        for factor in (1.5, 2, 3):
            stress[str(factor)] = measured(replay(micro, signals, candidate, "MNQ", factor), "MNQ")
        years = annual(metrics)
        checks = dict(profitable=metrics["net_pnl"] > 0, drawdown_below_2000=metrics["max_drawdown"] < 2000,
            intrabar_drawdown_below_2000=metrics["max_intraday_drawdown_bound"] < 2000,
            no_permanent_lock=not metrics["permanent_risk_lock"], both_selection_years_positive=len(years) == 2 and all(value > 0 for value in years.values()),
            enough_trades=metrics["trades"] >= 100, stress_2x_profitable=stress["2"]["net_pnl"] > 0,
            stress_2x_drawdown=stress["2"]["max_drawdown"] < 2000 and stress["2"]["max_intraday_drawdown_bound"] < 2000,
            stress_2x_no_lock=not stress["2"]["permanent_risk_lock"])
        matching = next((row for row in attempts if row["candidate"] == candidate), None)
        evidence = dict(training_verified=bool(matching and matching["screen_qualified"] and not verified[cid]["permanent_risk_lock"]),
            positive_confidence=metrics["uncertainty"]["mean_ci"][0] > 0)
        row = dict(candidate_id=cid, candidate=candidate, metrics=metrics, annual_pnl=years, stress=stress, checks=checks,
            evidence_checks=evidence, selection_qualified=all(checks.values()), economic_research_qualified=all(checks.values()) and all(evidence.values()),
            independent_final_confirmation=False, deployment_eligible=False)
        outcomes.append(row)
        json_write(folder/"MNQ_validation_results.json", outcomes)
        print("MNQ", candidate["sizing"], candidate["contracts"], candidate["stop_points"], candidate["payoff"], candidate["exit_minute"],
            "PnL", round(metrics["net_pnl"], 2), "DD", round(metrics["max_drawdown"], 2), "passes", row["selection_qualified"], flush=True)
        gc.collect()
    baseline = next(row for row in outcomes if row["candidate"] == dict(name=NAME, stop_points=40, payoff=3, exit_minute=660, contracts=1, sizing="fixed"))
    if not np.isclose(baseline["metrics"]["net_pnl"], 1635.5) or not np.isclose(baseline["metrics"]["max_drawdown"], 871):
        raise AssertionError("Original one-contract benchmark failed reproduction")
    eligible = [row for row in outcomes if row["selection_qualified"]]
    best = max(eligible, key=lambda row: row["metrics"]["net_pnl"]) if eligible else baseline
    report = dict(**protocol, path=str(folder), completed_at=datetime.now(timezone.utc).isoformat(),
        source_training_dataset_version=meta["dataset_version"], validation_dataset_version=val_meta["dataset_version"],
        calendar_verified=quality["calendar_verified"], screen_attempts=len(attempts), selected_replays=len(outcomes),
        baseline=baseline, best_selected=best, pnl_improvement=best["metrics"]["net_pnl"]-baseline["metrics"]["net_pnl"],
        validation_results=outcomes)
    json_write(folder/"results.json", report)
    json_write(ROOT/"reports/latest_risk_expansion_study.json", report)


if __name__ == "__main__":
    with threadpool_limits(limits=1):
        main()

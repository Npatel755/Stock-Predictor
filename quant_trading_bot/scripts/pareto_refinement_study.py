"""Seek higher profit and no worse drawdown than the frozen $4451 benchmark."""
import os
for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"
from pathlib import Path
from datetime import datetime, timezone
from functools import partial
import shutil
import gc
import json
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
import risk_expansion_study as base
from quant_futures.backtest import Simulator
from quant_futures.contracts import SPECS
from quant_futures.data import canonical, validate
from quant_futures.dataset_catalog import resolve_dataset
from quant_futures.transfer import guarded_partition, morning_indexes
from quant_futures.execution import Action, PaperBroker
from quant_futures.config import digest, file_hash
from quant_futures.research import json_write, code_identity

NAME = "gap_continuation_refined"


def entry(c):
    decisions = np.flatnonzero(c["minute"] == 584)
    if not len(decisions):
        return None
    decision = decisions[0]
    side = base.gap.direction(c, base.NAME, decision)
    if not side:
        return None
    opening = np.flatnonzero(c["minute"] == 570)[0]
    span = c["prior"]["high"]-c["prior"]["low"]
    return dict(decision=decision, side=side,
        gap=abs(c["open"][opening]-c["prior"]["close"])/span,
        momentum=abs(c["close"][decision]-c["open"][opening])/span)


def passes(features, candidate):
    return features is not None and candidate["gap_low"] <= features["gap"] <= candidate["gap_high"] and features["momentum"] >= candidate["momentum_min"]


def side_for(candidate, c, name, decision):
    features = entry(c)
    return features["side"] if passes(features, candidate) else 0


def signals_for(bars, candidate):
    return base.windows_engine.intents(bars, candidate, windows={NAME:(585, 690)},
        context_fn=base.gap.context, history_value=base.gap.history_value, side_fn=partial(side_for, candidate))


def protected_distance(candidate, favorable_distance):
    """Return stop distance from entry in the trade direction, in points."""
    risk = candidate["stop_points"]
    policy = candidate["protection"]
    if policy == "none":
        return -risk
    trigger = .75 if policy == "entry_075" else 1 if policy == "entry_1" else 1.5
    if favorable_distance < trigger*risk:
        return -risk
    if policy.startswith("entry"):
        return 1.  # Entry plus one point; not a guarantee of net breakeven under stress.
    trail = .75 if policy == "trail_075" else 1.
    return max(-risk, favorable_distance-trail*risk)


def replay(bars, signals, candidate, symbol, factor=1):
    cfg = base.configuration(symbol, candidate, factor)
    bars, quality = validate(bars, minutes=1)
    if quality["fatal"] or len(bars) != len(signals):
        raise ValueError("Valid aligned bars required")
    sim = Simulator(cfg)
    position_key, favorable = None, 0.
    for bar, signal in zip(bars.itertuples(index=False), signals):
        if sim.position is not None and sim.previous is not None:
            p = sim.position
            key = p.entry_index
            if position_key != key:
                position_key, favorable = key, 0.
            # Only the prior completed candle can tighten the current stop.
            favorable = max(favorable, p.side*(sim.previous.close-p.entry))
            distance = protected_distance(candidate, favorable)
            proposed = sim.spec.round_price(p.entry+p.side*distance)
            p.stop = max(p.stop, proposed) if p.side > 0 else min(p.stop, proposed)
        else:
            position_key, favorable = None, 0.
        sim.step(bar, signal)
    result = sim.finish()
    result.update(permanent_risk_lock=bool(sim.risk.killed), risk_reason=sim.risk.reason)
    return result


def screen(c, features, candidate, cfg, broker):
    if not passes(features, candidate):
        return None
    decision, side = features["decision"], features["side"]
    start = decision+1
    ends = np.flatnonzero((c["minute"] == 690) & (np.arange(len(c["minute"])) > start))
    quantity = min(candidate["contracts"], int(c["volume"][decision]*cfg.execution.participation))
    if not quantity or start >= len(c["minute"]) or c["minute"][start] != 585 or not len(ends):
        return None
    end, spec = ends[0], SPECS["NQ"]
    price = broker.market_price(c["open"][start], side, "NQ")
    ids = np.arange(start, end)
    prior_close_distance = side*(np.r_[price, c["close"][ids[:-1]]]-price)
    favorable = np.maximum.accumulate(np.maximum(prior_close_distance, 0))
    policy, risk = candidate["protection"], candidate["stop_points"]
    if policy == "none":
        distance = np.full(len(ids), -risk, dtype=float)
    else:
        trigger = .75 if policy == "entry_075" else 1 if policy == "entry_1" else 1.5
        tightened = np.full(len(ids), 1.) if policy.startswith("entry") else favorable-(.75 if policy == "trail_075" else 1)*risk
        distance = np.where(favorable >= trigger*risk, tightened, -risk)
    stops = np.round((price+side*distance)/spec.tick)*spec.tick
    target = price+side*risk*candidate["payoff"]
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


def main():
    root = base.ROOT
    parent = json.loads((root/"reports/latest_risk_expansion_study.json").read_text())
    benchmark = parent["best_selected"]
    if benchmark["metrics"]["net_pnl"] != 4451 or benchmark["metrics"]["max_drawdown"] != 1638:
        raise ValueError("Declared benchmark changed; prepare an explicit new protocol")
    folder = root/"runs"/datetime.now(timezone.utc).strftime("pareto_refinement_%Y%m%dT%H%M%SZ")
    folder.mkdir(exist_ok=False)
    grid = [dict(name=NAME, stop_points=40, payoff=payoff, exit_minute=690, contracts=q, sizing="fixed", risk_stop=1900,
        gap_low=low, gap_high=high, momentum_min=momentum, protection=protection)
        for low in (.1, .2) for high in (.4, .6) for momentum in (0, .05)
        for protection in ("none", "entry_075", "entry_1", "trail_075", "trail_1") for payoff in (3, 4) for q in (2, 3)]
    protocol = dict(created_at=datetime.now(timezone.utc).isoformat(), **code_identity(), pareto_refinement=True,
        post_final_test_research=True, final_test_accessed=False, parent_path=parent["path"],
        benchmark_net=4451, benchmark_drawdown=1638, benchmark_intrabar=benchmark["metrics"]["max_intraday_drawdown_bound"],
        design="Prespecified 160-case NQ 2010–2023 reference screen: stricter gap and opening-momentum filters, 5 protective-stop policies based only on prior completed closes, payoff 3/4 and 2/3 contracts. Top eight reference-ranked settings plus declared protective anchors then frozen before actual MNQ 2024–2025 replay.",
        risk_protocol="Continuous one-account replay, $1900 internal stop; user goal requires profit >4451, close DD <=1638, adverse intrabar DD <=1649, no permanent lock, positive 2024 and 2025, >=100 trades, positive 2x costs with DD <2000 and no permanent lock. Exact inherited integer fills, published fees, volume cap, size impact and risk budgets.",
        protection="No intrabar lookahead: after each completed close, move stop to entry+1 point at 0.75R/1R, or start a 0.75R/1R close-based trail at 1.5R. Stop never loosens. Entry+1 point is not a net-breakeven guarantee under stressed costs.",
        screening="Independent-trade approximate screen honors prior-volume quantity but omits continuous account risk. Mandatory full continuous reference replay for selected settings. No 2026 prices. Reused selection-period optimization cannot provide independent confirmation.",
        sources=parent["sources"], candidates=grid,
        script_hashes={Path(p).name:file_hash(p) for p in (__file__, base.__file__, base.gap.__file__, base.windows_engine.__file__)})
    for path in (__file__, base.__file__, base.gap.__file__, base.windows_engine.__file__):
        shutil.copyfile(path, folder/Path(path).name)
    json_write(folder/"protocol.json", protocol)
    source = resolve_dataset("NQ:train")
    meta = json.loads(source.with_suffix(".manifest.json").read_text())
    if meta["split_role"] != "train" or file_hash(source) != parent["source_training_dataset_version"]:
        raise ValueError("Reference source mismatch")
    configs = [base.configuration("NQ", candidate) for candidate in grid]
    brokers = [PaperBroker(cfg.costs) for cfg in configs]
    rows, history = [[] for _ in grid], []
    for count, group in enumerate(base.session_frames(source), 1):
        if not group.timestamp_utc.lt(pd.Timestamp("2024-01-01T00:00Z")).all():
            raise PermissionError("Reference includes future observations")
        c = base.gap.context(group, history)
        features = entry(c)
        for i, candidate in enumerate(grid):
            outcome = screen(c, features, candidate, configs[i], brokers[i])
            if outcome:
                rows[i].append(outcome)
        history.append(base.gap.history_value(group))
        if count % 750 == 0:
            print("Reference refinement sessions", count, flush=True)
    attempts = []
    for candidate, trades in zip(grid, rows):
        values = [row["net_pnl"] for row in trades if row["year"] >= 2022]
        curve = np.r_[0, np.cumsum(values)]
        dd = float(np.max(np.maximum.accumulate(curve)-curve))
        years = {str(year):sum(row["net_pnl"] for row in trades if row["year"] == year) for year in (2022, 2023)}
        earlier = sum(row["net_pnl"] for row in trades if row["year"] < 2022)
        sufficient = all(sum(row["year"] == year for row in trades) >= 30 for year in (2022, 2023))
        attempts.append(dict(candidate_id="refine_"+digest(candidate)[:10], candidate=candidate,
            earlier_2010_2021_net=earlier, screen_years=years, screen_drawdown=dd, screen_net=float(curve[-1]),
            screen_qualified=earlier > 0 and all(value > 0 for value in years.values()) and dd <= 16380 and sufficient,
            internal_pass=all(value > 0 for value in years.values()) and dd <= 16380 and sufficient,
            score=float(curve[-1])/(1+dd)))
    attempts.sort(key=lambda row:(row["screen_qualified"], row["internal_pass"], row["score"]), reverse=True)
    json_write(folder/"NQ_screen_attempts.json", attempts)
    selected = [row["candidate"] for row in attempts[:8]]
    selected += [dict(name=NAME, stop_points=40, payoff=3, exit_minute=690, contracts=q, sizing="fixed", risk_stop=1900,
        gap_low=.1, gap_high=.6, momentum_min=0, protection=protection)
        for q in (2, 3) for protection in ("entry_1", "trail_075", "trail_1")]
    selected = list({digest(candidate):candidate for candidate in selected}.values())
    json_write(folder/"frozen_selection.json", dict(frozen_at=datetime.now(timezone.utc).isoformat(), selected=selected,
        basis="NQ training ranking and predeclared protective anchors before actual micro validation. Reused 2024–2025 remains selection data."))
    del rows, configs, brokers
    training = canonical(pd.read_parquet(source, filters=[("timestamp_utc", ">=", pd.Timestamp("2021-10-01T00:00Z"))]))
    indexes = morning_indexes(training)
    indexes = indexes[training.timestamp_utc.iloc[indexes].ge(pd.Timestamp("2022-01-01T00:00Z")).to_numpy()]
    reference = training.iloc[indexes].reset_index(drop=True)
    verified = {}
    for candidate in selected:
        cid = "refine_"+digest(candidate)[:10]
        signal = signals_for(training, candidate).iloc[indexes].reset_index(drop=True)
        verified[cid] = base.measured(replay(reference, signal, candidate, "NQ"), "NQ")
        print("Reference verified", cid, round(verified[cid]["net_pnl"], 2), flush=True)
    json_write(folder/"NQ_event_training_verification.json", verified)
    json_write(folder/"NQ_training_attempts.json", [dict(candidate_id="refine_"+digest(candidate)[:10], candidate=candidate,
        status="completed", metrics=verified["refine_"+digest(candidate)[:10]]) for candidate in selected])
    del training, reference
    gc.collect()
    bars, val_meta, quality = guarded_partition("MNQ", "validation", minutes=1)
    if val_meta["dataset_version"] != parent["validation_dataset_version"]:
        raise ValueError("Micro source mismatch")
    warm = canonical(pd.read_parquet(resolve_dataset("MNQ:train"), filters=[("timestamp_utc", ">=", pd.Timestamp("2023-10-01T00:00Z"))]))
    combined = pd.concat([warm, bars], ignore_index=True)
    indexes = morning_indexes(bars)
    micro = bars.iloc[indexes].reset_index(drop=True)
    outcomes = []
    for candidate in selected:
        cid = "refine_"+digest(candidate)[:10]
        signal = signals_for(combined, candidate).iloc[len(warm):].iloc[indexes].reset_index(drop=True)
        result = replay(micro, signal, candidate, "MNQ")
        metrics = base.measured(result, "MNQ")
        result["curve"].to_parquet(folder/f"MNQ_{cid}_validation_equity.parquet", index=False)
        result["trades"].to_parquet(folder/f"MNQ_{cid}_validation_trades.parquet", index=False)
        del result
        stress = {str(factor):base.measured(replay(micro, signal, candidate, "MNQ", factor), "MNQ") for factor in (1.5, 2, 3)}
        years = base.annual(metrics)
        checks = dict(profit_above_4451=metrics["net_pnl"] > 4451, drawdown_no_worse=metrics["max_drawdown"] <= 1638,
            intrabar_no_worse=metrics["max_intraday_drawdown_bound"] <= protocol["benchmark_intrabar"],
            no_permanent_lock=not metrics["permanent_risk_lock"], both_selection_years_positive=len(years) == 2 and all(value > 0 for value in years.values()),
            enough_trades=metrics["trades"] >= 100, stress_2x_profitable=stress["2"]["net_pnl"] > 0,
            stress_2x_drawdown=stress["2"]["max_drawdown"] < 2000 and stress["2"]["max_intraday_drawdown_bound"] < 2000,
            stress_2x_no_lock=not stress["2"]["permanent_risk_lock"])
        training_row = next(row for row in attempts if row["candidate"] == candidate)
        evidence = dict(training_verified=training_row["screen_qualified"] and not verified[cid]["permanent_risk_lock"],
            positive_confidence=metrics["uncertainty"]["mean_ci"][0] > 0)
        outcomes.append(dict(candidate_id=cid, candidate=candidate, metrics=metrics, annual_pnl=years, stress=stress, checks=checks,
            evidence_checks=evidence, selection_qualified=all(checks.values()), economic_research_qualified=all(checks.values()) and all(evidence.values()),
            independent_final_confirmation=False, deployment_eligible=False))
        json_write(folder/"MNQ_validation_results.json", outcomes)
        print("MNQ", cid, candidate["protection"], "profit", round(metrics["net_pnl"], 2), "DD", round(metrics["max_drawdown"], 2),
            "beats goal", all(checks.values()), flush=True)
        gc.collect()
    # Preserve the exact previous best as a comparison, without a new trial count.
    for suffix in ("equity", "trades"):
        name = f"MNQ_{benchmark['candidate_id']}_validation_{suffix}.parquet"
        shutil.copyfile(Path(parent["path"])/name, folder/name)
    winners = [row for row in outcomes if row["selection_qualified"]]
    best = max(winners, key=lambda row:row["metrics"]["net_pnl"]) if winners else benchmark
    outcomes.append(dict(benchmark, reused_parent_result=True))
    json_write(folder/"MNQ_validation_results.json", outcomes)
    report = dict(**protocol, path=str(folder), completed_at=datetime.now(timezone.utc).isoformat(),
        source_training_dataset_version=meta["dataset_version"], validation_dataset_version=val_meta["dataset_version"],
        calendar_verified=quality["calendar_verified"], screen_attempts=len(attempts), selected_replays=len(selected),
        baseline=benchmark, best_selected=best, goal_met=bool(winners), pnl_improvement=best["metrics"]["net_pnl"]-4451,
        validation_results=outcomes)
    json_write(folder/"results.json", report)
    json_write(root/"reports/latest_pareto_refinement.json", report)


if __name__ == "__main__":
    with threadpool_limits(limits=1):
        main()

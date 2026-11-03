"""Reproducible staged DVS research search with chronological validation.

Historical data, including 2026, has already been inspected in this project.
The 2026 audit is retrospective and must not be described as a fresh holdout.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import random
import time

import numpy as np
import pandas as pd

from .config import StrategyConfig
from .engine import backtest
from .indicators import prepare_indicators
from .market_data import load_history, utc
from .paths import PARQUET, ROOT
from .reporting import safe_value, save_result


def baseline() -> StrategyConfig:
    return StrategyConfig(mode="research", strategy_version="v1.1", entry_timing="next_open",
                          intrabar_policy="stop_first", slippage_bps=2., swap_daily_bps=3.3)


def candidate_configs(count=256, seed=1027) -> list[dict]:
    """Fixed seed, single-variable ablations, then bounded hypothesis families."""
    base = baseline()
    configs = []
    seen = set()

    def add(label, changes):
        cfg = replace(base, **changes)
        serialized = json.dumps(asdict(cfg), sort_keys=True)
        if serialized not in seen:
            seen.add(serialized)
            configs.append({"id": len(configs), "label": label, "config": asdict(cfg)})

    add("baseline", {})
    add("cost_aware_risk", {"risk_includes_costs": True})
    choices = {
        "reward_r": [1., 1.25, 1.5, 2.5, 3., 4.],
        "breakout_rvol": [1., 1.2, 2., 2.5], "entry_rvol": [1., 1.5, 2., 2.5],
        "max_setup_bars": [12, 18, 36], "retest_atr": [.1, .4, .6], "stop_atr": [.25, .5, 1.],
        "min_stop_bps": [20., 40., 80.], "min_stop_atr": [1., 2., 3.],
        "min_reward_cost_ratio": [3., 5., 8.], "min_atr_bps": [5., 10., 15., 20.],
        "max_atr_bps": [15., 30., 50.], "min_trend_gap_bps": [25., 50., 100., 200.],
        "trade_direction": ["long", "short"], "session": ["europe_us", "us", "asia"],
        "allow_weekends": [False], "cooldown_bars": [6, 12, 24],
        "breakeven_r": [1., 1.5, 2.], "trail_atr": [2., 3., 4.],
        "max_holding_bars": [24, 48, 96, 288],
    }
    for key, values in choices.items():
        for value in values:
            if len(configs) >= count:
                return configs
            add(f"ablation_{key}_{value}", {key: value})
    rng = random.Random(seed)
    while len(configs) < count:
        family = (len(configs) % 4)
        if family == 0:  # Costs, stop geometry and reward.
            changes = dict(risk_includes_costs=True, reward_r=rng.choice([1.25, 1.5, 2., 2.5, 3.]),
                           min_stop_bps=rng.choice([0., 20., 40., 80.]), min_stop_atr=rng.choice([0., 1., 2.]),
                           stop_atr=rng.choice([.1, .25, .5]), min_reward_cost_ratio=rng.choice([0., 3., 5.]))
        elif family == 1:  # Signal quality without extra position management.
            changes = dict(breakout_rvol=rng.choice([1., 1.2, 1.5, 2.]), entry_rvol=rng.choice([1., 1.2, 1.5, 2.]),
                           max_setup_bars=rng.choice([12, 24, 36]), retest_atr=rng.choice([.1, .25, .4]),
                           min_atr_bps=rng.choice([0., 5., 10., 15.]), min_trend_gap_bps=rng.choice([0., 25., 50., 100.]),
                           reward_r=rng.choice([1.5, 2., 2.5, 3.]), risk_includes_costs=True)
        elif family == 2:  # Regimes and broad sessions, not individual cherry-picked hours.
            changes = dict(trade_direction=rng.choice(["both", "long", "short"]),
                           session=rng.choice(["all", "europe_us", "us", "asia"]),
                           allow_weekends=rng.choice([True, False]), min_stop_atr=rng.choice([0., 1., 2.]),
                           max_atr_bps=rng.choice([0., 30., 50.]), reward_r=rng.choice([1.5, 2., 2.5, 3.]),
                           cooldown_bars=rng.choice([0, 6, 12]), risk_includes_costs=True)
        else:  # Exit management; activation uses completed closes, effective next bar.
            changes = dict(breakeven_r=rng.choice([0., 1., 1.5, 2.]), trail_atr=rng.choice([0., 2., 3., 4.]),
                           max_holding_bars=rng.choice([0, 48, 96, 288]), reward_r=rng.choice([2., 2.5, 3., 4.]),
                           min_atr_bps=rng.choice([0., 5., 10.]), stop_atr=rng.choice([.1, .25, .5]),
                           risk_includes_costs=True)
        add(f"family_{family}_{len(configs)}", changes)
    return configs[:count]


def fingerprint():
    files = ["optimize.py", "config.py", "engine.py", "indicators.py", "market_data.py"]
    return {file: hashlib.sha256((ROOT / file).read_bytes()).hexdigest() for file in files}


def write_json(path, value):
    path.write_text(json.dumps(safe_value(value), indent=2, allow_nan=False), encoding="utf-8")


def pnl(metrics):
    return metrics["final_equity"] - metrics["initial_capital"]


def training_score(metrics):
    if metrics["entries"] < 25 or metrics["margin_call_events"]:
        return -1e9
    return pnl(metrics) / 100 - .5 * metrics["max_closed_equity_drawdown_usd"] / 100


def validation_score(folds):
    # Penalize a fragile negative fold, intrabar risk, and too few observations.
    if min(f["entries"] for f in folds) < 6 or sum(f["entries"] for f in folds) < 25:
        return -1e9
    if any(f["margin_call_events"] for f in folds):
        return -1e9
    returns = [pnl(f) / 100 for f in folds]
    return sum(returns) - 1.5 * max(0., -min(returns)) - .5 * max(f["max_closed_equity_drawdown_usd"] for f in folds) / 100


def subset(bars, features, start, end):
    mask = (bars.timestamp >= utc(start)) & (bars.timestamp < utc(end))
    return bars.loc[mask].reset_index(drop=True), features.loc[mask].reset_index(drop=True)


def evaluate(bars, features, config):
    return backtest(bars, StrategyConfig(**config), indicators=features, capture_details=False).metrics


def resume_rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


def append(path, row):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(safe_value(row), allow_nan=False) + "\n")
        stream.flush()


def run(args):
    args.output.mkdir(parents=True, exist_ok=True)
    candidates = candidate_configs(args.candidates, args.seed)
    plan = {"seed": args.seed, "candidate_count": len(candidates), "finalists": args.finalists,
            "source_hashes": fingerprint(), "data_sha256": hashlib.sha256(args.data.read_bytes()).hexdigest(),
            "risk_per_trade": 100, "initial_capital": 50000,
            "train": ["2023-01-01", "2025-01-01"],
            "validation_folds": [["2025-01-01", "2025-07-01"], ["2025-07-01", "2026-01-01"]],
            "audit": ["2026-01-01", "2026-10-28"],
            "selection": "training shortlist, then fixed chronological validation score; audit never reselects",
            "promotion_gate": "both validation halves positive, >=6 trades each and >=25 total, aggregate validation beats baseline",
            "warning": "2026 is a previously inspected retrospective audit; no fresh out-of-sample claim",
            "candidates": candidates}
    manifest = args.output / "manifest.json"
    if manifest.exists():
        if json.loads(manifest.read_text(encoding="utf-8")) != plan:
            raise ValueError("Resume manifest differs from code, data, or search plan; use a new output directory")
    else:
        write_json(manifest, plan)  # Freeze universe and decision rules before evaluating candidates.
    bars, quality = load_history(args.data)
    development = bars[bars.timestamp < utc("2026-01-01")].reset_index(drop=True)
    features = prepare_indicators(development)
    train_bars, train_features = subset(development, features, *plan["train"])
    training = resume_rows(args.output / "training.jsonl")
    done = {r["id"] for r in training}
    started = time.monotonic()
    for candidate in candidates:
        if candidate["id"] in done:
            continue
        metrics = evaluate(train_bars, train_features, candidate["config"])
        row = {"id": candidate["id"], "label": candidate["label"], "metrics": metrics, "score": training_score(metrics)}
        training.append(row)
        append(args.output / "training.jsonl", row)
        if len(training) % 10 == 0 or len(training) == len(candidates):
            best = max(training, key=lambda r: r["score"])
            print(f"TRAIN {len(training)}/{len(candidates)} elapsed={time.monotonic()-started:.0f}s best={best['label']} pnl=${pnl(best['metrics']):.2f}", flush=True)
    ranked = sorted(training, key=lambda r: (-r["score"], r["id"]))
    shortlist = [r["id"] for r in ranked[:args.finalists]]
    if 0 not in shortlist:
        shortlist.append(0)
    write_json(args.output / "shortlist.json", {"candidate_ids": shortlist, "selection_uses": "2023-2024 only"})
    validation = resume_rows(args.output / "validation.jsonl")
    done = {r["id"] for r in validation}
    for candidate_id in shortlist:
        if candidate_id in done:
            continue
        candidate = candidates[candidate_id]
        folds = []
        for start, end in plan["validation_folds"]:
            b, f = subset(development, features, start, end)
            folds.append(evaluate(b, f, candidate["config"]))
        row = {"id": candidate_id, "label": candidate["label"], "folds": folds, "score": validation_score(folds)}
        validation.append(row)
        append(args.output / "validation.jsonl", row)
        print(f"VALIDATION {len(validation)}/{len(shortlist)} {candidate['label']} pnl=${sum(pnl(f) for f in folds):.2f} score={row['score']:.2f}", flush=True)
    baseline_validation = next(r for r in validation if r["id"] == 0)
    winner = max(validation, key=lambda r: (r["score"], -r["id"]))
    valid = winner["score"] > -1e8 and all(pnl(f) > 0 for f in winner["folds"]) and (
        sum(pnl(f) for f in winner["folds"]) > sum(pnl(f) for f in baseline_validation["folds"]))
    selection = {"candidate": candidates[winner["id"]], "validation": winner,
                 "passed_predeclared_validation_gate": valid, "baseline_validation": baseline_validation,
                 "audit_cannot_change_selection": True}
    write_json(args.output / "selection.json", selection)
    # The decision is now frozen. Only now inspect the reused 2026 audit.
    all_features = prepare_indicators(bars[bars.timestamp < utc(plan["audit"][1])].reset_index(drop=True))
    all_bars = bars[bars.timestamp < utc(plan["audit"][1])].reset_index(drop=True)
    audit_bars, audit_features = subset(all_bars, all_features, *plan["audit"])
    audit = {}
    for name, config in [("baseline", asdict(baseline())), ("selected", candidates[winner["id"]]["config"]),
                         ("selected_slippage_stress", asdict(replace(StrategyConfig(**candidates[winner["id"]]["config"]), slippage_bps=4.)))]:
        audit[name] = evaluate(audit_bars, audit_features, config)
    write_json(args.output / "audit.json", audit)
    # Save exact replays and ledgers for the selected candidate and comparator.
    full_results = {}
    for name, config in [("baseline", baseline()), ("selected", StrategyConfig(**candidates[winner["id"]]["config"]))]:
        result = backtest(all_bars, config, indicators=all_features)
        save_result(result, args.output / name, args.data)
        full_results[name] = result.metrics
    write_json(args.output / "summary.json", {"selection": selection, "audit": audit, "full_history": full_results,
                                               "not_ready_for_funded_trading": True, "data_quality": quality})
    write_json(args.output / "candidate_config.json", candidates[winner["id"]]["config"])
    leaderboard = []
    for row in sorted(validation, key=lambda r: -r["score"]):
        train = next(r for r in training if r["id"] == row["id"])
        leaderboard.append({"id": row["id"], "label": row["label"], "train_pnl": pnl(train["metrics"]),
                            "validation_h1_pnl": pnl(row["folds"][0]), "validation_h2_pnl": pnl(row["folds"][1]),
                            "validation_trades": sum(f["entries"] for f in row["folds"]), "score": row["score"]})
    pd.DataFrame(leaderboard).to_csv(args.output / "leaderboard.csv", index=False)
    print(json.dumps(safe_value({"selected": candidates[winner["id"]]["label"], "passed_gate": valid,
                                 "validation_pnl": sum(pnl(f) for f in winner["folds"]), "audit": audit,
                                 "full_history": full_results}), indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=PARQUET)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/optimization/round1")
    parser.add_argument("--candidates", type=int, default=256)
    parser.add_argument("--finalists", type=int, default=32)
    parser.add_argument("--seed", type=int, default=1027)
    args = parser.parse_args()
    if args.candidates < 2 or args.finalists < 1:
        parser.error("Use at least two candidates and one finalist")
    run(args)

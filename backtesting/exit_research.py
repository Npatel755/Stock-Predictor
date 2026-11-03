"""Frozen v1.3 exit-management experiment on reused historical ETH data.

Uses the existing event-driven engine; never selects from the 2026 audit or
automatically replaces v1.2. Every losing candidate remains in checkpoints.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
from itertools import product
import json
from pathlib import Path

import pandas as pd

from .config import StrategyConfig
from .engine import backtest
from .indicators import prepare_indicators
from .market_data import clean_candles, load_history, utc
from .optimize import append, baseline, pnl, resume_rows, subset, write_json
from .paths import PARQUET, ROOT


def candidates(parent):
    result, seen = [], set()

    def add(label, cfg):
        key = json.dumps(asdict(cfg), sort_keys=True)
        if key not in seen:
            seen.add(key)
            result.append(dict(id=len(result), label=label, config=asdict(cfg)))

    add("saved_v1_2", parent)
    add("original_v1_1_research", baseline())
    for reward, breakeven, trailing in product([2., 3., 4.5], [0., 1., 1.5], [0., 2.]):
        add(f"rr{reward}_be{breakeven}_trail{trailing}",
            replace(parent, reward_r=reward, breakeven_r=breakeven, trail_atr=trailing))
    for trailing in [0., 2.]:
        add(f"rr4.5_be2.0_trail{trailing}", replace(parent, breakeven_r=2., trail_atr=trailing))
    for holding in [96, 288]:
        add(f"rr4.5_hold{holding}", replace(parent, max_holding_bars=holding))
    add("cost_aware_original_geometry", replace(parent, reward_r=2., stop_atr=.1, min_atr_bps=0.))
    return result


def training_score(folds):
    if min(m["entries"] for m in folds) < 10 or sum(m["entries"] for m in folds) < 100 or any(m["margin_call_events"] for m in folds):
        return -1e9
    returns = [pnl(m) for m in folds]
    return (sum(returns) - 2 * max(0., -min(returns)) - .5 * max(m["max_closed_equity_drawdown_usd"] for m in folds)) / 100


def validation_score(folds):
    if min(m["entries"] for m in folds) < 6 or sum(m["entries"] for m in folds) < 25 or any(m["margin_call_events"] for m in folds):
        return -1e9
    returns = [pnl(m) for m in folds]
    return (sum(returns) - 2 * max(0., -min(returns)) - .5 * max(m["max_closed_equity_drawdown_usd"] for m in folds)) / 100


def passes_gate(train, validation, parent_train, parent_validation):
    """A change must survive old regimes and both reused validation halves."""
    return (training_score(train) > -1e8 and validation_score(validation) > -1e8
            and sum(pnl(m) > 0 for m in train) >= 4
            and min(pnl(m) for m in train) >= min(pnl(m) for m in parent_train)
            and sum(pnl(m) for m in train) >= sum(pnl(m) for m in parent_train)
            and all(pnl(m) > 0 for m in validation)
            and sum(pnl(m) for m in validation) > sum(pnl(m) for m in parent_validation))


def freeze(path, plan):
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != plan:
            raise ValueError("Experiment manifest differs; choose a new output directory")
    else:
        write_json(path, plan)


def run(args):
    from .generalization_policy import assert_search_allowed
    assert_search_allowed(ROOT)
    args.output.mkdir(parents=True, exist_ok=True)
    parent_path = args.output / "parent_config.json"
    if not parent_path.exists():
        parent_path.write_bytes(args.parent.read_bytes())
    parent = StrategyConfig(**json.loads(parent_path.read_text(encoding="utf-8")))
    universe = candidates(parent)
    earlier = ROOT / "data/ethusd/perpetual_2020_2022/candles.parquet"
    plan = dict(name="v1.3 exit-management research", candidates=universe,
                training=[[f"{y}-01-01", f"{y+1}-01-01"] for y in range(2020, 2025)],
                validation=[["2025-01-01", "2025-07-01"], ["2025-07-01", "2026-01-01"]],
                audit=["2026-01-01", "2026-10-28"], finalists=args.finalists,
                dataset_hashes={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [earlier, args.data]},
                source_hashes={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                               for name in ["exit_research.py", "config.py", "engine.py", "indicators.py", "market_data.py", "optimize.py"]},
                parent_sha256=hashlib.sha256(parent_path.read_bytes()).hexdigest(),
                prior_search_slots=384,
                selection="Train shortlist; prefer gate-eligible changed candidate by 2025 score. Otherwise retain best changed candidate as unpromoted research. Tie: lower ID.",
                gate="At least four positive training years; training sum and worst year >= parent; both 2025 halves positive; 2025 sum > parent; trade-count/margin eligibility; continuous 2025 positive at 4bp extra slippage.",
                warning="All years have been inspected. 2020-2022 now become development data after failed transfer; 2025 selection is reused; 2026 audit is retrospective, not independent validation.",
                invariant="Risk $100, capital $50,000, max leverage 5x, same research execution costs; no live orders; v1.2 never overwritten.")
    freeze(args.output / "manifest.json", plan)
    old, _ = load_history(earlier)
    new, _ = load_history(args.data)
    bars, quality = clean_candles(pd.concat([old, new[new.timestamp < utc(plan["audit"][1])]], ignore_index=True))
    if quality["missing_bars"]:
        raise ValueError("This experiment requires complete candles; gaps cannot be silently skipped")
    features = prepare_indicators(bars)
    train_windows = [subset(bars, features, *window) for window in plan["training"]]
    training = resume_rows(args.output / "training.jsonl")
    done = {row["id"] for row in training}
    for candidate in universe:
        if candidate["id"] in done:
            continue
        cfg = StrategyConfig(**candidate["config"])
        folds = [backtest(b, cfg, indicators=f, capture_details=False).metrics for b, f in train_windows]
        row = dict(id=candidate["id"], label=candidate["label"], folds=folds, score=training_score(folds))
        training.append(row)
        append(args.output / "training.jsonl", row)
        print(f"TRAIN {len(training)}/{len(universe)} {row['label']} years={[round(pnl(m), 2) for m in folds]} score={row['score']:.2f}", flush=True)
    ranked = sorted(training, key=lambda row: (-row["score"], row["id"]))
    ids = [row["id"] for row in ranked if row["id"] not in {0, 1}][:args.finalists]
    ids = list(dict.fromkeys(ids + [0, 1]))
    write_json(args.output / "shortlist.json", dict(candidate_ids=ids, selection_uses="2020-2024 only"))
    validation = resume_rows(args.output / "validation.jsonl")
    done = {row["id"] for row in validation}
    for candidate_id in ids:
        if candidate_id in done:
            continue
        candidate = universe[candidate_id]
        cfg = StrategyConfig(**candidate["config"])
        folds = []
        for window in plan["validation"]:
            b, f = subset(bars, features, *window)
            folds.append(backtest(b, cfg, indicators=f, capture_details=False).metrics)
        row = dict(id=candidate_id, label=candidate["label"], folds=folds, score=validation_score(folds))
        validation.append(row)
        append(args.output / "validation.jsonl", row)
        print(f"VALIDATION {row['label']} halves={[round(pnl(m), 2) for m in folds]}", flush=True)
    parent_train = next(row for row in training if row["id"] == 0)
    parent_valid = next(row for row in validation if row["id"] == 0)
    changed = [row for row in validation if row["id"] not in {0, 1}]
    train_by_id = {row["id"]: row for row in training}
    eligible = [row for row in changed if passes_gate(train_by_id[row["id"]]["folds"], row["folds"], parent_train["folds"], parent_valid["folds"])]
    winner = max(eligible or changed, key=lambda row: (row["score"], -row["id"]))
    selected = universe[winner["id"]]
    cfg = StrategyConfig(**selected["config"])
    b, f = subset(bars, features, "2025-01-01", "2026-01-01")
    stress = backtest(b, replace(cfg, slippage_bps=4.), indicators=f, capture_details=False).metrics
    selection = dict(candidate=selected, validation=winner, training=train_by_id[winner["id"]],
                     passed_predeclared_validation_gate=bool(eligible) and pnl(stress) > 0,
                     eligible_before_stress=len(eligible), stress_2025_4bp=stress,
                     audit_cannot_change_selection=True, ready_for_funded_trading=False)
    freeze(args.output / "selection.json", selection)
    evaluation = {}
    for name, config in [("parent_v1_2", parent), ("candidate_v1_3", cfg)]:
        evaluation[name] = {}
        for label, window in [("audit_2026", plan["audit"]), ("continuous_2020_2026", ["2020-01-01", plan["audit"][1]]),
                              ("recent_october", ["2026-10-11", plan["audit"][1]])]:
            b, f = subset(bars, features, *window)
            result = backtest(b, config, indicators=f, capture_details=False)
            directory = args.output / name / label
            directory.mkdir(parents=True, exist_ok=True)
            write_json(directory / "metrics.json", result.metrics)
            result.trades.to_csv(directory / "trades.csv", index=False)
            evaluation[name][label] = result.metrics
            print(f"AUDIT {name} {label}: ${pnl(result.metrics):.2f}", flush=True)
    summary = dict(selection=selection, evaluation=evaluation, quality=quality, not_independent_validation=True)
    write_json(args.output / "summary.json", summary)
    leaderboard = []
    for row in ranked:
        item = dict(id=row["id"], label=row["label"], training_score=row["score"])
        item.update({f"pnl_{year}": pnl(m) for year, m in zip(range(2020, 2025), row["folds"])})
        valid = next((r for r in validation if r["id"] == row["id"]), None)
        if valid:
            item.update(validation_h1=pnl(valid["folds"][0]), validation_h2=pnl(valid["folds"][1]))
        leaderboard.append(item)
    pd.DataFrame(leaderboard).to_csv(args.output / "leaderboard.csv", index=False)
    lines = ["# v1.3 exit-management experiment", "", plan["warning"], "",
             f"Tested {len(universe)} fixed configurations; shortlisted {len(ids)-2} changed configurations using 2020–2024. Selected **{selected['label']}** before the 2026 audit.", "",
             f"Historical promotion gate passed: **{selection['passed_predeclared_validation_gate']}**. This is not readiness for funded trading.", "",
             "| Period / execution | Saved v1.2 | Candidate v1.3 |", "| --- | ---: | ---: |"]
    chosen_train = train_by_id[winner["id"]]
    for year, p, s in zip(range(2020, 2025), parent_train["folds"], chosen_train["folds"]):
        lines.append(f"| {year}, independent account | ${pnl(p):,.2f} | ${pnl(s):,.2f} |")
    for half, p, s in zip(["2025 H1", "2025 H2"], parent_valid["folds"], winner["folds"]):
        lines.append(f"| {half}, independent account | ${pnl(p):,.2f} | ${pnl(s):,.2f} |")
    for label in ["audit_2026", "continuous_2020_2026", "recent_october"]:
        lines.append(f"| {label} | ${pnl(evaluation['parent_v1_2'][label]):,.2f} | ${pnl(evaluation['candidate_v1_3'][label]):,.2f} |")
    lines.extend(["", f"Selected continuous 2025 with 4bp extra slippage: ${pnl(stress):,.2f}.", "",
                  "Annual and half-year rows start new accounts with causal indicator warm-up. Continuous replay is a separate account; fold sums are not its achieved P&L. Research execution includes next-open entries, fees, two ticks plus basis-point slippage, financing and stop-first handling. All configurations keep the same $100 planned risk and 5x maximum leverage. Stops tighten only after completed bars. Open positions remain marked at endpoints.", "",
                  "The recent October diagnostic was run after selection and cannot select parameters. It ends October 28 exclusive; missing later days are not fabricated. Earlier-regime data is now development data, so its results cannot be called an untouched transfer test. All candidates, negative results, source/data hashes and frozen selection remain in the artifact directory. No v1.2 file is overwritten and no orders are sent.", ""])
    report = "\n".join(lines)
    (args.output / "report.md").write_text(report, encoding="utf-8")
    (ROOT / "reports/v1_3_exit_research.md").write_text(report, encoding="utf-8")
    print(f"FINISHED selected={selected['label']} historical_gate={selection['passed_predeclared_validation_gate']}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=Path, default=ROOT / "configs/dvs_eth_v1_2.json")
    parser.add_argument("--data", type=Path, default=PARQUET)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/optimization/round3_v1_3_exits")
    parser.add_argument("--finalists", type=int, default=6)
    args = parser.parse_args()
    if args.finalists < 1:
        parser.error("At least one changed finalist is required")
    run(args)

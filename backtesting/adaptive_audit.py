"""Quarterly causal allocation diagnostic across frozen DVS variants and cash.

This is a historical rule replay. Candidate discovery already used later data;
it is not independent walk-forward model validation or a live trading system.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .config import StrategyConfig
from .engine import Broker, Position, backtest
from .indicators import prepare_indicators
from .market_data import BAR, clean_candles, load_history, utc
from .optimize import baseline, subset, write_json
from .paths import ROOT, PARQUET


def trailing_evidence(equity, trades, boundary, months=12):
    """Score only marks and exits strictly available by the quarter boundary."""
    boundary = utc(boundary)
    start = boundary - pd.DateOffset(months=months)
    times = pd.to_datetime(equity.timestamp, utc=True)
    marks = equity.loc[(times > start) & (times <= boundary)].copy()
    earlier = equity.loc[times <= start]
    if earlier.empty or marks.empty:
        return {"eligible": False, "reason": "insufficient_prior_history", "score": None}
    anchor = float(earlier.equity.iloc[-1])
    exits = pd.to_datetime(trades.exit_time, utc=True) if len(trades) else pd.Series(dtype="datetime64[ns, UTC]")
    count = int(((exits > start) & (exits <= boundary)).sum())
    midpoint = start + (boundary - start) / 2
    first = marks[pd.to_datetime(marks.timestamp, utc=True) <= midpoint]
    if first.empty:
        return {"eligible": False, "reason": "insufficient_half_history", "score": None}
    first_profit = float(first.equity.iloc[-1]) - anchor
    second_profit = float(marks.equity.iloc[-1] - first.equity.iloc[-1])
    running_peak = np.maximum.accumulate(np.r_[anchor, marks.equity.to_numpy()])[1:]
    drawdown = float(np.max(running_peak - marks.intrabar_worst_equity.to_numpy()))
    eligible = count >= 20 and first_profit > 0 and second_profit > 0
    return {"eligible": eligible, "score": first_profit + second_profit - .5 * drawdown if eligible else None,
            "first_half_pnl": first_profit, "second_half_pnl": second_profit, "closed_legs": count,
            "drawdown_usd": drawdown, "lookback_start": str(start), "information_cutoff": str(boundary)}


def choose(evidence):
    eligible = [(name, row) for name, row in evidence.items() if row["eligible"] and row["score"] > 0]
    return max(eligible, key=lambda item: (item[1]["score"], item[0]))[0] if eligible else "cash"


def close_at_boundary(result, bars, cfg):
    """Scheduled quarter-end liquidation; includes market slippage/commission.

    Uses the same Broker implementation; no future gap knowledge is needed.
    The next quarter's allocation is computed only at/after this close.
    """
    if result.metrics["open_position"] is None:
        return result
    broker = Broker(cfg)
    broker.cash = result.metrics["final_cash"]
    broker.position = Position(**result.metrics["open_position"])
    broker.exit(float(bars.close.iloc[-1]), bars.timestamp.iloc[-1], "scheduled_rebalance", "research_close")
    result.trades = pd.concat([result.trades, pd.DataFrame(broker.trades)], ignore_index=True)
    result.events = pd.concat([result.events, pd.DataFrame(broker.events)], ignore_index=True)
    i = result.equity.index[-1]
    result.equity.loc[i, ["cash", "equity", "position_qty"]] = [broker.cash, broker.cash, 0.]
    result.equity.loc[i, "intrabar_worst_equity"] = min(result.equity.loc[i, "intrabar_worst_equity"], broker.cash)
    result.metrics.update(final_cash=broker.cash, final_equity=broker.cash, open_position=None,
                          net_return=broker.cash / cfg.initial_capital - 1,
                          closed_trade_legs=len(result.trades),
                          total_commission=result.metrics["total_commission"] + broker.total_commission)
    return result


def run(args):
    args.output.mkdir(parents=True, exist_ok=True)
    config_paths = {"first_v1_2": ROOT / "artifacts/optimization/round2_v1_2_neighborhood/parent_config.json",
                    "refined_v1_2": ROOT / "artifacts/optimization/round2_v1_2_neighborhood/candidate_config.json"}
    configs = {"baseline": asdict(baseline()), **{name: json.loads(path.read_text(encoding="utf-8")) for name, path in config_paths.items()}}
    early = ROOT / "data/ethusd/perpetual_2020_2022/candles.parquet"
    plan = {"name": "Quarterly trailing-performance allocation audit", "candidate_configs": configs,
            "lookback_months": 12, "minimum_closed_legs": 20,
            "eligibility": "both chronological lookback halves positive, score=net minus half modeled intrabar drawdown > 0; otherwise cash",
            "evaluation_start": "2022-01-01", "end_exclusive": "2026-10-28", "rebalance": "UTC calendar quarters",
            "liquidation": "scheduled market close on last candle of each evaluation quarter with fees/slippage; discard setup state",
            "risk": "$100 planned per entry, capital carried across quarters, cash alternative earns zero",
            "data_hashes": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [early, PARQUET]},
            "source_hashes": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                              for name in ["engine.py", "config.py", "indicators.py", "adaptive_audit.py"]},
            "selection_bias": "Frozen candidates were discovered using 2023-2025 data. Causal allocation is not independent validation. No profile is overwritten."}
    manifest = args.output / "adaptive_manifest.json"
    if manifest.exists() and json.loads(manifest.read_text(encoding="utf-8")) != plan:
        raise ValueError("Adaptive protocol differs; use another directory")
    write_json(manifest, plan)
    old, _ = load_history(early)
    recent, _ = load_history(PARQUET)
    bars, quality = clean_candles(pd.concat([old, recent[recent.timestamp < utc(plan["end_exclusive"])]]))
    if quality["missing_bars"]:
        raise ValueError("Adaptive comparison requires complete history")
    features = prepare_indicators(bars)
    shadows = {}
    for name, config in configs.items():
        result = backtest(bars, StrategyConfig(**config), indicators=features)
        shadows[name] = result
        result.equity.to_parquet(args.output / f"shadow_{name}_equity.parquet", index=False)
        result.trades.to_parquet(args.output / f"shadow_{name}_trades.parquet", index=False)
        print(f"SHADOW {name} total_net=${result.metrics['final_equity']-50000:.2f}", flush=True)
    boundaries = list(pd.date_range(plan["evaluation_start"], plan["end_exclusive"], freq="QS", tz="UTC"))
    boundaries.append(utc(plan["end_exclusive"]))
    windows, curves, ledgers, cash = [], [], [], 50000.
    for start, end in zip(boundaries, boundaries[1:]):
        evidence = {name: trailing_evidence(r.equity, r.trades, start) for name, r in shadows.items()}
        allocation = choose(evidence)
        b, f = subset(bars, features, start, end)
        before = cash
        if allocation == "cash":
            curve = pd.DataFrame({"timestamp": b.timestamp + BAR, "equity": cash, "cash": cash,
                                  "intrabar_worst_equity": cash, "position_qty": 0.})
            trades = pd.DataFrame()
        else:
            cfg = StrategyConfig(**{**configs[allocation], "initial_capital": cash})
            result = close_at_boundary(backtest(b, cfg, indicators=f), b, cfg)
            cash = result.metrics["final_cash"]
            curve, trades = result.equity, result.trades
            if len(trades):
                trades = trades.copy()
                trades["allocation"] = allocation
                ledgers.append(trades)
        curves.append(curve)
        windows.append({"start": str(start), "end_exclusive": str(end), "allocation": allocation,
                        "pnl": cash - before, "closed_legs": len(trades), "evidence": evidence})
        write_json(args.output / "allocation_decisions.json", windows)
        print(f"ALLOCATION {start.date()} {allocation} pnl=${cash-before:.2f}", flush=True)
    curve = pd.concat(curves, ignore_index=True)
    trades = pd.concat(ledgers, ignore_index=True) if ledgers else pd.DataFrame()
    peak = np.maximum.accumulate(np.r_[50000., curve.equity.to_numpy()])[1:]
    dd = (peak - curve.intrabar_worst_equity.to_numpy()) / peak
    comparisons = {"adaptive": {"net_pnl": cash - 50000., "closed_legs": len(trades), "max_intrabar_drawdown": float(dd.max()),
                                "cash_quarters": sum(w["allocation"] == "cash" for w in windows), "quarters": len(windows)}}
    # Fixed comparators start on the same 2022 evaluation date with $50,000.
    b, f = subset(bars, features, plan["evaluation_start"], plan["end_exclusive"])
    for name, config in configs.items():
        result = backtest(b, StrategyConfig(**config), indicators=f, capture_details=False)
        m = result.metrics
        comparisons[name] = {"net_pnl": m["final_equity"] - 50000., "closed_legs": m["closed_trade_legs"], "max_intrabar_drawdown": m["max_intrabar_drawdown"]}
    curve.to_parquet(args.output / "adaptive_equity.parquet", index=False)
    trades.to_csv(args.output / "adaptive_trades.csv", index=False)
    write_json(args.output / "adaptive_summary.json", {"comparisons": comparisons, "decisions": windows,
                                                       "selection_unchanged": True, "not_independent_validation": True})
    rows = [f"| {name} | ${m['net_pnl']:,.2f} | {m['closed_legs']} | {m['max_intrabar_drawdown']:.2%} |" for name, m in comparisons.items()]
    report = f"""# Causal quarterly allocation diagnostic

The allocation rule was fixed before this run. It scores only marks/exits available at each UTC quarter boundary, using the preceding 12 months. It requires at least 20 closed legs and profit in both chronological halves, then chooses the best score (net less half drawdown), or cash if none qualifies.

**This is not independent walk-forward validation.** The candidate configurations were previously discovered using later 2023–2025 observations. Causality in allocation does not erase that candidate-selection bias. No strategy profile was overwritten.

| Scenario, 2022-01-01 to 2026-10-28 exclusive | Net P&L | Closed legs | Running-peak intrabar drawdown |
| --- | ---: | ---: | ---: |
{chr(10).join(rows)}

Adaptive cash quarters: {comparisons['adaptive']['cash_quarters']} of {len(windows)}. Cash earns zero. Every comparator retains $100 planned risk. The adaptive strategy closes at scheduled quarter boundaries with commissions/slippage and resets setup state; fixed comparators run continuously. These differences are disclosed rather than hidden.

The complete decisions, their historical evidence, shadow ledgers, realized adaptive ledger, equity marks and source/data hashes are saved under `artifacts/optimization/adaptive_trailing_audit/`. A cash-heavy result is reduced exposure, not proof of stronger entry signals. No live orders or future observations are included.
"""
    (args.output / "report.md").write_text(report, encoding="utf-8")
    (ROOT / "reports/strategy_adaptive_audit.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/optimization/adaptive_trailing_audit")
    run(parser.parse_args())

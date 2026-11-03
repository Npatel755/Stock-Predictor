"""Post-selection robustness diagnostics; never reselects the candidate."""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .config import StrategyConfig
from .engine import backtest
from .indicators import prepare_indicators
from .market_data import load_history, utc
from .optimize import baseline, evaluate, pnl, subset, write_json
from .paths import PARQUET, ROOT
from .reporting import save_result


def daily_pnl(result):
    curve = result.equity
    # 00:00 is the preceding candle's close, not the next trading day's P&L.
    days = (pd.to_datetime(curve.timestamp, utc=True) - pd.Timedelta(nanoseconds=1)).dt.floor("D")
    closes = pd.Series(curve.equity.to_numpy(), index=days).groupby(level=0).last()
    changes = closes.diff()
    changes.iloc[0] = closes.iloc[0] - result.metrics["initial_capital"]
    return changes


def paired_week_bootstrap(candidate, comparator, samples=10000, seed=1027):
    pair = pd.concat([candidate.rename("candidate"), comparator.rename("baseline")], axis=1, sort=True)
    if pair.isna().any().any() or pair.empty:
        raise ValueError("Paired uncertainty estimates require matching complete daily series")
    delta = pair.candidate - pair.baseline
    # Circular moving seven-day blocks, trimmed to the original day count.
    # Aggregating a short final block and resampling it as a full block would
    # vary the observation horizon across replicates (365 is not divisible by 7).
    values = delta.to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    block_count = int(np.ceil(len(values) / 7))
    starts = rng.integers(0, len(values), size=(samples, block_count))
    indices = ((starts[:, :, None] + np.arange(7)) % len(values)).reshape(samples, -1)[:, :len(values)]
    draws = values[indices].sum(axis=1)
    return {"paired_net_pnl_difference": float(delta.sum()), "conditional_95pct_interval": np.quantile(draws, [.025, .975]).tolist(),
            "fraction_resamples_positive": float((draws > 0).mean()), "days": len(delta), "blocks": block_count,
            "method": "paired circular moving seven-day block bootstrap, trimmed to original day count, conditional on selected strategy",
            "limitations": "Does not correct the selection bias from searching many candidates; not a future-profit probability"}


def analyze(directory: Path, data_path=PARQUET):
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    for name, digest in manifest["source_hashes"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Experiment implementation changed; analyze with the recorded version")
    if hashlib.sha256(Path(data_path).read_bytes()).hexdigest() != manifest["data_sha256"]:
        raise ValueError("Dataset differs from frozen experiment")
    selected = StrategyConfig(**summary["selection"]["candidate"]["config"])
    bars, _ = load_history(data_path)
    bars = bars[bars.timestamp < utc("2026-10-28")].reset_index(drop=True)
    indicators = prepare_indicators(bars)
    comparisons = {}
    for label, start, end in [("validation_2025", "2025-01-01", "2026-01-01"),
                              ("retrospective_audit_2026", "2026-01-01", "2026-10-28")]:
        b, f = subset(bars, indicators, start, end)
        replays = {}
        for name, cfg in [("baseline", baseline()), ("selected", selected)]:
            result = backtest(b, cfg, indicators=f)
            save_result(result, directory / "robustness" / label / name, data_path)
            replays[name] = result
        comparisons[label] = {"baseline": replays["baseline"].metrics, "selected": replays["selected"].metrics,
                              "conditional_paired_bootstrap": paired_week_bootstrap(daily_pnl(replays["selected"]), daily_pnl(replays["baseline"]))}
    sensitivity = []
    for bps in [0., 1., 2., 4., 8.]:
        b, f = subset(bars, indicators, "2025-01-01", "2026-01-01")
        for name, cfg in [("baseline", baseline()), ("selected", selected)]:
            metrics = evaluate(b, f, asdict(replace(cfg, slippage_bps=bps)))
            sensitivity.append({"scenario": name, "slippage_bps_per_market_side": bps, "validation_net_pnl": pnl(metrics),
                                "entries": metrics["entries"], "max_drawdown": metrics["max_closed_equity_drawdown_usd"]})
    neighborhoods = []
    neighbors = [("selected", selected)]
    for key in ["reward_r", "breakout_rvol", "entry_rvol", "min_stop_bps", "min_stop_atr", "stop_atr", "min_atr_bps"]:
        value = getattr(selected, key)
        if not value:
            continue
        for factor in [.8, 1.2]:
            proposal = value * factor
            if key == "reward_r":
                proposal = max(1., proposal)
            neighbors.append((f"{key}_x{factor}", replace(selected, **{key: proposal})))
    b, f = subset(bars, indicators, "2023-01-01", "2026-01-01")
    for name, cfg in neighbors:
        metrics = evaluate(b, f, asdict(cfg))
        neighborhoods.append({"perturbation": name, "development_net_pnl": pnl(metrics), "entries": metrics["entries"],
                              "max_drawdown": metrics["max_closed_equity_drawdown_usd"]})
    result = {"chronological_comparisons": comparisons, "slippage_sensitivity_2025": sensitivity,
              "development_parameter_neighborhood": neighborhoods, "selection_unchanged": asdict(selected),
              "all_history_was_previously_inspected": True}
    write_json(directory / "robustness.json", result)
    pd.DataFrame(sensitivity).to_csv(directory / "slippage_sensitivity.csv", index=False)
    pd.DataFrame(neighborhoods).to_csv(directory / "parameter_neighborhood.csv", index=False)
    gate = summary["selection"]["passed_predeclared_validation_gate"]
    rows = []
    for label, values in comparisons.items():
        for name in ["baseline", "selected"]:
            m = values[name]
            rows.append(f"| {label} | {name} | ${pnl(m):,.2f} | {m['entries']} | {m['win_rate']:.1%} | ${m['max_closed_equity_drawdown_usd']:,.2f} |")
    folds = summary["selection"]["validation"]["folds"]
    differences = {key: value for key, value in asdict(selected).items() if value != asdict(baseline())[key]}
    report = f"""# DVS strategy improvement experiment: {directory.name}

Evaluated {manifest['candidate_count']} predetermined candidates on 2023–2024; validated the training shortlist on two halves of 2025. The 2026 period is an already-inspected retrospective audit, **not a fresh holdout**.

Frozen candidate: **{summary['selection']['candidate']['label']}**. Passed the predefined validation gate: **{gate}**.
Independent 2025 half-year P&L: **${pnl(folds[0]):,.2f}** and **${pnl(folds[1]):,.2f}**.
Risk remains $100 planned per trade, initial capital $50,000. No increase in risk or leverage was counted as improvement.

## Exact research replay comparison

| Period | Scenario | Net P&L | Entries | Win rate | Drawdown from closed-equity peak |
| --- | --- | ---: | ---: | ---: | ---: |
{chr(10).join(rows)}

The 2025 continuous replay differs from the two independent half-year validation accounts: account/setup/position state is carried across July in the continuous replay. Both are supplied rather than silently conflated.

## Selected changes from the cost-scenario baseline

```json
{json.dumps(differences, indent=2)}
```

Both configurations use next-open execution, 4bp commission per side, two ticks plus 2bp assumed slippage, daily financing, and stop-first ambiguous bars. They share the v1.1 DVS signals unless explicitly changed above.

## Robustness diagnostics

- `robustness.json` contains paired seven-day-block bootstrap intervals. These are conditional on the already-selected candidate; they do not correct for the search and must not be interpreted as probabilities of future profit.
- `slippage_sensitivity.csv` replays both strategies at 0/1/2/4/8bp extra slippage using 2025 only. Financing and fees remain included.
- `parameter_neighborhood.csv` checks plus/minus 20% parameter perturbations on development data only. These results do not reselect the candidate.
- Baseline and selected full-period ledgers, equity curves, events and source/config/data hashes are preserved under this experiment directory.

## Limitations and next steps

There are few trades relative to the number of configurations tested. Historical selection bias remains material. The baseline historical dataset and 2026 have already been inspected; future observations and execution-feed paper testing are still needed. The 2026 stress run was diagnostic only. A failed validation gate is a failed promotion, even if a full-history curve looks attractive.

No live orders, exchange credentials or funded-account execution have been added. The verified parity version remains unchanged and separately selectable. Research risk estimates cannot guarantee a stop-loss budget through gaps or unknown fills.
"""
    (directory / "research_report.md").write_text(report, encoding="utf-8")
    target = ROOT / "reports" / f"strategy_improvement_{directory.name}.md"
    target.write_text(report, encoding="utf-8")
    print(f"Saved post-selection diagnostics: {target}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--data", type=Path, default=PARQUET)
    args = parser.parse_args()
    analyze(args.directory, args.data)

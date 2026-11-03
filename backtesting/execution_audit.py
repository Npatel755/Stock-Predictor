"""Frozen-profile stress diagnostics; no candidate selection or tuning."""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pandas as pd

from .config import StrategyConfig
from .engine import backtest
from .indicators import prepare_indicators
from .market_data import load_history, utc
from .optimize import evaluate, pnl, subset, write_json
from .paths import PARQUET, ROOT


def concentration(trades: pd.DataFrame):
    """Mechanical removal diagnostic, never a re-simulated counterfactual."""
    net = trades.net_pnl if len(trades) else pd.Series(dtype=float)
    values = {"closed_trade_pnl": float(net.sum()), "closed_trade_legs": len(trades)}
    for count in [1, 3, 5, 10]:
        values[f"pnl_excluding_best_{count}_legs"] = float(net.sum() - net.nlargest(count).sum())
    losses, longest = 0, 0
    for value in net:
        losses = losses + 1 if value < 0 else 0
        longest = max(longest, losses)
    values["longest_losing_leg_streak"] = longest
    values["note"] = "Subtracts recorded winning legs without re-simulating state, fees, sizing or margin; not an executable counterfactual"
    return values


def run(directory: Path, data_path=PARQUET):
    selection = json.loads((directory / "selection.json").read_text(encoding="utf-8"))
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    for name, digest in manifest["source_hashes"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Frozen source changed")
    if hashlib.sha256(Path(data_path).read_bytes()).hexdigest() != manifest["data_sha256"]:
        raise ValueError("Frozen dataset changed")
    cfg = StrategyConfig(**selection["candidate"]["config"])
    bars, _ = load_history(data_path)
    bars = bars[bars.timestamp < utc("2026-10-28")].reset_index(drop=True)
    features = prepare_indicators(bars)
    windows = [(f"{year}_H{half+1}", f"{year}-{'01' if half == 0 else '07'}-01",
                f"{year}-07-01" if half == 0 else f"{year+1}-01-01")
               for year in [2023, 2024, 2025] for half in [0, 1]]
    windows += [("2026_audit", "2026-01-01", "2026-10-28")]
    results = []
    for label, start, end in windows:
        b, f = subset(bars, features, start, end)
        for slip in [2., 4., 8.]:
            scenario = replace(cfg, slippage_bps=slip)
            metrics = evaluate(b, f, scenario.__dict__)
            results.append({"period": label, "slippage_bps": slip, "metrics": metrics})
            print(f"STRESS {label} extra_slippage={slip}bp pnl=${pnl(metrics):.2f}", flush=True)
    # Risk budgets remain fixed here; costs use mark-price assumptions only.
    all_result = backtest(bars, cfg, indicators=features, capture_details=False)
    trade_diagnostics = {"full_history": concentration(all_result.trades)}
    for label, start, end in [("validation_2025", "2025-01-01", "2026-01-01"),
                              ("audit_2026", "2026-01-01", "2026-10-28")]:
        b, f = subset(bars, features, start, end)
        result = backtest(b, cfg, indicators=f, capture_details=False)
        trade_diagnostics[label] = concentration(result.trades)
    payload = {"selection_unchanged": cfg.__dict__, "half_year_slippage_stress": results,
               "trade_concentration": trade_diagnostics, "audit_only_no_profile_selection": True}
    write_json(directory / "execution_stress.json", payload)
    rows = [{"period": row["period"], "slippage_bps": row["slippage_bps"], "net_pnl": pnl(row["metrics"]),
             "trades": row["metrics"]["entries"], "drawdown_usd": row["metrics"]["max_closed_equity_drawdown_usd"]} for row in results]
    pd.DataFrame(rows).to_csv(directory / "half_year_execution_stress.csv", index=False)
    report = f"""# Frozen v1.2 execution stress — {directory.name}

The selected rules are unchanged. Every scenario retains commission, financing and next-open fills. The extra slippage assumption is varied without changing the strategy or excluding losing periods. Half-year accounts start independently with $50,000 and $100 planned risk; indicator warm-up uses causal prior history. 2025 has been reused for model selection, and 2026 was previously inspected.

| Window | Extra adverse slippage per market/stop side | Net P&L | Entries | Closed-equity drawdown |
| --- | ---: | ---: | ---: | ---: |
{chr(10).join(f"| {r['period']} | {r['slippage_bps']}bp | ${r['net_pnl']:,.2f} | {r['trades']} | ${r['drawdown_usd']:,.2f} |" for r in rows)}

## Concentration of returns

```json
{json.dumps(trade_diagnostics, indent=2)}
```

Removal diagnostics are mechanical ledger subtraction, not an executable backtest. They do not account for changed position state or capital. They help expose dependence on a few large winners. Slippage estimates do not observe spread, order-book liquidity, or actual Breakout fills. Passing a historical gate at one cost level is not proof of a durable edge.
"""
    (directory / "execution_stress.md").write_text(report, encoding="utf-8")
    (ROOT / "reports/v1_2_execution_stress.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--data", type=Path, default=PARQUET)
    args = parser.parse_args()
    run(args.directory, args.data)

"""Reproducible JSON/CSV/Parquet results plus offline HTML and PNG charts."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .engine import BacktestResult


def attach_research_profile(result: BacktestResult, configuration: Path):
    """Label a saved preset only if its exact config and derivative hash match."""
    configuration = Path(configuration)
    metadata_path = configuration.with_name(configuration.stem + ".metadata.json")
    if not metadata_path.exists():
        return
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(json.dumps(result.config, sort_keys=True).encode()).hexdigest()
    if digest != metadata.get("configuration_sha256"):
        return  # CLI overrides or edited configurations are not the frozen preset.
    name = metadata.get("strategy_name")
    if name != "DVS ETH v1.2":
        return
    derivative = configuration.parent.parent / "reference/DVS_ETH_v1_2.pine"
    if not derivative.exists() or hashlib.sha256(derivative.read_bytes()).hexdigest() != metadata.get("pine_sha256"):
        raise ValueError("Saved strategy's Pine derivative does not match its metadata")
    result.provenance.update(research_profile=name + " (experimental)",
                             research_derivative_sha256=metadata["pine_sha256"],
                             base_pine_version=result.config["strategy_version"],
                             historical_gate_passed=metadata.get("passed_predeclared_validation_gate", False))


def safe_value(value):
    if isinstance(value, dict):
        return {key: safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe_value(item) for item in value]
    if isinstance(value, (pd.Timestamp, Path)):
        return str(value)
    if isinstance(value, (float, np.floating)) and not np.isfinite(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    return value


def chart(result: BacktestResult):
    curve = result.equity
    # Render a compact overview while keeping full-resolution data in Parquet.
    step = max(1, len(curve) // 15000)
    display = curve.iloc[::step]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[.7, .3], vertical_spacing=.06)
    fig.add_trace(go.Scatter(x=display.timestamp, y=display.equity, name="Equity", line={"color": "#38bdf8"}), row=1, col=1)
    dd = curve.equity / curve.equity.cummax() - 1
    fig.add_trace(go.Scatter(x=display.timestamp, y=dd.iloc[::step] * 100, name="Close drawdown %", fill="tozeroy",
                             line={"color": "#fb7185"}), row=2, col=1)
    profile = result.provenance.get("research_profile", f"DVS ETH {result.config['strategy_version']}")
    fig.update_layout(template="plotly_dark", title=f"{profile} · {result.config['mode']} · parity unverified",
                      height=650, margin=dict(l=30, r=30, t=65, b=30), legend=dict(orientation="h"))
    fig.update_yaxes(title_text="USD", row=1, col=1)
    fig.update_yaxes(title_text="%", row=2, col=1)
    return fig


def save_result(result: BacktestResult, directory: Path, data_path: Path) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    provenance = {**result.provenance, "dataset_sha256": hashlib.sha256(Path(data_path).read_bytes()).hexdigest(),
                  "implementation_sha256": {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
                                             for name in ["config.py", "market_data.py", "indicators.py", "engine.py"]},
                  "python": platform.python_version(), "created_at_utc": str(pd.Timestamp.now(tz="UTC")),
                  "versions": {p: importlib.metadata.version(p) for p in ["pandas", "numpy", "pyarrow", "plotly"]}}
    payload = {"metrics": result.metrics, "config": result.config, "quality": result.quality, "provenance": provenance}
    (directory / "results.json").write_text(json.dumps(safe_value(payload), indent=2, allow_nan=False), encoding="utf-8")
    for name, data in [("trades", result.trades), ("equity", result.equity), ("signals", result.signals), ("events", result.events)]:
        data.to_parquet(directory / f"{name}.parquet", index=False)
        if name in {"trades", "events"}:
            data.to_csv(directory / f"{name}.csv", index=False)
    chart(result).write_html(directory / "equity.html", include_plotlyjs=True)
    fig, ax = plt.subplots(figsize=(11, 4), constrained_layout=True)
    ax.plot(result.equity.timestamp, result.equity.equity, color="#0284c7", linewidth=.8)
    profile = result.provenance.get("research_profile", f"DVS ETH {result.config['strategy_version']}")
    ax.set(title=f"{profile} — {result.config['mode']} (TradingView parity unverified)", ylabel="Equity (USD)")
    ax.grid(alpha=.2)
    fig.savefig(directory / "equity.png", dpi=150)
    plt.close(fig)
    m = result.metrics
    summary = f"""# {profile} backtest — {result.config['mode']}

Source: **{provenance['pine_title']}**. TradingView parity remains **unverified**.
Period: {result.equity.timestamp.iloc[0]} through {result.equity.timestamp.iloc[-1]}.

| Measure | Result |
| --- | ---: |
| Starting equity | ${m['initial_capital']:,.2f} |
| Final marked equity | ${m['final_equity']:,.2f} |
| Net return | {m['net_return']:.2%} |
| Entries | {m['entries']} |
| Closed trade legs | {m['closed_trade_legs']} |
| Maximum modeled intrabar drawdown | {m['max_intrabar_drawdown']:.2%} |
| Drawdown from prior closed-equity peak | ${m['max_closed_equity_drawdown_usd']:,.2f} ({m['max_closed_equity_drawdown_fraction']:.2%}) |
| Commission | ${m['total_commission']:,.2f} |
| Financing | ${m['total_swap']:,.2f} |
| Margin call events | {m['margin_call_events']} |

Dataset gaps in requested range: {result.quality.get('missing_bars', 0)} five-minute bars.
Gap policy: **{result.config['gap_policy']}**. No candles are forward-filled.
Open positions remain marked at the final close; they are not silently liquidated.
Partial margin liquidations appear as separate trade legs; entry count is distinct.
Intrabar fill timestamps are upper bounds; use `exit_bar_open` and `exit_phase` for reconciliation.

The selected source version is {result.config['strategy_version']}; both original supplied files are preserved under `backtesting/reference/`.
Run configuration, data/source hashes and library versions are in `results.json`.
This run uses {result.config['commission_bps'] / 100:.2f}% commission per side, {result.config['slippage_ticks']} instrument ticks slippage, and {result.config['swap_daily_bps']}bp/day financing.
Mode B changes are listed explicitly in the configuration and must not be interpreted as TradingView parity.
Personal Pine loss/entry limits are not a test of a funded account's contractual rules.

[Offline interactive chart](equity.html). Full-resolution signals, events, equity and trades are provided as Parquet.
"""
    (directory / "report.md").write_text(summary, encoding="utf-8")
    return directory / "report.md"

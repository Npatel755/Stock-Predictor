"""Frozen strategy transfer test on previously unused 2020-2022 ETH perps.

This is an earlier-market-regime retrospective audit, not prospective testing.
No parameter selection or profile export is performed by this module.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import json
import logging
from pathlib import Path

from .config import StrategyConfig
from .engine import backtest
from .indicators import prepare_indicators
from .market_data import download_history, load_history, utc
from .optimize import baseline, pnl, subset, write_json
from .paths import ROOT
from .reporting import save_result


def freeze_plan(directory: Path, selection_path: Path, parent_path: Path):
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    configs = {"baseline": asdict(baseline()), "first_v1_2": parent,
               "refined_v1_2": selection["candidate"]["config"]}
    plan = {"name": "2020-2022 earlier-regime transfer audit", "start": "2020-01-01", "end_exclusive": "2023-01-01",
            "evaluation_windows": [["2020-01-01", "2021-01-01"], ["2021-01-01", "2022-01-01"],
                                   ["2022-01-01", "2023-01-01"], ["2020-01-01", "2023-01-01"]],
            "configs": configs, "decision": "Frozen refined candidate already chosen using pre-2026 development data; audit cannot reselect or overwrite profiles",
            "selection_sha256": hashlib.sha256(selection_path.read_bytes()).hexdigest(),
            "parent_config_sha256": hashlib.sha256(parent_path.read_bytes()).hexdigest(),
            "source_hashes": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                              for name in ["config.py", "engine.py", "indicators.py", "market_data.py", "transfer_audit.py"]},
            "gap_policy": "Explicit research segmentation for all configurations if actual data gaps occur; no candles fabricated",
            "classification": "Newly fetched, previously untested earlier regime; neither chronological forward validation nor proof of future profitability"}
    path = directory / "transfer_manifest.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != plan:
            raise ValueError("Frozen transfer protocol differs; use a new output directory")
    else:
        write_json(path, plan)  # Freeze before looking at or downloading outcomes.
    return plan


def run(args):
    args.output.mkdir(parents=True, exist_ok=True)
    plan = freeze_plan(args.output, args.selection, args.parent)
    data = ROOT / "data/ethusd/perpetual_2020_2022/candles.parquet"
    if not data.exists():
        download_history(plan["start"], plan["end_exclusive"], directory=data.parent)
    bars, quality = load_history(data)
    features = prepare_indicators(bars)
    results = []
    for start, end in plan["evaluation_windows"]:
        b, f = subset(bars, features, start, end)
        for name, raw in plan["configs"].items():
            cfg = replace(StrategyConfig(**raw), gap_policy="segment")
            result = backtest(b, cfg, indicators=f)
            output = args.output / f"{start[:4]}_{end[:4]}" / name
            save_result(result, output, data)
            results.append({"window_start": start, "window_end_exclusive": end,
                            "scenario": name, "metrics": result.metrics})
            write_json(args.output / "transfer_results.json", {"results": results, "quality": quality,
                                                                  "dataset_sha256": hashlib.sha256(data.read_bytes()).hexdigest()})
            print(f"TRANSFER {start}:{end} {name}: pnl=${pnl(result.metrics):.2f}, entries={result.metrics['entries']}", flush=True)
    lines = []
    for row in results:
        m = row["metrics"]
        lines.append(f"| {row['window_start']}–{row['window_end_exclusive']} | {row['scenario']} | ${pnl(m):,.2f} | {m['entries']} | {m['max_intrabar_drawdown']:.2%} |")
    report = f"""# Earlier-regime strategy transfer audit

Rules and all three comparators were frozen before this previously unused 2020–2022 dataset was downloaded. This is a **retrospective earlier-regime test**, not forward paper trading or a new claim of chronological out-of-sample performance.

All variants retain $100 planned risk on $50,000 capital, next-open entries, 4bp commission per side, two ticks plus 2bp assumed extra adverse market/stop slippage, financing and stop-first ambiguity handling. The refined candidate was already selected before this audit and is not reselected here.

| UTC window (end exclusive) | Scenario | Net P&L | Entries | Running-peak intrabar drawdown |
| --- | --- | ---: | ---: | ---: |
{chr(10).join(lines)}

Annual rows are independent accounts with historical indicator warm-up. The 2020–2023 row is a separate continuous account, so annual sums need not equal it. Partial starting indicator history is unavailable before 2020. Data quality: {quality['rows']:,} bars, {quality['missing_bars']} missing bars. Any gap is explicitly segmented in Research mode; it is never filled with invented or spot candles. Gap-boundary closes, if any, are synthetic data-quality handling.

Raw/cleaned earlier data remains separate from the 2023–2026 dataset. Every comparison includes full ledgers and data/source/configuration hashes under this audit's artifact directory. This additional historical check does not remove model-selection bias or the need for future paper observations.
"""
    (args.output / "report.md").write_text(report, encoding="utf-8")
    (ROOT / "reports/strategy_transfer_2020_2022.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, default=ROOT / "artifacts/optimization/round2_v1_2_neighborhood/selection.json")
    parser.add_argument("--parent", type=Path, default=ROOT / "artifacts/optimization/round2_v1_2_neighborhood/parent_config.json")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/optimization/transfer_2020_2022")
    run(parser.parse_args())

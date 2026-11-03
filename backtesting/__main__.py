"""Command line interface for the local DVS ETH research platform."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from .config import StrategyConfig
from .engine import backtest
from .market_data import download_history, load_history, utc
from .paths import PARQUET, RUNS
from .reporting import save_result, safe_value, attach_research_profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    data = sub.add_parser("download", help="Incremental public ETH perpetual archive import")
    data.add_argument("--start", default="2023-01-01")
    data.add_argument("--end", help="Exclusive UTC date; defaults to current UTC day")
    run = sub.add_parser("run", help="Run DVS event-driven strategy")
    run.add_argument("--data", type=Path, default=PARQUET)
    run.add_argument("--mode", choices=["parity", "research"], default="parity")
    run.add_argument("--strategy-version", choices=["v1", "v1.1"], help="Pine source version; defaults to v1.1")
    run.add_argument("--config", type=Path, help="JSON StrategyConfig; CLI mode/gap policy override it")
    run.add_argument("--gap-policy", choices=["reject", "segment"], default="reject")
    run.add_argument("--start", help="Inclusive UTC date; indicators initialize at this data start")
    run.add_argument("--end", help="Exclusive UTC date")
    run.add_argument("--output", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.command == "download":
        path, quality = download_history(args.start, args.end)
        print(json.dumps({"path": str(path), "rows": quality["rows"], "missing_bars": quality["missing_bars"]}, indent=2))
        return
    values = json.loads(args.config.read_text(encoding="utf-8")) if args.config else {}
    values.update(mode=args.mode, gap_policy=args.gap_policy)
    if args.strategy_version:
        values["strategy_version"] = args.strategy_version
    cfg = StrategyConfig(**values)
    bars, quality = load_history(args.data)
    if args.start or args.end:
        from .market_data import clean_candles
        start = utc(args.start) if args.start else bars.timestamp.min()
        end = utc(args.end) if args.end else bars.available_at.max()
        bars = bars[(bars.timestamp >= start) & (bars.available_at <= end)]
        bars, quality = clean_candles(bars, start, end)
    logging.info("Starting %s DVS run: %s bars", cfg.mode, len(bars))
    result = backtest(bars, cfg, quality=quality)
    if args.config:
        attach_research_profile(result, args.config)
    out = args.output or RUNS / f"{cfg.mode}_{cfg.strategy_version.replace('.', '_')}"
    report = save_result(result, out, args.data)
    print(json.dumps(safe_value({"report": report, **result.metrics}), indent=2, allow_nan=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, FileNotFoundError) as exc:
        logging.error("%s", exc)
        raise SystemExit(2) from None

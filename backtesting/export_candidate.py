"""Export experimental signal/risk rules to Pine, with explicit fill-model limits."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re

from .config import StrategyConfig
from .paths import PINE, ROOT


def pine_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value)
    return str(value)


def render_candidate(config: StrategyConfig, label="Experimental research", version="v1.2") -> str:
    if version not in {"v1.2", "v1.3"}:
        raise ValueError("Unsupported research export version")
    if config.mode != "research" or config.strategy_version != "v1.1":
        raise ValueError("Export requires a v1.1 research configuration")
    source = PINE.read_text(encoding="utf-8")

    def swap(old, new):
        nonlocal source
        if source.count(old) != 1:
            raise ValueError(f"Pine source anchor changed: {old[:65]}")
        source = source.replace(old, new, 1)

    swap('strategy("DVS ETH v1.1 | Bias + Structure + Volume",', f'strategy("DVS ETH {version} | Research candidate",')
    swap("process_orders_on_close=true", "process_orders_on_close=" + pine_value(config.entry_timing == "signal_close"))
    swap("commission_value=0.04", f"commission_value={config.commission_bps / 100}")
    swap("slippage=2, margin_long=20, margin_short=20", f"slippage={config.slippage_ticks}, margin_long={config.margin_ratio*100}, margin_short={config.margin_ratio*100}")
    swap("initial_capital=50000", f"initial_capital={config.initial_capital}")
    mapping = {"riskUSD": config.risk_usd, "rewardR": config.reward_r, "maxLeverage": config.max_leverage,
               "maxDailyLoss": config.max_daily_loss, "maxTradesDay": config.max_trades_day,
               "maxSetupBars": config.max_setup_bars, "breakoutRVOL": config.breakout_rvol,
               "entryRVOL": config.entry_rvol, "retestATR": config.retest_atr, "stopATR": config.stop_atr}
    for variable, value in mapping.items():
        source, matches = re.subn(rf"({variable}\s*=\s*input\.(?:float|int)\()[^,]+", lambda match: match[1] + pine_value(value), source)
        if matches != 1:
            raise ValueError(f"Missing unique Pine input: {variable}")
    header = f"""// RESEARCH DERIVATIVE of the supplied DVS ETH v1.1; original copyright/license retained.
// Candidate: {label.replace(chr(10), ' ')}
// Config SHA-256: {hashlib.sha256(json.dumps(asdict(config), sort_keys=True).encode()).hexdigest()}
// NOT a verified TradingView/Python execution match.
// Pine models only {config.slippage_ticks} ticks of slippage; Python additionally assumes {config.slippage_bps}bp per market/stop side.
// Extra slippage below affects risk estimation, not Pine's broker fills.
// Pine does not reproduce Python's {config.swap_daily_bps}bp/day financing or its '{config.intrabar_policy}' OHLC ambiguity policy.
// Compare exported entries/stops/sizes before using this research derivative.
"""
    extra = f"""
// Experimental settings, separate from the supplied parity source.
minStopBps = input.float({config.min_stop_bps}, "Minimum stop (basis points)", minval=0)
minStopATR = input.float({config.min_stop_atr}, "Minimum stop (ATR)", minval=0)
costRisk = input.bool({pine_value(config.risk_includes_costs)}, "Include estimated fees/slippage in size")
assumedExtraBps = input.float({config.slippage_bps}, "Extra slippage for risk estimate only (bp)", minval=0)
minRewardCost = input.float({config.min_reward_cost_ratio}, "Minimum target / estimated costs", minval=0)
minAtrBps = input.float({config.min_atr_bps}, "Minimum 5m ATR (bp)", minval=0)
maxAtrBps = input.float({config.max_atr_bps}, "Maximum 5m ATR (bp; 0 disables)", minval=0)
minTrendBps = input.float({config.min_trend_gap_bps}, "Minimum 4H trend distance (bp)", minval=0)
tradeDirection = input.string({pine_value(config.trade_direction)}, "Directions", options=["both", "long", "short"])
utcSession = input.string({pine_value(config.session)}, "UTC session", options=["all", "europe_us", "us", "asia"])
weekends = input.bool({pine_value(config.allow_weekends)}, "Allow weekends")
cooldownBars = input.int({config.cooldown_bars}, "Cooldown bars after exit", minval=0)
breakevenR = input.float({config.breakeven_r}, "Close-based breakeven trigger R; 0 disables", minval=0)
trailATR = input.float({config.trail_atr}, "Close-based trailing ATR; 0 disables", minval=0)
maxHoldingBars = input.int({config.max_holding_bars}, "Maximum holding bars; 0 disables", minval=0)
estimateCosts(price) => 2 * price * ({config.commission_bps} + assumedExtraBps) / 10000 + 2 * {config.slippage_ticks} * syminfo.mintick
var int lastExitBar = -1000000
var float activeStop = na
var float activeTarget = na
var float initialRisk = na
if strategy.closedtrades > nz(strategy.closedtrades[1])
    lastExitBar := bar_index
"""
    swap("validChart = timeframe.in_seconds() == 300", extra + "\nvalidChart = timeframe.in_seconds() == 300")
    gating = """
utcHour = hour(time, "UTC")
utcDay = dayofweek(time, "UTC")
sessionOK = utcSession == "all" or (utcSession == "europe_us" and utcHour >= 7 and utcHour < 21) or (utcSession == "us" and utcHour >= 13 and utcHour < 21) or (utcSession == "asia" and utcHour >= 0 and utcHour < 8)
weekdayOK = weekends or (utcDay >= dayofweek.monday and utcDay <= dayofweek.friday)
directionOK = (confirmLong and tradeDirection != "short") or (confirmShort and tradeDirection != "long")
atrBps = atr5 / close * 10000
volatilityOK = atrBps >= minAtrBps and (maxAtrBps == 0 or atrBps <= maxAtrBps)
trendOK = minTrendBps == 0 or math.abs(close4h / ema4h - 1) * 10000 >= minTrendBps
researchAllowed = sessionOK and weekdayOK and directionOK and volatilityOK and trendOK and bar_index - lastExitBar >= cooldownBars
"""
    swap("if barstate.isconfirmed and (confirmLong or confirmShort)", gating + "\nif barstate.isconfirmed and (confirmLong or confirmShort)")
    swap("    if stopValid and stopDistance > syminfo.mintick", """    stopDistance := math.max(stopDistance, math.max(close * minStopBps / 10000, atr5 * minStopATR))
    stopPrice := close - (isLong ? 1 : -1) * stopDistance
    estimatedCost = estimateCosts(close)
    rewardCostOK = rewardR * stopDistance >= minRewardCost * estimatedCost
    if stopValid and stopDistance > syminfo.mintick and rewardCostOK and researchAllowed""")
    swap("sizeByRisk = riskUSD / (stopDistance * syminfo.pointvalue)", "sizeByRisk = riskUSD / ((stopDistance + (costRisk ? estimatedCost : 0)) * syminfo.pointvalue)")
    swap("        if tradeQty > 0", """        if tradeQty > 0
            activeStop := stopPrice
            activeTarget := targetPrice
            initialRisk := na""")
    manager = f"""
// Completed-close management affects later ticks; it cannot fill earlier on this candle.
if strategy.position_size != 0 and not na(activeStop)
    dir = strategy.position_size > 0 ? 1 : -1
    if na(initialRisk)
        initialRisk := math.abs(strategy.position_avg_price - activeStop)
    heldBars = bar_index - strategy.opentrades.entry_bar_index(0) + {1 if config.entry_timing == 'next_open' else 0}
    if maxHoldingBars > 0 and heldBars >= maxHoldingBars
        if dir == 1
            strategy.close("Long", comment="Research time exit", immediately=true)
        else
            strategy.close("Short", comment="Research time exit", immediately=true)
    else
        favorable = dir * (close - strategy.position_avg_price)
        proposed = activeStop
        if breakevenR > 0 and favorable >= breakevenR * initialRisk
            proposed := strategy.position_avg_price + dir * estimateCosts(strategy.position_avg_price)
        if trailATR > 0 and favorable >= math.max(1, breakevenR) * initialRisk
            trailing = close - dir * trailATR * atr5
            proposed := dir == 1 ? math.max(proposed, trailing) : math.min(proposed, trailing)
        tighter = dir == 1 ? proposed > activeStop : proposed < activeStop
        placeable = dir * (close - proposed) > syminfo.mintick
        if tighter and placeable
            activeStop := proposed
            if dir == 1
                strategy.exit("Long TP/SL", from_entry="Long", stop=activeStop, limit=activeTarget)
            else
                strategy.exit("Short TP/SL", from_entry="Short", stop=activeStop, limit=activeTarget)
"""
    swap('plot(ema4h, "Previous confirmed 4H EMA 50"', manager + '\nplot(ema4h, "Previous confirmed 4H EMA 50"')
    # Retain the original license header; version annotation must precede code.
    return header + source


def export(directory: Path, output: Path, version="v1.2"):
    selection = json.loads((directory / "selection.json").read_text(encoding="utf-8"))
    candidate = selection["candidate"]
    cfg = StrategyConfig(**candidate["config"])
    content = render_candidate(cfg, candidate["label"], version=version)
    stem = "dvs_eth_" + version.replace(".", "_")
    config_path = ROOT / "configs" / f"{stem}.json"
    metadata_path = ROOT / "configs" / f"{stem}.metadata.json"
    # Preserve each earlier saved derivative before changing the current v1.2.
    # Content-addressed revisions make repeated exports idempotent.
    if output.exists() and output.read_text(encoding="utf-8") != content:
        previous_digest = hashlib.sha256(output.read_bytes()).hexdigest()
        archive = ROOT / "reference/revisions" / previous_digest[:16]
        archive.mkdir(parents=True, exist_ok=True)
        (archive / output.name).write_bytes(output.read_bytes())
        for previous in [config_path, metadata_path]:
            if previous.exists():
                (archive / previous.name).write_bytes(previous.read_bytes())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")
    metadata = {"strategy_name": f"DVS ETH {version}", "base_pine_version": "v1.1", "mode": "research",
                "experiment": directory.name, "selected_candidate": candidate["label"],
                "passed_predeclared_validation_gate": selection["passed_predeclared_validation_gate"],
                "ready_for_funded_trading": False,
                "historical_gate_is_forward_validation": False,
                "configuration_sha256": hashlib.sha256(json.dumps(asdict(cfg), sort_keys=True).encode()).hexdigest(),
                "pine_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "pine_compilation_verified": False, "tradingview_parity_verified": False,
                "execution_differences": ["Pine fixed tick slippage omits Python's additional basis-point fill slippage",
                                          "Pine omits Python's financing and stop-first ambiguity policy"],
                "note": "Version label names this research derivative; gate is historical/reused-data selection, not evidence of profitable future trading. See regime-transfer and execution-stress reports."}
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Exported experimental Pine signals/risk; execution assumptions differ: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--version", choices=["v1.2", "v1.3"], default="v1.2")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or ROOT / "reference" / f"DVS_ETH_{args.version.replace('.', '_')}.pine"
    export(args.directory, output, version=args.version)

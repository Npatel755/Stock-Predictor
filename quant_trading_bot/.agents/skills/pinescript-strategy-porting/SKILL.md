---
name: pinescript-strategy-porting
description: Translate TradingView Pine Script strategies to Python or LEAN while preserving bar timing, order semantics and accounting.
---

# Pine Script Strategy Porting and Parity

## Trigger
When an existing strategy is Pine Script/TradingView code or comes from a YouTube TradingView tutorial.

## Conversion procedure
1. Snapshot the exact Pine version/code, chart timeframe, symbol, adjusted data, timezone/session and strategy settings (`process_orders_on_close`, `calc_on_every_tick`, pyramiding, commissions, slippage, margins).
2. Map series operations to online causal indicators, respecting bar-close availability, `security` / higher-timeframe values, `lookahead` settings and history references.
3. Separate strategy signal timing from simulated entry/exit timing; TradingView broker-emulator behavior differs from vectorized Python and LEAN.
4. Implement a small deterministic fixture and export timestamped Pine signals/orders/equity when accessible.
5. Match trade-by-trade signals, positions, fees and exits on the same data in Python/LEAN; investigate every mismatch before optimizing.
6. Treat order fill modeling, intrabar high/low ambiguity and bar magnifier availability as explicit assumptions.
7. Once equivalent, freeze a baseline and explore improvements only on the proper training partition.

## Deliverables
Rules parity matrix, calculation timing ledger, conversion tests, mismatches, and two strategies marked source/derived.

Never equate a TradingView strategy tester P&L with a funded-account compliant realized P&L without independent checks.

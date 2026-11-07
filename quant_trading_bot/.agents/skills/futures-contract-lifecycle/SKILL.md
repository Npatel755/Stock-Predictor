---
name: futures-contract-lifecycle
description: Handle equity-index futures expirations, contract rolls, continuous series, sessions, and actual contract-level execution safely.
---
# Futures contract lifecycle and realistic historical series

Use this skill when importing historical ES/NQ/MES/MNQ contracts, constructing continuous data, rolling futures, calculating P&L across expirations, or comparing backtest and live contract identifiers. Coordinate with `data-integrity`, `backtesting-engine`, and `cross-contract-transfer`.

## Non-negotiable distinctions
- Keep the **tradable individual contract** (symbol, expiry, exchange, multiplier, tick size) distinct from a **synthetic continuous series** used for signal research.
- A back-adjusted continuous price is not a fillable historical price. Never use an adjustment jump as real return or unrealized P&L.
- Maintain an as-of-date contract map and explicit roll policy. CME publishes customary equity-index roll dates, but any rolling rule must be defined before analyzing its profitability.
- Require explicit sources for expirations, last-trading times, session calendars, tick sizes and fees. Do not invent dates, trade unavailable contracts, or infer fillability from an interpolated continuous bar.

## Procedure
1. Ingest and preserve raw per-contract timestamps, OHLCV/trades/quotes, contract IDs, time zone, vendor, provenance and data version.
2. Produce a roll schedule from point-in-time executable inputs (e.g., fixed calendar rule or *prior-known* volume/open-interest rule); document which contract is active each session.
3. If constructing a continuous series, explicitly name the adjustment method (`unadjusted`, `back_adjusted`, `ratio`) and audit jump behavior and indicators near rolls.
4. Generate indicators from the documented research series, but execute orders and mark-to-market on the actual contract available at the time.
5. Model flattening/rolling positions as explicit transactions with realistic spread, commission, price gaps, market closures, and risk exposure.
6. Use official market hours and holiday calendars; handle DST via IANA time zones, not hardcoded UTC offsets.
7. Report P&L, trade counts, and failure cases segmented by expiry cycle, roll week, and regular/overnight sessions.

## Unit and regression tests
- There is no artificial gain from a continuous-series adjustment.
- Contract changes preserve dollar exposures only when position-size and P&L multipliers are deliberately applied.
- No trading after an instrument's last eligible trading time.
- No signals or rolls use volume/open interest unavailable at decision time.
- Roll execution fees and spreads appear in the ledger.

## Output
Provide a contract calendar, roll table, adjustment explanation, continuous-vs-tradable comparison, reconciliation tests, exceptions, and a machine-readable audit log. Fail closed if contract metadata is missing.

## References
- CME equity-index roll conventions: https://www.cmegroup.com/trading/equity-index/rolldates.html
- CME holiday/trading hours: https://www.cmegroup.com/trading-hours.html
- CME equity futures contract summary: https://www.cmegroup.com/markets/equities/sp-500-and-nasdaq-100-futures.html

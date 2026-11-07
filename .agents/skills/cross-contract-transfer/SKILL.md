---
name: cross-contract-transfer
description: Research signals on E-mini NQ/ES while validating tradeability and net P&L on target micro MNQ/MES with correct contract economics.
---
# E-mini to Micro E-mini cross-contract transfer

Use when a strategy is designed using NQ or ES historical data and intended to trade MNQ or MES. Coordinate with `data-integrity`, `futures-contract-lifecycle`, `execution-optimization`, and `risk-management`.

## Economic mappings (verify periodically against CME)
- NQ: $20 per Nasdaq-100 index point; MNQ: $2 per point.
- ES: $50 per S&P 500 index point; MES: $5 per point.
- Each has 0.25 index-point minimum tick: NQ $5.00, MNQ $0.50, ES $12.50, MES $1.25 per tick.
- This is a contract-size relationship, **not** proof of identical bid/ask liquidity or proportional all-in trading costs.

## Transfer workflow
1. Determine whether large-contract data powers **feature/signal research only** or also drives fills. Never silently treat NQ/ES close prices as executable MNQ/MES fills.
2. Separate underlying index-point signals from dollar P&L, position size, exchange-specific fees and fill modeling.
3. Preserve as-of timestamp alignment and the same contract calendar for paired contracts; quantify missing bars and feed discrepancies.
4. If target micro quote/trade data exists, independently simulate target fills with target spread, depth, tick size, fees and actual order constraints.
5. If only large-contract OHLCV exists, produce an **indicative signal backtest** and explicit conservative micro-execution scenarios; do not call this a verified micro strategy.
6. Evaluate whether fixed dollar stop and target rules scale sensibly and whether minimum tradable micro size breaks risk limits.
7. Out-of-sample test transfer across quiet, high-volatility, overnight, release-time and roll periods, especially where micro fills diverge.

## Acceptance gates
- All multiplier/tick arithmetic matches deterministic fixture trades.
- Strategies meet configured *actual* micro account drawdown and contract limits, not merely scaled E-mini metrics.
- Material performance differences between source and target are disclosed rather than averaged away.
- No claims of micro net profitability without credible target-instrument fill/cost evidence.

## Reference
- CME equity index contract summary: https://www.cmegroup.com/markets/equities/sp-500-and-nasdaq-100-futures.html

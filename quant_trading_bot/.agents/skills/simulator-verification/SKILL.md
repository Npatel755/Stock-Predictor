---
name: simulator-verification
description: Independently audit a futures backtester with accounting invariants, synthetic fixtures, adversarial scenarios and cross-engine reconciliation.
---
# Simulator verification and adversarial backtester testing

Use before believing P&L, sharpe, drawdown or funded-account compliance from any new or modified backtester. Coordinate with `backtesting-engine` and `risk-management` but act as an independent verifier, not a performance optimizer.

## Mandatory invariants
- Trades cannot fill before the order and triggering market data become available.
- Contract P&L = signed price change × verified contract multiplier × quantity, adjusted for applicable costs.
- Every executed order updates cash, realized/unrealized P&L, fees, inventory and exposure consistently.
- Realized profits do not appear twice during position closes or rollover.
- Adding nonnegative costs to identical fills cannot increase net P&L.
- Invalid prices, fractional tick fills, impossible liquidity and unknown margins trigger rejection or explicit conservative modeling.
- Entry/stop/target conflicts within one OHLC candle must never quietly select the most profitable path.
- Trailing/threshold risk checks should evaluate the precise equity basis and timing prescribed by the current configured rule set.

## Verification fixtures
1. Flat price, no orders -> zero gross P&L.
2. One long, one short with deterministic fills -> manually reconciled symmetric price P&L before fees.
3. Known synthetic gap through stop -> adverse/no-better-than-possible execution.
4. Both stop and target touched in one candle -> tick resolution or explicit pessimistic/unknown case.
5. Overnight hold, early close, roll date, expired contract -> correct session and instrument logic.
6. Same trade with doubled verified multiplier -> doubled gross dollar exposure and P&L, not necessarily doubled net result after per-contract costs.
7. Identical trade sequence with higher costs -> no improvement in net result.
8. Streaming one bar at a time vs full-data run -> identical signals when no future data is used.

## Independent reconciliation
- Build a transparent small reference ledger separate from the optimized engine.
- Compare deterministic executions, cash flows, positions and risk states bar-by-bar.
- Use property-based or randomized test cases; seed all randomness; store failure fixtures.
- Compare vectorized vs event-driven engines where compatible, investigating any unexplained divergence.
- Require tests to pass in CI before changes to order handling, sizing, fees, resampling or futures rolls are accepted.

## Output gate
Provide test report, invariant checklist, counterexamples, unresolved model assumptions and PASS/FAIL. A failing fundamental invariant blocks all claims of demonstrated profitability from that engine.

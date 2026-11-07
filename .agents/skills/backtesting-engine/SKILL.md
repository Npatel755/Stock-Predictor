---
name: backtesting-engine
description: Build and validate fast research backtests against sequential event-driven simulations; use when implementing signal timing, orders, positions, cash flows or P&L.
---

# Backtesting Engine

## Objective
Make simulated P&L chronologically valid, consistent and contract-correct.

## Procedure
1. Define event clock, bar timestamp semantics, signal observation time, order submission, eligibility and fill time. Default to next available tradable price after a completed signal bar, with market-order costs, unless evidence supports a different model.
2. Implement cash/equity, realized/unrealized P&L, commissions per side, spread, slippage, position quantity, contract multiplier, tick increments, order rejection, margin and session close behavior.
3. Distinguish research vectorized engine from a sequential event-driven simulator; cross-check top candidates trade-by-trade. Disagreements must be explained before accepting results.
4. Stops/targets in same OHLC bar have unknowable intrabar ordering. Use tick data or conservative precedence; do not assume best-case execution. Model stop markets through gaps, not magically at stop price.
5. Simulate expiry, rollover, flattening, trading halts, missing-data gaps and market access restrictions. Do not carry raw contract positions across expiration by continuous-series arithmetic.
6. Reconcile accounting invariants: ending equity = starting equity + realized + unrealized - costs; trade P&L equals price delta x multiplier x signed contracts minus costs; no fills without a valid order.
7. Run fixtures: flat market, gap through stop, both target+stop hit, commissions on both sides, partial fill, timezone boundary, futures roll, forced liquidation, and next-bar causality.

## Metrics
Produce trade ledger, mark-to-market equity curve, cash flow, max intraday/closed-equity drawdown separately, and event-level audit records. Do not equate fast vectorized speed with execution realism.

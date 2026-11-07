---
name: batch-streaming-signal-parity
description: Prove identical causal signals and order intentions between offline backtests, paper trading and streaming production implementations.
---
# Batch-to-Streaming Signal Parity

## Trigger
Use before claiming an offline strategy can be run live, after changing indicator implementations, on switching historical data sources, or after investigating missing/mismatched paper signals. Coordinate with `paper-trading-reconciliation`, `point-in-time-feature-engineering`, `simulator-verification`, and `deployment-safety-monitoring`.

## Scope and contract
Define one deterministic strategy state machine with canonical input events, fill events and risk state. A signal must be based on the same completed data, timestamp semantics, indicator warm-up, parameter version and decision clock in both modes. Separate **signal parity** from **fill/P&L parity**; live fills may legitimately differ.

## Required checks
1. Record a compact chronological event tape: input hash, source timestamp, arrival timestamp, contract, bar version, schedule and any external publication data.
2. Backtest route A processes historical input incrementally using exact event availability. Paper/live route B replays the same tape with the same initial state. Compare per-event feature snapshot, strategy state, entry/exit intention, size and reason codes.
3. Test hot restarts and recovery using state snapshots, repeat event delivery, out-of-order messages, missing bars, overlapping subscriptions, revisions and reconnects. Verify deterministic replay and order idempotency.
4. Verify multi-timeframe indicators close only when the corresponding bar closes; explicit warm-up sufficiency; no discretionary look-ahead via future session high/low or whole-day VWAP.
5. Assert exact signal identity where deterministic; otherwise document numeric tolerances and reconcile rare floating-point differences. Any unexplained discrepancy is a release blocker.
6. Compare paper broker fills and actual brokerage fee/margin model separately; do not demand identical live prices or claim paper fill quality is executable proof.
7. Store code commit, dependencies, data version, parameter hash and time-zone configuration. Reject parity comparisons across mismatched versions unless purposely evaluating the difference.

## Outputs
Produce `research/parity/<strategy-id>/` with an event tape or reproducible locator, signal diff CSV, first-divergence report, parity summary by instrument/session, restart/idempotency tests, and evidence of zero unexplained divergences before promotion.

## Safeguards
No real-money order placement or broker permission expansion without explicit user authorization. Keep credentials out of research artifacts. A passing parity test does not establish future profitability.

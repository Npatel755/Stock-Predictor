---
name: deployment-safety-monitoring
description: Design non-live-first trading surveillance, reconciliation, drift alarms, broker safeguards and fail-closed shutdown controls for automated futures strategies.
---
# Strategy monitoring and deployment safety

Use when preparing a validated strategy for continuous paper operation or, **only with explicit authorization**, live automated trading. Coordinate with `paper-trading-reconciliation` and `risk-management`.

## Safe defaults
- **Paper trading is the default. Never send live orders, connect live credentials, or alter live risk settings without explicit approval.**
- Design monitoring as a separate process from order generation where possible; persist events durably.
- Risk-limit breaches or missing critical state should fail closed, cancel or block new orders subject to known broker semantics, and alert the user. Do not promise fills/closures that exchange connectivity cannot guarantee.

## Monitors
- Freshness, delay, gaps and source-health of market data; clock synchronization.
- Signal-to-order-to-fill latency, rejects, partial fills, duplicate/replayed orders and disconnected order state.
- Position mismatch, mark-price vs broker equity differences, limit utilization, open orders and contract expiry.
- Relative live/paper vs expected trade frequency, spread/slippage, P&L distribution and drawdown; confidence-aware drift rather than a single arbitrary threshold.
- Sudden loss streaks, extreme volatility, market hours/holiday, exchange incidents and broker restrictions.

## Kill-switch design
1. Define clear risk states (normal, reduced size, no-new-orders, cancel-pending, emergency manual intervention).
2. Separate unambiguous invariant violations from statistically noisy drift alerts.
3. Implement idempotent cancel/reconcile logic and clear rules for recovery after disconnects.
4. Require operator acknowledgment before resuming after severe breaches.
5. Test using injected faults in paper mode: stale quote, duplicate order, fill during disconnect, unexpected position, jump through a stop, session closure and broker rejection.
6. Keep a chronological incident and recovery log; never suppress errors to maintain the appearance of success.

## Outputs
Architecture diagram, configuration, alarms matrix, fault-injection test plan, escalation/rollback procedure, audit log format, and explicit confirmation of paper vs live environment.

---
name: adversarial-stress-lab
description: Create deterministic adversarial futures market and infrastructure scenarios that expose fragile execution, stop, sizing and funded-rule assumptions.
---
# Adversarial Stress Lab

## Trigger
Use after baseline simulator verification and before paper/live promotion; also when strategy metrics appear implausibly smooth. This is scenario-focused engineering that complements `risk-of-ruin-monte-carlo` (distributional outcomes) and `simulator-verification` (accounting correctness).

## Scenario library
- Sudden multi-tick jump beyond stop (stop-market slippage); limit order unfilled during fast move.
- Spread widening, depth depletion, partial fills and post-only order rejection.
- Volatility regime change, trend reversal after signal, gap across overnight/holiday, and repeated correlated loss bursts.
- Market-data freeze followed by stale batch; duplicate/out-of-order bars; clock skew; reconnect replay; cancel not acknowledged; idempotency of order submission.
- Trading halt, exchange downtime, early close, expiration/roll transition, margin change and unexpected reduced liquidity.
- Funded-account rule transition: trailing peak, liquidation threshold, session loss cap, consistency rule, daily lockout, forced flat or payout-state reset (only with verified provider semantics).

## Procedure
1. Use small deterministic fixtures with clearly specified expected outcomes before adding stochastic stress families.
2. Vary one failure mechanism at a time, then combine correlated stresses using transparent assumptions. Document impossibility/approximation of bar-level outcomes.
3. For each scenario, replay the same strategy and compare fill ledger, risk state, surviving position, cash/equity, cancellation state and stop behavior against written invariants.
4. Define fail-safe reactions: stale data -> no fresh entries; disconnected broker -> inspect positions and outstanding orders before resuming; unknown rule state -> disable entries pending reconciliation; duplicate events -> idempotent processing.
5. Measure scenario worst-case loss conditional on assumptions and detection/recovery time, not just mean P&L.
6. Do not tune strategy rules using already protected TEST periods. Synthetic stress cases should test engineering requirements, not be relabeled as actual historical performance evidence.

## Deliverables
Machine-readable scenario fixture set, invariant assertions, worst-case scenario table, risk-state replays, unresolved failure checklist and explicit promotion veto list. Default to `NOT READY` for any high-severity unresolved order, data or risk-control failure.

## Non-goals
Do not create the illusion of guaranteed extreme-event coverage. Synthetic stress scenarios cannot enumerate every market shock.

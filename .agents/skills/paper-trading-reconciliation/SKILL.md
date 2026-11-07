---
name: paper-trading-reconciliation
description: Run and audit forward paper trading, reconcile intended signals and simulated executions, and quantify backtest-to-forward performance gaps.
---
# Paper trading and backtest-to-forward reconciliation

Use after a strategy is frozen and passes internal historical validation. Do not connect or trade a live account without explicit user authorization.

## Forward experiment setup
- Freeze executable strategy artifact and config hash, fees, risk constraints, order policy, clock/time zone and instrument list before paper observation.
- Run the exact strategy code/data pipeline planned for deployment when feasible. Require timestamped market-feed timestamps, signal time, decision time, order-send time, acknowledgment, fills and cancellation events.
- Record expected backtest fill, shadow fill under live observed market conditions and actual paper-simulator fill **separately**.
- Keep an immutable append-only raw event ledger and derived reports; protect API keys and account credentials.

## Daily reconciliation
1. Rebuild signals from contemporaneously available data and match to forward logs.
2. Categorize differences: stale feed, missed bars, clock skew, market closure, order rejection, incomplete fills, slippage, wrong symbol, contract roll and implementation drift.
3. Compare expected vs observed P&L, transaction cost, drawdown, trade frequency, latency and exposure.
4. Treat paper fills as hypothetical: a broker paper simulator may not model queue priority, spread widening or true liquidity.
5. Escalate unresolved discrepancies; do not quietly change strategy parameters using forward evaluation data and keep calling the result untouched.

## Go/no-go evaluation
- Agree on minimum observation period, number of trades, adverse regimes and discrepancy tolerances before starting.
- Report whether all scheduled sessions and relevant market events were observed.
- If changes are made, version strategy and restart a separate forward evaluation period; no retroactive relabeling.

## Deliverables
Reconciliation dashboard/table, reproducible logs, list of incidents, gap attribution, risk-breach alerts, and explicit limitations of paper fills.

---
name: champion-challenger
description: Compare a current trading strategy with proposed improvements using frozen protocols and forward paper-trading evidence.
---

# Champion–Challenger Evaluation

## Purpose
Prevent new ideas from automatically replacing a stable baseline merely because a revised backtest looks better.

## Procedure
1. Freeze champion code, parameter config, data and fill assumptions, risk budget, and evaluation date.
2. Register each challenger with a distinct hypothesis and independent version/commit; do not change it during an evaluation window.
3. Compare under identical data access, fees, contract and risk settings. Track expectancy, drawdown, turnover, trade overlap, operational reliability and uncertainty, not just return.
4. Use matched periods and paired comparisons where possible; include degradation on hard regimes, event days and pessimistic slippage.
5. Prefer a *prospective* shadow/paper-trading period rather than using repeated old holdout results to crown a new winner.
6. Define promotion, rollback and retirement triggers **before** examining forward results.
7. Maintain champion and challenger audit trails including negative results.

## Deployment boundary
This skill does not authorize live trading, changing funded-account orders, or automatic promotion to real-money systems. Require explicit user approval and all safety gates.

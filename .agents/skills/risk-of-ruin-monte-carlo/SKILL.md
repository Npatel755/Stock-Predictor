---
name: risk-of-ruin-monte-carlo
description: Stress-test futures strategy equity paths and estimate funded-evaluation rule-breach risk with dependency-aware Monte Carlo methods.
---
# Risk of ruin and funded-evaluation path simulation

Use when judging whether a strategy is likely to survive a $50K funded-account evaluation with a tight loss buffer, not merely whether average backtest profit is positive. Coordinate with `risk-management` and `portfolio-construction`.

## First define the actual rule state machine
- Load *verified current* account rules from authoritative provider materials: static/trailing drawdown, equity basis (balance/equity), intraday vs end-of-day behavior, lock/floor, daily loss checks, trade limits, flat-at-close, payout/consistency specifics.
- Keep **research target** (e.g., $2,000 maximum drawdown) distinct from actual rule settings; do not assume the rule set from memory.
- If rule ambiguity is unresolved, simulate labeled scenarios rather than asserting pass/fail accuracy.

## Simulation procedure
1. Derive the chronological net-of-cost trade or intraday P&L process from training/validation evaluation; preserve actual session structure and risk sizing.
2. Prefer day-block, moving-block or regime-aware resampling when autocorrelation or clustered volatility matters; naive independent trade shuffling is at most a diagnostic.
3. Include adverse sensitivities: fee escalation, greater slippage, missed orders, streak clustering, volatility change, session gaps and less favorable stops.
4. Recompute trading path state at every step, including dynamic position sizing and all account-rule transitions.
5. Report multiple horizons and sample-size sensitivity, not a single point-estimate probability.
6. Benchmark results against observed historical drawdown and simple block/bootstrap uncertainty intervals.

## Mandatory outputs
- Estimated proportion of sampled paths breaching each configured rule, with a conspicuous statement that it is **model-conditional, not a reliable forecast**.
- Distribution of max equity drawdown, worst daily loss, days to target/failure, and longest loss streak.
- Worst observed path replay with timestamps/trades and rule-state transitions.
- Sensitivity plots/tables across reasonable changes in costs, resampling block length and volatility.
- Reasons why conclusions may be unstable (short sample, nonstationarity, tail risk, missing ticks).

## Prohibitions
- Never fit Monte Carlo assumptions on untouched test outcomes.
- Never convert a low estimated failure probability into a guarantee of passing.
- Never ignore catastrophic tails because they were absent from sampled historical paths.

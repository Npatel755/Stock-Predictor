---
name: strategy-discovery
description: Generate and evaluate hypothesis-driven futures, stocks and cryptocurrency trading strategy candidates; use when exploring trend, reversal, breakout, momentum, or volatility edges.
---

# Strategy Discovery

## Objective
Generate falsifiable hypotheses instead of searching endlessly for profitable parameter combinations.

## Procedure
1. State economic/mechanical thesis, traded market, horizon, signal publication time, execution time, conditions for failure, and benchmark *before* coding.
2. Cover distinct families: trend continuation (moving-average slope, time-series momentum), mean reversion (extreme normalized deviations), opening-range breakout, intraday momentum, volatility expansion/contraction, session effects, and cross-market confirmation. Treat cross-asset predictors as timestamped and not automatically causal.
3. Search broad, interpretable parameter grids using TRAINING data only; register every trial, including rejected candidates. Avoid arbitrary complex indicator piles and unbounded genetic search.
4. Use predeclared gates for liquidity, turnover, minimum independent trade observations, risk exposure, costs, and plausible capacity. Compare with no-trade, buy-and-hold (where meaningful), simple trend, and shuffled-signal nulls.
5. Cluster similar strategies by trade overlap and return correlation; do not count near-duplicate parameters as independent discoveries.
6. Forward finalists to overfitting-defense, walk-forward-validation, and backtesting-engine; do not inspect TEST or repeatedly optimize to VALIDATION.

## Candidate record
Save hypothesis_id, family, instruments, signal formula, data timestamp rules, parameter ranges, training period, trial count, net-of-cost metrics, regime performance, complexity, and rejection reason.

## Stop rules
When a family fails predefined feasibility gates, stop tuning that family; log a negative result. A positive backtest alone is not an edge.

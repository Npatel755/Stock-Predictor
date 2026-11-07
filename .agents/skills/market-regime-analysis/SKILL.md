---
name: market-regime-analysis
description: Detect point-in-time trend, range, volatility and liquidity regimes; use to diagnose when trading edges work or fail without hindsight-based regime labels.
---

# Market Regime Analysis

## Objective
Understand conditional strategy performance without designing hindsight-fitted filters.

## Procedure
1. Choose transparent ex-ante regime features from rolling past-only realized volatility, slope, range efficiency, volume, spreads and session times; specify available timestamps.
2. Distinguish retrospective descriptive regimes (for postmortems) from genuinely tradable online regime labels. Never use hindsight turning points as an input to the strategy.
3. Label each eligible bar using only trailing windows; require lag and warmup; fit all clustering/thresholding on TRAIN folds only.
4. Report per-regime trade count, net expectancy, drawdown, costs, exposure and uncertainty; avoid conclusions from tiny subgroups.
5. Compare strategy with and without a candidate regime filter under the same training-only development and predefined validation rules. Count filter exploration as trials.
6. Stress abrupt regime transitions, news shocks, holidays and low-liquidity windows. No regime classifier is infallible.

## Deliverable
Reproducible regime feature definitions, point-in-time labels, transition matrix, regime-conditioned analysis and caveats.

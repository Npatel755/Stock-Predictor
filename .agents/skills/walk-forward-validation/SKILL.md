---
name: walk-forward-validation
description: Run chronological rolling-origin or expanding-window trading strategy evaluations; use when testing regime adaptation, recalibration schedules and out-of-sample stability.
---

# Walk Forward Validation

## Objective
Estimate what would have been tradable if decisions were made using only information available at the time.

## Procedure
1. Specify window sizes, warmup, retraining cadence, lookback, horizons, purge/embargo, costs, and selection criteria before running evaluation.
2. At each origin t: fit features/parameters on allowed training history up to t; freeze; generate signals and trade in the next unseen evaluation block; repeat without revising earlier decisions.
3. Never normalize, compute volatility thresholds or select assets using future evaluation statistics.
4. Preserve each fold's trade ledger, profit after costs, drawdown, turnover, time under water and regime tags. Show failures and degradation, not just pooled winner metrics.
5. Stitch disjoint out-of-sample equity changes only when account/position continuity and overlapping fold handling are explicit. Avoid counting overlapping test bars twice.
6. Analyze distribution of fold performance, worst-fold risk, live-like retraining burden and how often an edge disappears; compare with frozen-parameter control.
7. For final TEST, apply the fully predetermined development procedure once. Do not reselect strategy based on final test.

## Deliverables
Walk-forward manifest, fold-by-fold results, stitched OOS curve (when valid), sensitivity summary and go/no-go recommendation.

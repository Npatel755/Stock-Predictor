---
name: point-in-time-feature-engineering
description: Build auditable past-only time series features with availability timestamps, lagged joins and safe multi-timeframe resampling.
---
# Point-in-Time Feature Engineering

## Trigger
Use whenever making ML features, mixing 1-minute and 5/15/60-minute indicators, joining economic data, importing QuantConnect/TradingView research, or producing walk-forward training tables. Coordinate with `data-integrity`, `intraday-session-clock`, `overfitting-defense`, and `strategy-replication`.

## Four timestamps
For each observation track: (1) event time; (2) market/source publish time if known; (3) locally available/received time; (4) decision/eligible order time. Availability may lag event time. Treat missing publication lag conservatively and expose uncertainty.

## Research protocol
1. Specify each feature's raw field lineage and formula. Use causal trailing windows only. When normalizing, fit scalers and imputers on TRAIN and freeze/fit anew only inside proper training folds.
2. For bar-derived features, define close timestamp, bar-end availability and latency. Never use the complete current 5/15/60-minute bar for a decision earlier in that bar.
3. For joins, use as-of joins with `information_available_at <= decision_time`, tolerance limits and provider-specific delays; drop data that fails the tolerance instead of silently backfilling from the future.
4. Distinguish economic event occurrence, first release, later revision and revised historical series. Historical revisions are not necessarily known at the historical decision time.
5. Align outcome labels and prediction horizons; use appropriate purge/embargo for overlapping labels or portfolio horizon dependencies. No target leakage via centered rolling statistics, future extrema, global fit transforms or forward-adjusted labels.
6. Treat continuous futures backward adjustments as analytical transforms; ensure signal and order execution use the proper real contract prices, and diagnose any full-history adjustment that could change earlier feature values as the sample endpoint moves.
7. Require replay parity: run features incrementally up to timestamp `t`, and compare against a batch feature matrix truncated to `t`, with tolerances. Differences indicate look-ahead, state or warm-up bugs.

## Mandatory QA fixtures
Synthetic monotonic candles, alternating candles, missing minutes, late event release, incomplete hourly bar, DST transition, rolling futures contract, and overwritten/revised release. Assert a value at `t` remains invariant if unseen future raw rows are appended, except for explicitly retrospective, non-tradable diagnostics.

## Deliverables
A versioned feature catalog, lineage/schema, data-lag assumptions, as-of join tests, chronological fold manifest, leakage audit and reproducible dataset snapshots/hashes. Fail the pipeline when causal timing cannot be established.

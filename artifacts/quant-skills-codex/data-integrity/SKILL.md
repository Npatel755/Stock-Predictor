---
name: data-integrity
description: Audit historical market data and futures roll adjustments; use when importing, preparing, joining, resampling or validating ES, NQ, MES, MNQ, equities or crypto OHLCV and tick data.
---

# Data Integrity

## Objective
Audit point-in-time inputs and reproducibility. Block trading claims when unresolved data faults invalidate the simulation.

## Procedure
1. Preserve immutable raw files with hash, vendor, acquisition date, timezone, timestamp convention (bar start/end), session calendar, contract symbol, and adjustment metadata.
2. Check monotonic timestamps, duplicates, OHLC consistency (high >= max(open,close); low <= min(open,close)), nonnegative volume, tick alignment, holidays, DST transitions, sessions, missing bars, outliers, and bad ticks.
3. Maintain mapping of raw individual expiries to continuous research series. Document roll dates, roll selection rule, adjustment method, and whether adjusted series may be used for fills (usually no: fills require tradable raw contract prices).
4. For training on ES/NQ and execution on MES/MNQ, explicitly map observation timestamps, sessions, spreads and fills to micro contracts; do not claim micro liquidity equals E-mini liquidity. Avoid using same-bar unavailable prices.
5. Resampling must use only fully completed source bars. Align multiple markets via availability/as-of timestamps; exclude future releases and revised economic data.
6. Partition chronologically and store immutable manifests of TRAIN/VALIDATION/TEST. Preprocessing fit exclusively on training windows (including normalization and feature selection).
7. Generate machine-checkable QA report: coverage, gaps, outliers, rollover events, duplicate count, clock assumptions, unresolved faults.

## Deliverables
Data manifest, QA JSON/Markdown, reproducible transforms, and blocked status if integrity is insufficient. Never interpolate price gaps silently or synthesize tradable quotes.

---
name: quantconnect-lean-replication
description: Replicate QuantConnect LEAN trading algorithms and cross-check engine behavior, data, fills and performance against independent simulations.
---

# QuantConnect LEAN Replication Lab

## Prerequisites
Use public or authorized code and data. Check installed LEAN/CLI version, Docker, data access, and account entitlement before attempting commands. Do not authorize purchases or deploy live strategies.

## Reproduction checklist
1. Pin source URL, code revision, platform/runtime version, Python/C# version, project parameters, initial equity, asset IDs, source dates and time zone.
2. Document `initialize`, `on_data`, scheduled events, trade signals, order types, warmups, slippage, fill/fee models, buying power, and portfolio sizing.
3. For futures: capture `DataMappingMode`, `DataNormalizationMode`, specific mapped symbol vs continuous analysis symbol, expiry/roll behavior and exchange hours. Price adjusted vs tradable/raw series correctly.
4. Build minimal local project or notebook (when permitted) and confirm execution through documented CLI commands. Example commands (version/access dependent): `lean init`, `lean create-project "Project"`, `lean research "Project"`, `lean backtest "Project"`.
5. For any sample trial, compare selected signals, order submits, fill times and prices to a second implementation on *identical data, costs and symbol mapping*. Explain each mismatch.
6. Run fee/slippage stress and delayed-entry controls. LEAN default fills may be optimistic for a given strategy; customize and justify assumptions.
7. Preserve deterministic fixtures for regression tests and export comparison tables. Save failed replications.
8. Mark status `replicated`, `approximately reproduced`, `blocked`, or `not reproduced`; never assert parity without checking trades.

## Cross-engine parity report
Record signal mismatches, timestamp conventions, warmup differences, roll mapping, trade count, realized/unrealized P&L, drawdown conventions and maximum tolerances.

## Research boundary
LEAN's reporting engine is not an independent holdout. Using the same data and rules across two backtest engines checks implementation, **not statistical generalization**.

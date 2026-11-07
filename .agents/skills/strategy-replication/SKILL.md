---
name: strategy-replication
description: Reproduce published or existing trading strategies faithfully before modifying them or claiming transferability to new markets.
---

# Faithful Strategy Replication

## Trigger
Use whenever researching a published strategy, a video tutorial, GitHub algorithm, QuantConnect example, or another agent's backtest.

## Protocol
1. Freeze the source (URL/version, code commit, timestamp, license) and extract a **literal rule specification**: signal construction, trading universe, trading calendar, data normalization, warmup, direction, order types, stop/target logic, execution time, sizing and costs.
2. Explicitly distinguish ambiguities from assumptions. Ask for a source only if essential; otherwise record each assumption and run conservative alternatives on development data.
3. Replicate the original instrument, resolution and date period where authorized data exist. Do not silently replace sources; log substitutions and note non-comparability.
4. Build unit tests for indicators and trade chronology. Compare selected timestamps, signals, orders, fills and P&L against source screenshots/logs or test fixtures.
5. Independently cross-check with an event-driven engine or LEAN if appropriate. Investigate mismatches before exploring enhancements.
6. Separate **faithful reproduction** from **adaptation**: fork the hypothesis ID and mark a different research claim whenever changing the rules, market, costs, or data.
7. Evaluate the adaptation on proper training/validation/untouched test data; original author's reported OOS results do not become your own fresh OOS evidence.

## Output
Replication audit: exact/approximate/not reproduced, mismatch ledger, evidence URLs, source/version, reference trades, data rights, and reproducible commands.

No claims of reproducing a paper/video without code or enough specification to establish parity.

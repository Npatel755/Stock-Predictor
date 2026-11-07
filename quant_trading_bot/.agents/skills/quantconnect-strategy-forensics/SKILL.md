---
name: quantconnect-strategy-forensics
description: Perform source-code-level forensic investigations of individual QuantConnect strategies, papers, notebooks, forum backtests, and LEAN implementations; replicate and stress-test the actual mechanism before adapting it to NQ/ES/MNQ/MES.
---

# QuantConnect Strategy Forensics — from source claim to independently tested hypothesis

## Role
You are an implementation auditor and quantitative investigator. Inspect **how** a published strategy works, **when** its information was available, and **why** its backtest could differ from live outcomes. Never assume an attractive QuantConnect equity curve implies an actionable edge.

## When to invoke
Whenever research discovers a named QuantConnect strategy, algorithm, research notebook, community backtest, or LEAN implementation worth replicating. Pair this skill with `quantconnect-deep-research`, `quantconnect-lean-replication`, `simulator-verification`, `overfitting-defense`, `strategy-memory`, and `cross-contract-transfer` where appropriate.

## Investigation protocol (complete in order)
1. **Source identity and permissions.** Record title, public URL, authors, post/update dates, linked original paper, public code or notebook location, Git SHA where possible, claimed return dates, license, and access status. No inaccessible code may be fabricated.
2. **Market hypothesis.** Write the economic/behavioral mechanism as a one-sentence *falsifiable* statement and describe when it should fail. Identify whether strategy is intraday trend, breakout, reversal, pairs, factor, volatility, or other.
3. **Mechanically reconstruct.** Translate code into unambiguous pseudocode/mathematics: assets, signal formulas, lookbacks, consolidation frequency, warm-up, time zones, overnight position policy, entry/exit, order types, stops, leverage, risk budget, reentry, and order cancellation. Mark unspecific parts UNKNOWN; do not invent them silently.
4. **Trace a concrete trade.** Walk through at least two illustrative timestamps (one entry, one exit), showing which market-data bar became available, the code callback that observed it, what signal was emitted, when the order was placed, the eligible fill price, and the resulting cash/position impact. For actual code, use chronological event trace or small unit fixture.
5. **Audit platform-specific behavior.** Review LEAN semantics for OnData, consolidators, history timestamps, warmups, data subscriptions, timezone, corporate events, data normalization and futures SymbolChangedEvents; inspect the exact version/source when behavior materially changes results.
6. **Audit statistical validity.** Identify train/optimization/test dates, leakage, circular selection, look-ahead, survivorship, publication bias, multiple comparisons, tiny trade sample, unstable thresholds, and benchmark choice. Classify the published test as already observed.
7. **Audit economics and execution.** Calculate executable contract tick sizes/multipliers, commissions, spread, slippage, margin, fill uncertainty, rollover, contract mapping, trading windows, and data-source limitations. Model at least base and stressed costs.
8. **Reproduce as published first.** On legitimately available data run the closest faithful LEAN reproduction, version-lock configs, save event/trade logs, compare counts and fills against the original. Explain differences rather than tune to match the reported P&L. If not runnable, provide static review and mark UNVERIFIED.
9. **Independent reasonableness tests.** Implement simplified benchmark/negative controls; perturb parameters, drop subperiods, vary entry delay/cost and roll assumptions, inspect yearly and regime returns. Label all dates used to shape the idea as training/consumed.
10. **Futures hypothesis transfer.** Separately propose an NQ/ES-to-MNQ/MES adaptation under correct contract economics. Do NOT blindly copy parameters from stocks, ETFs, crypto, or commodity futures. Specify testable difference vs parent and run TRAINING-only tests first.
11. **Decision and memory.** Save source and forensic cards, code hashes, deviations, hypotheses, failures, and evidence of transferability. Tag APPROVED_FOR_RESEARCH, NEEDS_DATA, REJECTED, or UNVERIFIED—not PROFITABLE solely from sourced results.

## Mandatory stop / escalation conditions
- If the source is paywalled, private, confidential, or otherwise unauthorized: stop extraction, record ACCESS_BLOCKED, use permitted public descriptions only.
- If required LEAN CLI/data/MCP privileges do not exist: do not claim reproduction; use static audit, note required access and legal alternatives.
- Before ANY purchase, paid cloud job, external publication, private repo modification or account change: request explicit user approval.
- NEVER connect a brokerage, initiate live trading, deploy a strategy, or place an order without specific user permission.
- Do not use validation or final test results for repeated optimization. Once touched for design, document contamination and replace the holdout rather than pretending independence.

## Outputs
For EACH audited strategy, write:
- `research/quantconnect/strategy_audits/<slug>.md` with full ten-step audit and timestamped link/citation table.
- `research/quantconnect/strategy_audits/<slug>.json` following `templates/forensic-card.json` (null for unknown fields; never fabricated values).
- `research/quantconnect/reproduction_reports/<slug>.md` with exact status: NOT_RUN / FAILED / PARTIAL / REPRODUCED, and what was compared.
- `research/quantconnect/experiment_queue.md` with preregistered training-only hypotheses and stop criteria.

Read `references/forensic-protocol.md` and `references/futures-transfer-audit.md`. Treat them as required checklists, not optional suggestions. For wide searches, coordinate with `quantconnect-deep-research`.

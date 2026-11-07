---
name: research-orchestrator
description: Coordinate repeatable multi-skill quantitative trading research, experiment registries and objective go/no-go reporting; use when Devin is tasked with full strategy research or 10000+ candidate evaluations.
---

# Research Orchestrator

## Objective
Orchestrate an auditable research program, not an endless quest for a positive backtest.

## Workflow
1. Read project repository and avoid disrupting running jobs. Collect confirmed market/account requirements and identify missing rule evidence.
2. Invoke data-integrity before strategy research. Freeze split manifest and initialize experiment registry.
3. Invoke strategy-discovery to register hypotheses and training-only parameter search. Invoke overfitting-defense on every selection protocol.
4. Use backtesting-engine to cross-check fills and accounting, execution-optimization to stress costs, and market-regime-analysis to diagnose concentration.
5. Use walk-forward-validation for forward-like evaluation; use risk-management for account breaches; use portfolio-construction only when several independent strategies exist.
6. Select finalists under precommitted criteria with a limited validation review; freeze code, config and hashes; run final TEST once.
7. Publish report showing every strategy family attempted, number of trials, best TRAIN/VALIDATION/TEST (not hiding failures), sensitivity, uncertainty, account breach rate, market caveats and outstanding blockers.
8. Define status: REJECTED, RESEARCH-ONLY, PAPER-TRADE-CANDIDATE, or LIVE-REVIEW-REQUIRED. Never auto-trade, pay fees or place orders without explicit user permission.

## Reporting contract
Include assumptions, data provenance, leakage safeguards, number of trials, fees, execution fidelity, results separated by chronological partition, weakest regimes, drawdown floor simulations, and exact reasons for recommendation.

## Mandatory stop rule
No candidate passes predefined gates -> report no credible edge. Do not mine protected data, invent results or keep searching until luck makes something look profitable.

## Learning and external-source dispatch (expanded pack)
Before launching a new candidate search, use `strategy-memory`, `research-prioritization`, and `evidence-provenance`. For external ideas dispatch to `research-source-ingestion` and the matching specialist (`youtube-strategy-research`, `quantconnect-deep-research`, `academic-paper-mining`, or `public-strategy-mining`). Route candidates through `strategy-replication`, `strategy-decomposition`, `signal-ablation`, and `hypothesis-transfer`; require `quantconnect-lean-replication` or `pinescript-strategy-porting` as needed. Store failed tests using `failure-learning`. Compare alternatives through `champion-challenger`. Treat previously viewed holdouts as consumed; protect a genuinely new holdout and seek prospective paper evidence.

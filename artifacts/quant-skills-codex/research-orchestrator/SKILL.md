---
name: research-orchestrator
description: Coordinate repeatable multi-skill quantitative trading research, experiment registries and objective go/no-go reporting; use for multi-stage trading-strategy research or large training-only configuration searches.
---

# Research Orchestrator

## Objective
Orchestrate an auditable research program, not an endless quest for a positive backtest.

## Scope and discovery

Preserve the user's existing split boundaries, research budget, authorization and project instructions. This skill does not authorize new holdout evaluations, purchases, live connections, messages, trades or deployments. Never relabel observed data as untouched. Parameter fitting, feature selection and strategy development use training data only; validation may apply only a ranking rule and shortlist frozen beforehand. If the relevant validation/test period has already been used, record that limitation and require fresh forward observations for independent confirmation.

Load sibling skills only for the current work. These installed siblings are available in the same parent directory:

- Data and contract provenance: [data-integrity](../data-integrity/SKILL.md), [futures-contract-lifecycle](../futures-contract-lifecycle/SKILL.md), [cross-contract-transfer](../cross-contract-transfer/SKILL.md).
- Strategy development and evidence: [strategy-discovery](../strategy-discovery/SKILL.md), [walk-forward-validation](../walk-forward-validation/SKILL.md), [overfitting-defense](../overfitting-defense/SKILL.md), [negative-control-testing](../negative-control-testing/SKILL.md), [market-regime-analysis](../market-regime-analysis/SKILL.md), [economic-event-research](../economic-event-research/SKILL.md).
- Simulation and risk: [backtesting-engine](../backtesting-engine/SKILL.md), [simulator-verification](../simulator-verification/SKILL.md), [execution-optimization](../execution-optimization/SKILL.md), [risk-management](../risk-management/SKILL.md), [risk-of-ruin-monte-carlo](../risk-of-ruin-monte-carlo/SKILL.md), [portfolio-construction](../portfolio-construction/SKILL.md).
- Forward operation: [paper-trading-reconciliation](../paper-trading-reconciliation/SKILL.md), [deployment-safety-monitoring](../deployment-safety-monitoring/SKILL.md).

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
If no candidate passes the predefined gates, report no credible edge. Complete an explicitly requested finite training-search budget even when early candidates fail or succeed; do not stop merely to obtain a favorable result. Never extend a protected validation/test stage or change candidates from its outcomes. Stop a run for missing required data, an unrecoverable execution error, an explicit resource limit, or user instruction; preserve resumable checkpoints.

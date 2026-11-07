---
name: failure-learning
description: Investigate unsuccessful trading strategies with structured root-cause analysis and turn failures into testable training-only hypotheses.
---

# Failure Learning: Diagnose Before Modifying

## Trigger
Use after a losing, unstable, invalid, or suspiciously profitable backtest; also when previously attempted ideas keep resurfacing.

## Workflow
1. Retrieve the full run including code, trades, order events, data issues, metrics, assumptions, and provenance. Determine whether failure was **strategy**, **data**, **simulator**, **cost model**, **implementation**, or **risk rule**.
2. Reproduce the failing run bit-for-bit if feasible. Fix correctness bugs before comparing strategy variants.
3. Slice diagnostics by instrument, regime, session, direction, day of week, volatility, contract roll, event days, and holding time. Require minimum sample size and mark exploratory findings.
4. Quantify cost drag, rare-event dependence, maximum adverse excursion, instability, and parameter cliffs. Check whether apparently positive variants differ only because of chance.
5. Write a root-cause narrative with `confirmed`, `likely`, and `unknown` labels; list alternative explanations and contradictory evidence.
6. Propose **one simple, falsifiable** remedy per independent hypothesis, pre-register expected direction, training-only experiment, and stop condition.
7. Save negative results and lessons to `strategy-memory` so they inform idea selection without contaminating protected holdouts.

## Failure report
- `run_id`, classification, reproducibility, failed assumption
- Evidence: trades, dates, costs, relevant charts, tests
- Hypothesis and controlled next experiment; uncertainty and rejected alternative causes
- Proposed disposition: fix engine / revise on training / retire / defer for more data

Never create a patch solely because it improves an already-inspected validation or test equity curve.

---
name: research-prioritization
description: Use the experiment ledger and external evidence to prioritize novel, testable trading research rather than endlessly tuning old ideas.
---

# Research Prioritization

## Operating method
1. Review strategy-memory, open bug reports, available data, current champions, and source evidence before proposing a search.
2. Group ideas by *mechanism* and failure cause. Avoid proposing parameter variants that duplicate an already-exhausted family.
3. Score the candidates (0-3 per criterion): plausibility, source independence, market relevance, data feasibility, execution feasibility, novelty relative to registry, and expected information gain. Subtract complexity, data leakage risk and estimated compute expense.
4. Select a **diverse bounded batch** of experiments with pre-registered hypotheses, primary metrics, failure criteria, time budget, and validation budget.
5. Allocate initial resources to simulator/data correctness and cheap falsification tests; reserve costly event-driven testing for credible finalists.
6. Update research priorities using **training and controlled research evidence**, not repeatedly inspected holdouts. If a test set is exposed, document the loss of independence.
7. End the batch with a research memo: what was learned, next three highest-information experiments, and what not to repeat.

## Hard stop
If no candidates meet pre-specified training/validation evidence standards, report that none pass. Do not relax the threshold after seeing results without explicitly creating a new research phase.

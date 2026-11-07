---
name: strategy-memory
description: Remember and retrieve past strategy hypotheses, parameters, experiments and failures before starting new quantitative trading research.
---

# Strategy Memory: Persistent Lessons From Past Experiments

## When to use
At the start and end of **every** strategy experiment; whenever asked to find an existing idea or improve one that was previously tested. This is persistent *project knowledge*, not an update to the AI model's weights.

## Procedure
1. Inspect the existing experiment tracker/DB first; adapt to it, rather than creating an incompatible parallel tracker. If absent, create an append-only JSONL or SQLite registry under `research/strategy_memory/`.
2. Store separate **hypothesis**, **implementation**, **run**, **result**, and **lesson** records. A strategy can have many runs; never overwrite old runs with better outcomes.
3. Record immutable `strategy_id`, `parent_id`, `hypothesis`, `family`, `market`, `timeframe`, `data_snapshot`, dataset hashes, train/validation/test roles, code commit, parameter hash, trading-cost model, metrics, timestamps, failure diagnosis, and decision.
4. Tag strategies by signal mechanism, hold duration, session, regime, and trade overlap; search near-duplicates before proposing new work.
5. Distill transferable lessons (e.g., 'sensitivity to open-session spread') with pointers to exact run IDs; distinguish observations from proven causes.
6. Query memory before new research, and create **new training-only hypotheses** based on lessons. Never tune to remembered TEST outcomes. A test set revealed in an earlier experiment is permanently **consumed**, not future 'unseen data'.
7. Version the schema, back up records, and provide a readable `lessons.md` summary plus machine-readable history.

## Output contract
Return: prior related strategies, top findings **including failures**, duplicate-warning, proposed falsifiable follow-up, experiment ID, and evidence links.

## Guards
No fabricated experiments; no cherry-picking; no data leakage through memory. Past test results may be disclosed for audit but must not guide further optimization against the same test period.

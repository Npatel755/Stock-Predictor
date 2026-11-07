---
name: quantconnect-deep-research
description: Thoroughly investigate QuantConnect strategy tutorials, published research, community posts, public notebooks, LEAN implementation details, and available MCP tools; build a traceable research dossier before testing futures strategies.
---

# QuantConnect Deep Research — evidence-first research pipeline

## Activation
Use this skill for broad or targeted research on QuantConnect strategies, datasets, forum discussions, public notebooks, LEAN examples, or QuantConnect tooling. For a single specific strategy's source-to-trade audit, invoke **`quantconnect-strategy-forensics`**. For executable replication, invoke **`quantconnect-lean-replication`**. For experiment retention, invoke **`strategy-memory`**.

## Objective
Research QuantConnect as a knowledge ecosystem, NOT a guaranteed-profit strategy repository. Find independently testable market mechanisms and learn from successful, unsuccessful, and incomplete examples. Favor high-fidelity replication, transparency, and contamination-aware futures testing over published return claims.

## Grounded research surfaces
Read `references/quantconnect-research-map.md` for verified entrypoints and research queries.

1. QuantConnect **Strategy Library**: catalog tutorials and their underlying academic references; prioritize relevant futures and intraday mechanisms.
2. **QuantConnect Research public GitHub notebooks**: read actual notebook code and outputs, repository commits, limitations, and data provenance.
3. QuantConnect **Research articles** and **community forum**: study source discussions, code, known bugs, updates, and critique; separate user claims from evidence.
4. **LEAN source and CLI**: inspect event ordering, indicator warm-up, fill/fee/slippage models, data mapping, normalization, contract selection, and rollover handling.
5. **QuantBook Research Environment**: investigate mechanisms with statistical tests before event-driven backtests when authorized and available.
6. **Original papers / primary studies**: trace the study from each published tutorial, compare methodology, market, time period and research assumptions.
7. **QuantConnect Research Pipeline / Agents / MCP**: discover which official features can be used in the CURRENT environment. Do not assume access or paid entitlement. QuantConnect MCP can connect approved agent clients to the API but must be configured and authorized.

## Autonomous research cycle
1. **Scope and source plan.** Decide target instruments (ES/NQ research, MES/MNQ execution), resolution, hold period, time zones, predeclared search terms, budget, and availability of platform/data. Maintain search log with date and source inventory. Do not claim exhaustive search if coverage is partial.
2. **Broad evidence inventory.** Find diverse strategy families (breakout, momentum, trend, reversal, intraday seasonality, volatility, cross-asset, event-sensitive), including unprofitable cases. Deduplicate different articles deriving from the same paper/underlying code.
3. **Rank for investigation only.** Prioritize by testability, plausible market mechanism, data availability, source reliability, transferability to futures, and replication cost. Published Sharpe or P&L alone never qualifies an idea.
4. **Forensic deep-dives.** For each promising source invoke `quantconnect-strategy-forensics`, recording exact signal formulas, entry/exit mechanics, risk controls, data timestamps, and source-level ambiguity.
5. **Reproduce unchanged first.** Implement and compare LEAN/backtest behavior on the originally specified asset and sample whenever legally and technically possible. Keep reproduction separate from adaptations. If a credible reproduction is impossible, clearly label **UNVERIFIED**.
6. **Translate to user instruments.** Adapt the *hypothesis*, not the historical equity curve. For actual MNQ/MES orders use correct instrument specifications, tick economics, executable contracts, roll schedule, costs, and broker/funded rules. Use NQ/ES as signal or proxy data only if justified.
7. **Protect research independence.** Published results and all viewed periods are already public/touched information, not independent holdouts. Freeze experiments on training data; use bounded validation and preserve genuinely unseen test data. Never mine a final holdout to optimize.
8. **Record learning.** Write source cards, exact reproductions, deviations, negative results, near duplicates, failure reasons, and research-derived hypotheses to persistent strategy memory.
9. **Report precisely.** Publish a coverage log, reproducibility status, mechanism ranking, counterevidence, experiment backlog, and the next low-cost test. Disclose what could not be accessed or run.

## Mandatory scientific and safety boundaries
- Do not attribute performance to a strategy without the original source and scope; distinguish author-reported, self-replicated, validation, paper, and live results.
- Do not invent inaccessible source code, missing data, fee schedules, paywalled studies, or QuantConnect access.
- Never bypass authorization, paywalls, datasets licensing, ToS, or source-code licenses. Ask before ANY purchase, paid cloud operation, broker connection, deployment or live order; never execute live orders without explicit transaction-specific authorization.
- If official MCP/CLI unavailable (tier, auth, permissions, Docker, data), use public research and local independent analysis and label execution unperformed.
- Never use adjusted continuous-futures price levels as executable fill prices. Trade the *mapped individual contract* and model all roll costs.
- A large search is a hypothesis-generation process; it does not establish future profitability.

## Required deliverables
- `research/quantconnect/coverage_log.md`: queries, dates, examined links and access status.
- `research/quantconnect/source_registry.jsonl`: one machine-readable card per unique source with original references and commit/version.
- `research/quantconnect/strategy_audits/`: detailed implementation forensics on selected ideas.
- `research/quantconnect/reproduction_reports/`: reproduction attempts with pass/fail and engine differences.
- `research/quantconnect/quantconnect_dossier.md`: ranked mechanisms, counterevidence, data/access constraints, risk notes and bounded training-only next experiments.

If the existing project uses another research storage convention, adapt paths without deleting prior records. See `quantconnect-strategy-forensics/references/forensic-protocol.md` for auditing detail.

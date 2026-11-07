# Devin Quant Trading Skills — Complete Research & Learning Pack

**43 repository skills**: the prior 36 research skills plus 7 targeted market-data, statistical-audit, and deployment-parity skills. These are instruction files, **not** trained model weights, backtesting code, purchased datasets, or guaranteed-profit systems.

## Added in v5 (7 additional skills)
- `orderflow-microstructure`
- `statistical-evidence-auditor`
- `trade-edge-attribution`
- `intraday-session-clock`
- `point-in-time-feature-engineering`
- `adversarial-stress-lab`
- `batch-streaming-signal-parity`

These are specialized additions, not replacements for the earlier 36. Use `intraday-session-clock` and `point-in-time-feature-engineering` for basic data correctness; `statistical-evidence-auditor` for independent credibility checks; and only use `orderflow-microstructure` when the actual dataset contains the requisite quote/order-book fields. See `research_skillpack/NEW_SKILLS_RESEARCH.md`.

## Install
Extract this archive **at the repository root** so the files appear under `.agents/skills/<skill-name>/SKILL.md`. Preserve existing files and review conflicts; do not indiscriminately overwrite existing skills. Commit changes and ask Devin to confirm discovery in its own environment. Current public documentation describes `@skills:<skill-name>` as an explicit invocation syntax, but confirm it works in your Devin version.

**Never assume this archive is installed into Devin just because you downloaded it.** It must be added to a repository Devin can access.

## Added learning/research skills (18)
- `academic-paper-mining`
- `champion-challenger`
- `cross-source-triangulation`
- `evidence-provenance`
- `failure-learning`
- `hypothesis-transfer`
- `pinescript-strategy-porting`
- `public-strategy-mining`
- `quantconnect-deep-research` (expanded with source discovery, MCP-aware research, and reproducibility)
- `quantconnect-strategy-forensics` (new source-to-trade audit and futures-transfer protocol)
- `quantconnect-lean-replication`
- `research-prioritization`
- `research-source-ingestion`
- `signal-ablation`
- `strategy-decomposition`
- `strategy-memory`
- `strategy-replication`
- `youtube-strategy-research`

## Original 18 retained
- `backtesting-engine`
- `cross-contract-transfer`
- `data-integrity`
- `deployment-safety-monitoring`
- `economic-event-research`
- `execution-optimization`
- `futures-contract-lifecycle`
- `market-regime-analysis`
- `negative-control-testing`
- `overfitting-defense`
- `paper-trading-reconciliation`
- `portfolio-construction`
- `research-orchestrator`
- `risk-management`
- `risk-of-ruin-monte-carlo`
- `simulator-verification`
- `strategy-discovery`
- `walk-forward-validation`

## Recommended order of operations
1. `simulator-verification` + `data-integrity` — make sure the engine and data are not lying.
2. `strategy-memory` + `failure-learning` — inventory prior experiments, including failures, and mark all touched holdouts as consumed.
3. `research-prioritization` + `evidence-provenance` — plan bounded research on independent evidence.
4. `quantconnect-deep-research`, `youtube-strategy-research`, `academic-paper-mining`, `public-strategy-mining` — source many distinct mechanisms, not repetitive indicator tweaks.
5. `strategy-replication` and `quantconnect-lean-replication` — recreate the idea before modifying it.
6. `strategy-decomposition`, `signal-ablation`, `hypothesis-transfer` — find useful components and transfer hypotheses to the actual executable contract.
7. `overfitting-defense`, `walk-forward-validation`, `negative-control-testing` — estimate how likely the edge is to generalize.
8. `risk-management`, `risk-of-ruin-monte-carlo`, `execution-optimization` — enforce real funded-account and tradability constraints.
9. `champion-challenger` and `paper-trading-reconciliation` — compare prospectively before recommending real-money use.

## Learning from previous strategies safely
The pack writes durable experimental knowledge to the repo, not the AI model's parameters. Store code commits, configs, result records, negative results, and source provenance. **A test dataset that has influenced research decisions is no longer fresh**; never revisit it repeatedly to engineer a winning result. Use a new forward holdout or genuine prospective paper evidence.

## QuantConnect usage
The deep-research skill includes an annotated source map for Strategy Library, Research notebooks, LEAN docs, futures mapping, slippage, fill models, and LEAN CLI. Local LEAN CLI workflows may require Docker, licensed datasets, and an eligible paid organization plan. Do not automatically purchase or run costly cloud resources. Learn rules from examples and independently replicate them.

## YouTube usage
YouTube video research uses authorized available content, user-provided transcripts, timestamps and explicit provenance. The official captions download API is **not** an unrestricted transcript endpoint; its access permissions limit what can be retrieved. Never assume Devin can watch or transcribe every video automatically, or bypass rights/restrictions.

## Research artifacts
`research_skillpack/templates/` contains JSON starter schemas for source cards, strategy cards and experiment runs. Adapt to the existing project ledger rather than creating two sources of truth. `research_skillpack/SOURCES.md` lists primary URLs.

## Safety and deployment
No skill can guarantee profitability. Realistic fills, commissions, sample uncertainty and legal/account restrictions matter. Skills do not authorize live orders, purchases, new paid subscriptions, sharing account credentials, or violating platform terms. Confirm LucidFlex's currently applicable rules directly in the user's account/documents before modeling them as definitive.

## QuantConnect forensic workflow (v4)
Use `@skills:quantconnect-deep-research` for broad source mining and `@skills:quantconnect-strategy-forensics` when a specific strategy needs a deep code-level audit. Each audited source gets a dated source record, rule reconstruction, trade trace, reproducibility status, and independent test hypothesis. QuantConnect MCP/LEAN access is optional, requires actual availability, and does not grant permission for paid actions or live orders.

## Additional verification before paper deployment (v5)
`adversarial-stress-lab` explores deterministic market and infrastructure failures; `batch-streaming-signal-parity` checks bar-by-bar signal equivalence. A no-divergence result is a software integrity check, not evidence of profitable edge.

---
name: public-strategy-mining
description: Find, classify, and critically evaluate public trading strategies from open research, repositories, broker education, and credible websites.
---

# Public Strategy Mining

## Goal
Build a provenance-rich **idea library**, not a collection of advertised backtest returns.

## Sources
Academic papers, QuantConnect Strategy Library, official platform docs, reputable open-source repositories, futures exchange research, publicly accessible articles and forums, and authorized video notes. Prefer primary implementations and authors over summaries.

## Method
1. Define the target market/horizon and search query; record date, search terms, inclusion rules, and publication-time availability.
2. For each candidate capture URL/DOI/repository commit, author, publication date, license, asset, original timeframe, thesis, exact signal/exit/risk rules, data period, costs, train/test policy, and limitations.
3. Classify every claim as `documented`, `replicated`, `hypothesized`, or `unverifiable`. Never claim an edge because the author reports a profit.
4. Deduplicate ideas using mechanism + rules + code hash, not title alone. Link derivative ideas to original sources.
5. Filter for execution feasibility on target markets (MES/MNQ vs ES/NQ). Include sessions, ticks, commissions, liquidity, exchange calendars, roll logic, and leverage.
6. Produce minimal, falsifiable, *training-only* candidate specs. Send promising candidates to `strategy-replication`, then `overfitting-defense`.
7. Obey copyrights, paywalls, licenses, rate limits and access permissions; do not misrepresent inaccessible material as reviewed.

## Deliverable
A sourced discovery table containing hypothesis, mechanism, source, assumptions, duplicate cluster, feasibility, evidence rating, and proposed controlled experiment.

---
name: academic-paper-mining
description: Extract reproducible trading hypotheses from academic papers, preprints and technical reports with careful statistical scrutiny.
---

# Academic Paper Mining

## Inputs
Publisher websites, SSRN, arXiv, institutional working papers, DOI-indexed literature, and references listed in papers; obey access terms.

## Procedure
1. Build a query set: target asset (futures, equity index), effect class (momentum, reversals, volatility), timeframe, signal horizon, and publication date range.
2. Record DOI/title/authors/year/version, sample period, asset universe, data availability, observation timing, transaction costs, implementation details, and supplementary code/data licenses.
3. Distinguish peer-reviewed work, preprints, replications, and commentary. Record corrections, errata and later contradictory findings when discoverable.
4. Translate methods to an executable mathematical specification, including transformations, lag convention, measurement units, lookbacks, training windows, and positioning rules.
5. Check research threats: multiple hypotheses, post-publication decay, look-ahead, survivorship bias, future revisions, unrealizable fills, and capacity.
6. Replicate **the original claim first** on authorized data when feasible; mark non-comparable datasets. Then create a separate, training-only adaptation for the user's target market.
7. Save an annotated `paper_card`, reproducibility status, derived code commit, and result hashes in source registry.

## No shortcut
A statistically significant paper about daily equities does not establish an intraday index-futures edge. Do not quote claimed alpha without its assumptions and date context.

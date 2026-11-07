---
name: cross-source-triangulation
description: Cross-check trading ideas from QuantConnect, YouTube, papers, forums and GitHub without counting reposted claims as independent evidence.
---

# Cross-Source Triangulation

## Mission
Find agreement and disagreement on *mechanisms and implementation facts*, not just bullish backtest claims.

## Process
1. For a proposed idea, find primary sources: original paper, reference implementation, exchange specs, current platform docs, and independent replications when possible.
2. Create a claim graph linking each source to its primary origin. Identify reposts, derivative code, tutorial adaptations, and reused datasets.
3. Separate questions: Does the signal exist? Can it be observed causally? Can it be traded? Is it robust net of costs? Does it transfer to MNQ/MES?
4. Compare timestamp conventions, market regimes, train/test periods, contract mappings, fees, and order fills. Where sources conflict, note both and perform a targeted reproducible check.
5. Discount evidence originating from the same backtest or dataset; do not raise confidence for duplicated videos/blogs describing a single result.
6. Summarize strongest supporting observation, strongest contradictory evidence, unresolved assumption, and cheapest *training-only* disconfirming experiment.
7. Write findings back to `evidence-provenance` and `strategy-memory`; never convert multiple publicity claims into statistical significance.

## Output
`claim_matrix.md` with claim, source links, common ancestor, agreement/conflict, evidence quality and replication plan.

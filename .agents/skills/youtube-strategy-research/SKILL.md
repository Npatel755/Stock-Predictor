---
name: youtube-strategy-research
description: Learn trading ideas from YouTube videos using lawful accessible transcripts, exact timestamps, verification and reproducible backtests.
---

# YouTube Strategy Research and Evidence Extraction

## Purpose
Analyze publicly described trading ideas, tutorials, interviews and educational videos and convert useful claims into falsifiable research specs. **Viewing video content is not evidence of profitability**.

## Authorized intake
- Discover relevant videos via approved search or YouTube API with permitted access; use title, creator, date, URL, description, chapters and public comments as low-confidence leads.
- Use transcripts/captions only when they are available through permitted, authorized methods (e.g., user-provided transcripts, rights-holder-permitted files, accessible manual transcript view where authorized). The official `captions.download` API requires permission to edit the video; do **not** assume that it retrieves arbitrary creators' transcripts.
- If no legal transcript is accessible, rely on available description/chapters and clearly label the source incomplete. Ask for a transcript if needed. Never evade restrictions, scrape in violation of terms, or download protected audiovisual content.
- For video charts, distinguish genuinely disclosed order rules from retrospective hand-drawn examples; do not infer exact parameters from screenshots alone.

## Investigation protocol
1. Log URL, channel, publish date, video length if available, version, speaker's relevant incentives, affiliate or course promotion, and every referenced market/timeframe.
2. Extract claims with **timestamps** and paraphrases: rules, indicators, entry and exit, position sizing, stop, session, costs, advertised metrics, and missing implementation details.
3. Separate `directly stated`, `reasoned inference`, `marketing claim`, and `unknown`; keep conflicting statements visible.
4. Seek independent source code, docs, academic work or exchange data to corroborate. Flag cherry-picked screenshots, repainting, hindsight, unrealistic fills and omitted costs.
5. Draft deterministic, testable strategy rules with assumptions and a minimal implementation. Register as *unverified hypotheses*; run `strategy-replication` and `overfitting-defense` before any evaluation claim.
6. Write a short `source_card` with video link, timestamp anchors, reliability, copyright/access note, and next experiment.

## Failure condition
When precise trading logic is unavailable, record a research lead rather than inventing a strategy or fabricating transcript content.

# Shared research coordination — 2026-11-07

User explicitly requested Codex work alongside Antigravity Gemini and research another 200,000 strategies, reporting how many have positive net P&L and drawdown strictly below $2,000.

Codex observed Gemini's existing `training_search_500k_v1` job running and will not change its source, process, progress, database, reports, or frozen manifest. Antigravity's window closed before an agent message could be submitted; this file is a shared handoff, not evidence that Gemini acknowledged a message.

Codex owns `scripts/collaborative_200k.py`, `runs/collaborative_200k_v1`, and `reports/COLLABORATIVE_200K*`. Its 200,000 active configurations exclude all 370,000 historical configurations plus all 500,000 already reserved by Gemini, including unexecuted ones. Please exclude this new frozen manifest from any further Gemini search.

Both agents must preserve the fixed splits. This request authorizes TRAIN-only research; no new validation/test access, protected outcome inspection for development, or live execution. Codex's main reported count uses positive aggregate training net and all cash/closing/intrabar drawdowns strictly below $2,000. Additional quality gates and permanent risk locks are reported separately. Net sums four annual training accounts; drawdown is worst annual fold, not continuous four-year drawdown.

Suggested Gemini contribution: independently audit the completed Codex manifest/count/report using only this run's saved TRAIN artifacts; write comments to `reports/GEMINI_COLLABORATIVE_200K_REVIEW.md`. Do not rerun candidates or edit frozen sources/manifests. No Gemini review is claimed unless actually received.

## Static scheduler finding for Gemini's 500k job

Codex noticed `training_search_500k.run()` schedules `for lookback in sorted(LOOKBACKS)`, but its generated `opening_range` cases use `OPENING_LOOKBACKS=(15,30,45,60,75,90,105,120)`, which have no overlap with ordinary `LOOKBACKS=(8,12,16,24,32,48,64,96)`. On the currently observed source, this appears to leave all 50,000 opening-range cases unscheduled, so the full-budget guard should fail at 450,000 rather than publish 500,000. This is a static code finding, not a claim about final runtime results. Please independently verify and address through a separately recorded, hash-audited orchestration correction without changing candidate rules or rerunning completed cases. Codex has not changed your running job, protocol, or frozen source. Codex's separate200k scheduler reads all distinct horizons from its own frozen configuration database, and its coverage test checks all eight opening horizons.

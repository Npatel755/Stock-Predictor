# sizing_1 — does the $150 per-trade risk budget help or hurt the intraday paper ledgers? (pre-registered 2026-11-09)

## Motivation
All intraday paper ledgers show 0 trades since 2026-11-06 because the research engine sizes by stop risk and refuses any entry whose
1-contract stop risk (`stop_atr × ATR × $2 + fees/slippage`) exceeds `risk_per_trade = $150`; at the current 15-min NQ ATR (≈110–130 pts) every
sleeve is blocked. The same rule shaped every training backtest. Question: on 2010–23, what do the trades that this rule blocks look like?
If they are no worse than ordinary trades and the drawdown stays under the $2,000 floor, an "always one contract" version is a legitimate
challenger; if they lose or concentrate the drawdown, the current zero-trade state is the rule working as intended.

## Data and separation
MNQ/MES 1-min → 30/60/15-min bars, 2010-01-01 … 2023-12-31 (train split only). 2024–25 and 2026 are not loaded. Same costs/engine as the
QUAD_2 / ARCHC_2 / ALLWEATHER_1 pilots (fixed engine, 1 micro contract, engine defaults).

## Candidates (frozen, as deployed on paper)
C1 `ag_quad_v2`   — AG_MORN30, AG_TRD60Q (both backwardation-filtered), AG_TRD30PM, AG_MES_TRD30; strict 1-contract router.
C2 `ag_arch_c_v2` — Crabel 15m open-drive, MNQ 30m trend lb16, MNQ 60m trend lb12; backwardation filter; strict 1-contract router.
C3 `ag_all_weather_v2` — its two sleeves, backwardation filter.

## Variants
V0 champion: `risk_per_trade = max_open_risk = $150` (engine default).
V1 one-contract-always: `risk_per_trade = max_open_risk = $1e9`, `max_contracts = 1`; **every other gate unchanged** (daily loss, hard drawdown,
funded $2k lock, consecutive-loss lockout, flat 15:55, participation cap). Only the stop-risk sizing refusal is removed.

## Metrics (per candidate)
net, trades, $/trade, positive years (of 14), 2010–19 net, max single-year share, closed daily-equity max DD, by-sleeve net;
**added trades** = V1 trades whose (sleeve, entry_ts) is absent from V0: count, net, $/trade, worst trade, share of V1 DD days that contain an added trade;
**stop-risk buckets**: V1 trades grouped by 1-contract stop risk (<$150, $150–250, $250–400, >$400): count, $/trade, win rate;
1-year block-bootstrap (20-day blocks, 2,000 paths) P(DD ≥ $2,000) for V0 and V1.

## Controls
P1 (added-trade placebo): 20 random subsets of V1 trades with the same count as the added set → distribution of subset net; report the added
set's percentile. P2: same with same-count random *days*.

## Pre-registered decision
V1 of candidate Cx is a deployable challenger (as `<key>_1c`, paper only, beside the original) iff: V1 net > V0 net, V1 closed DD ≤ $2,000,
V1 positive years ≥ V0, added-trade net > 0, and added-trade net ≥ P1 median. Otherwise V1 is recorded as rejected and the $150 budget stands
(the paper ledgers' current zero-trade state is then the rule protecting the floor, not a missed edge). No parameter is tuned; one comparison per
candidate; no look at 2024–26. Deployment is my judgement call under Nick's standing paper-discretion rule; live routing is never implied.

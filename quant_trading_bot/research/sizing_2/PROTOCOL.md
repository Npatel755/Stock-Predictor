# sizing_2 — intermediate stop-risk budget $250 (pre-registered 2026-11-09, after sizing_1)

## Motivation
sizing_1 (reports/SIZING_1_TRAINING.md) showed on 2010–23 that the trades blocked by the $150 budget with 1-contract stop risk in $150–250 are better
than the candidates' average trade (Quad $39/tr on 166, Arch C $35/tr on 98, All-Weather $63/tr on 39) while the >$250 trades are few and negative
(Quad 18, Arch C 6, All-Weather 0). The unbounded V1 failed for Quad (DD $2,061) and Arch C (one fewer positive year). The obvious intermediate —
a $250 budget — is a parameter chosen after seeing sizing_1's buckets, so it gets its own single pre-registered comparison here; nothing else is varied.
Multiplicity: this is the second sizing comparison on the same training split for these candidates; it is recorded as such.

## Data and separation
Same as sizing_1: MNQ/MES train split 2010-01-01 … 2023-12-31 only; 2024–26 not loaded.

## Candidates (frozen): ag_quad_v2, ag_arch_c_v2, ag_all_weather_v2 (as deployed).
## Variant V2: `risk_per_trade = max_open_risk = $250`, max 1 contract, every other gate unchanged. Compared with V0 ($150, deployed) and V1 (∞, sizing_1).

## Metrics: as sizing_1 (net, trades, $/tr, positive years, 2010–19 net, max-year share, closed DD, by-year, added trades vs V0 with the P1/P2 placebos,
stop-risk buckets, 1-year block-bootstrap P(DD ≥ $2,000)).

## Pre-registered decision
V2 of candidate Cx is a deployable challenger (`<key>_r250`, paper only, beside the original) iff: V2 net > V0 net, V2 closed DD ≤ $2,000 and ≤ V0 DD + $100,
V2 positive years ≥ V0, added-trade net > 0 and ≥ P1 median, P(DD ≥ 2k, 1y) ≤ V0 + 1 pt. For All-Weather (whose V1 already passed and is on paper as
`_1c`) V2 is reported only, not deployed — V1 is its challenger. Deployment of any passer is Devin's judgement under Nick's paper-discretion rule.
No 2024–26 look. No further budget values will be tried after this round.

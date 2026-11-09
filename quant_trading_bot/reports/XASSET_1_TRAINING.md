# xasset_1 — cross-asset (ZN / 6E / CL) information for MNQ, training 2010–2023 (2026-11-09)

Protocol research/xasset_1/PROTOCOL.md (pre-registered before download). Data: Databento GLBX.MDP3 ohlcv-1m continuous ZN.c.0 / 6E.c.0 / CL.c.0
Jun 2010–Dec 2025, $45.94 (approved; data/market/crossasset, gitignored). NQ 2010–18 + MNQ 2019–23 1-min; features from completed minutes, lagged one
bar; roll minutes excluded. Scripts: scripts/xasset_1_t1.py, scripts/xasset_1_t2.py. Validation 2024–25 untouched; 2026 never loaded.

## T1 — predictive test (36 channel × lag × horizon cells; strongest per channel)
| channel | lag/horizon (min) | t | top–bottom decile spread (MNQ ticks) | years same sign | qualifies (|t|>4, spread>5.4 ticks, ≥10 yrs) |
|---|---|---:|---:|---:|---|
| ZN | L15/h1 | +5.87 | +0.35 | 12/14 | no |
| 6E | L5/h1 | +2.45 | +0.17 | 10/14 | no |
| CL | L15/h30 | -4.88 | -5.95 | 11/14 | yes |

ZN leads NQ at 1–5 minutes with high significance (t up to 5.9, 12/14 years) but the spread is under one tick — cost-bound, as NQ→ES was. 6E carries
nothing. CL is the one qualifying channel and its sign is **inverse** to the registered "risk-on continuation" hypothesis: a crude rally over the prior
15–30 min is followed by NQ weakness over the next 30 min (t −4.9, −6 ticks, 11/14 years). Only CL went to T2.

## T2 — executable rules on CL (9 configs × registered direction, plus the post-hoc inverse as exploratory; 20 same-count random-direction placebos each)
| variant | k | H (min) | net | trades | $/trade | placebo mean | beats | +years |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| registered_cl_up_long | 1.0 | 15 | -161,611 | 48,791 | -3.31 | -186,967 | 20/20 | 0/14 |
| exploratory_cl_up_short | 1.0 | 15 | -142,761 | 48,855 | -2.92 | -186,967 | 20/20 | 0/14 |
| registered_cl_up_long | 1.0 | 30 | -103,563 | 28,921 | -3.58 | -104,769 | 11/20 | 0/14 |
| exploratory_cl_up_short | 1.0 | 30 | -75,379 | 28,952 | -2.60 | -104,769 | 20/20 | 0/14 |
| registered_cl_up_long | 1.0 | 60 | -66,907 | 16,456 | -4.07 | -60,328 | 3/20 | 0/14 |
| exploratory_cl_up_short | 1.0 | 60 | -34,023 | 16,451 | -2.07 | -60,328 | 20/20 | 2/14 |
| registered_cl_up_long | 1.5 | 15 | -118,878 | 34,705 | -3.43 | -166,165 | 20/20 | 0/14 |
| exploratory_cl_up_short | 1.5 | 15 | -98,379 | 34,755 | -2.83 | -166,165 | 20/20 | 1/14 |
| registered_cl_up_long | 1.5 | 30 | -86,503 | 22,705 | -3.81 | -97,677 | 19/20 | 0/14 |
| exploratory_cl_up_short | 1.5 | 30 | -54,704 | 22,699 | -2.41 | -97,677 | 20/20 | 0/14 |
| registered_cl_up_long | 1.5 | 60 | -57,447 | 14,147 | -4.06 | -55,524 | 8/20 | 0/14 |
| exploratory_cl_up_short | 1.5 | 60 | -32,526 | 14,139 | -2.30 | -55,524 | 20/20 | 1/14 |
| registered_cl_up_long | 2.0 | 15 | -82,358 | 23,100 | -3.57 | -135,928 | 20/20 | 0/14 |
| exploratory_cl_up_short | 2.0 | 15 | -62,596 | 23,132 | -2.71 | -135,928 | 20/20 | 1/14 |
| registered_cl_up_long | 2.0 | 30 | -62,077 | 16,494 | -3.76 | -83,410 | 20/20 | 0/14 |
| exploratory_cl_up_short | 2.0 | 30 | -41,074 | 16,498 | -2.49 | -83,410 | 20/20 | 1/14 |
| registered_cl_up_long | 2.0 | 60 | -42,071 | 11,222 | -3.75 | -48,502 | 14/20 | 0/14 |
| exploratory_cl_up_short | 2.0 | 60 | -29,109 | 11,229 | -2.59 | -48,502 | 20/20 | 1/14 |

**0 of 18 pass.** The registered direction loses and is mostly indistinguishable from random. The inverse direction beats the random-signal placebo in
every config (20/20) — the information is real — but every config still loses: with the registered rule firing on every minute |z| ≥ k, the 11k–49k
trades over 14 years pay ≈ $3.40 round trip each while the CL information is worth ≈ $1.7/trade (≈ 3.5 ticks), exactly what the T1 decile spread
implied (≈ 6 ticks top-vs-bottom ≈ 3 ticks per side). Same structure as every lead-lag found here: statistically undeniable, economically sub-cost.

## Verdict
**REJECTED** for the registered rules. Cross-asset family status: rates lead (ZN) sub-tick; FX (6E) none; oil (CL) inverse ≈ 3 ticks per 30 min.
A once-per-episode, 30-min-horizon version of the CL-inverse signal is the only post-hoc lead; it would need its own pre-registration and, at ≈ 3.5 ticks
gross against 5.4 ticks cost, has no realistic path to a funded-account edge on a micro. Spend this round: $45.94.

# Antigravity AG_NQ_Leader (NQ-vs-ES opening relative momentum → long MNQ) — fixed-engine replication (2026-11-08)

Rule as specified: at the 10:00 ET close, spread = NQ 09:30→10:00 return − ES 09:30→10:00 return; z = spread / std of the prior 20 sessions'
spreads; z ≥ 1.25 → long 1 MNQ (fill at the 10:00 bar open on the fixed engine), stop 2.0 × ATR14 (15m), target 4R, hold 12 × 15m bars, flat
15:55. NQ/ES 2010–18 + MNQ/MES 2019–23, 1.75-tick spread, 1 tick slippage, $0.61/side. Script: scripts/replicate_antigravity_nqleader.py.
Short side (z ≤ −1.25 → short MNQ) shown for information only. Validation 2024–25 NOT run (training gates failed); 2026 never loaded.

| year | long net (trades) | short net |
|---|---:|---:|
| 2010 | -28 (11) | -110 |
| 2011 | +12 (28) | +84 |
| 2012 | -248 (28) | -51 |
| 2013 | +146 (37) | +118 |
| 2014 | -13 (23) | +91 |
| 2015 | +196 (24) | -235 |
| 2016 | -199 (35) | -172 |
| 2017 | +206 (20) | +132 |
| 2018 | -302 (29) | +166 |
| 2019 | +202 (17) | -218 |
| 2020 | +500 (28) | +1,032 |
| 2021 | +282 (19) | -222 |
| 2022 | +593 (10) | +489 |
| 2023 | +484 (30) | +728 |

Long: 14-year +1,832 on 339 trades (sender: +$6,084 on 349), 2010–19 -28 (sender +$629), 9/14 years positive
(sender 12/14), largest year 32% of net. Short side: +$1,833 — both tails are positive, i.e. a large opening NQ/ES divergence
is followed by continuation of MNQ *in the direction of the divergence*, consistent with the ratio continuation found in pairs_1.

Placebo (20 random day sets with the same count per year, long at 10:00, identical exits): mean -864 (SD 1,094);
the real rule beats 20/20. The z-filter therefore carries information beyond random days — the first day-selection signal in this
project to do so on the long side — but the amount is ~$5/trade before 2020 and the rule fails the registered gates (9/14 years, 2010–19 flat).

Verdict: **not accepted; validation stays sealed.** Trade counts reproduce (339 vs 349), so the signal is the same; the sender's P&L is ~3× ours
with identical stated costs, which points to an execution/fill difference on its side (entry price, ATR bar, or hold accounting) — resolve before
quoting the +$6k. Worth keeping as a training-only lead: a symmetric (long and short) version with more history per year could be pre-registered,
but ~25 signals/yr at $5–17 each is not a funded-account edge.

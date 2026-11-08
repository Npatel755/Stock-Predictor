# anomaly_1: published intraday anomalies on ES/NQ (pre-registered 2026-11-09, before any result is seen)

Why. All data-mined families on disk are closed. These three are *externally* pre-specified effects with published evidence,
so the multiplicity is tiny (a handful of variants each) and the per-year gate is the real test.

Data. 1-min ES/NQ 2010-2018 + MES/MNQ 2019-2023 (train split), RTH 09:30-16:00 ET; FOMC dates from
research/news/official_calendar_2010_2026.csv (statement at 14:00 ET, 2010-2023: 8-12 per year). Validation 2024-25 once,
only for a frozen variant that passes training; 2026 never loaded. Costs: $0.61/side, MNQ spread 1.75 ticks / MES 1 tick,
1 tick slippage per side, $0.50/tick MNQ, $1.25/tick MES; 1 contract; flat by 15:55 ET.

A. Intraday momentum (Gao, Han, Li, Zhou 2018: first half-hour return predicts last half-hour return).
   Signal r1 = close(10:00) / open(09:30) - 1, optionally scaled by trailing 20-session std of r1. Variants: entry 15:00 or
   15:30, exit 15:55; threshold |z| >= {0, 0.5, 1.0}; also the Gao "12th half-hour" variant (13:30-14:00 return as a second
   predictor, trade only when both agree). 2 products x 2 entries x 3 thresholds x 2 (r1 only / r1 & r12) = 24 variants.
B. Pre-FOMC drift (Lucca & Moench 2015; drift concentrated in the 24 h before the 14:00 ET statement).
   Long from 09:30 (or 10:00) ET on announcement day to 13:55 ET (before the statement; no holding through it), and
   separately long on the RTH of the day before (09:30 -> 15:55). 2 products x 3 windows = 6 variants; ~110 events each.
   Control: same windows on all non-FOMC days (mean + day-block t), and 200 random 8-day-per-year placebo calendars.
C. Efficiency-ratio regime filter (Kaufman ER) as a filter on a *fixed, previously tested* 15-min momentum rule
   (mass_v2 reference: sign(momentum lb24) all-day 09:45-15:45, stop 2.0 ATR, target 3R, hold 24, MNQ). Variants: no filter,
   ER(24) > 0.3, > 0.5, > 0.7; and the same rule with the filter mask permuted (same on-fraction per year, 20 placebos).
   The question is only whether ER selects profitable bars beyond a random mask of the same size - not whether the base rule works.

Gates (training). Per variant: net > 0; positive in >= 10 of 14 years; no single year > 40% of net; >= 95% of placebos beaten;
>= 100 trades (A, C) or event-level day-block |t| > 3 with mean per-event net > cost (B). Decision per family: PASS -> freeze
and run 2024-25 once; else REJECTED. Nothing promoted to paper from this round regardless.

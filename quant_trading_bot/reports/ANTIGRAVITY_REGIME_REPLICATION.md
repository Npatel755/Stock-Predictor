# Antigravity "Dual-Regime" pair (ER-regime MNQ + morning trend MNQ) replicated on the fixed engine (2026-11-09)

Script: scripts/replicate_antigravity_regime.py; numbers: reports/ANTIGRAVITY_REGIME_REPLICATION.json. NQ 2010-18 + MNQ 2019-23 training, MNQ 2024-25 validation (already consulted by Antigravity before this run, so not out-of-sample for the pair). Micro costs as in all replications. Antigravity reports the pair was the best of 324 configs on 2010-23.

| sleeve | 14y net (AG) | 2010-19 | 2020-23 | +yrs/14 | max DD | trades | 2024 | 2025 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Regime_A (ER>0.5, vol_ratio<1.5, lb24, 2.0 ATR stop, 3R, trail 2.5, hold 24) | +5,719 (+5,710) | +2,326 | +3,394 | 10 | 879 | 790 | +2,773 | −872 |
| Trend_B (lb16 th0.75, 10-12 ET, 2.0 ATR, 3R, hold 8) | +5,611 (+4,929) | +726 | +4,884 | 11 | 959 | 954 | +1,566 | +147 |
| Pair (1c each) validation | | | | | EOD DD 982 | | +3,613 total (AG +3,385) | |

Regime_A by year: 2010 −44, 2011 +75, 2012 +190, 2013 −156, 2014 −61, 2015 +168, 2016 +178, 2017 +508, 2018 +1,497, 2019 −30, 2020 +35, 2021 +1,308, 2022 +1,840, 2023 +210.

Reading.
- Reproduces: Regime_A within $10, pair validation within $230; Trend_B is $680 higher here (bar/cost detail), direction the same.
- "10 of 14 years positive" is technically true but 2010-2016 are seven years of ±$200 (net +$350 over 7 years, i.e. zero after any cost error); the pre-2020 profit is 2017-18 (+$2,005 of +$2,326), and 2018 + 2021-22 are 81% of the 14-year net. Not a flat-decade antidote - a rule that is flat 2010-16, 2019-20, 2023 and catches three trending years.
- **ER-mask placebo fails the gate**: keeping the same number of eligible bars per year but placing them at random (direction still sign(momentum)), 20 placebos average +$838 with SD ≈ $4,000; the real rule beats 16 of 20 (80%, gate 95%), and three random masks score higher (+6,179, +6,622, +7,826). So ER > 0.5 does not demonstrably pick better bars than a random subset of the same size; the result is within what a mask-free momentum rule plus sampling noise produces - and this rule was the best of 324, which the placebo does not even correct for.
- 2025 validation of Regime_A is −$872 with a $1,029 intrabar DD on 27 trades; the pair's validation is 2024 alone.

Verdict: REJECTED as an undeniable edge; same class as the earlier trend sleeves with a filter that does not beat its own placebo. Not added to paper (five ledgers already carry this family).

# News round 2: post-release continuation sleeve

News round 2 (pre-registered 2026-11-08): post-release continuation as its own sleeve.

Hypothesis: after a high-impact 08:30 ET release, the direction of the 08:30-08:45 15-min bar continues for the next
hours (information is absorbed over time rather than instantly). Entry decision at the close of that bar, fill at the
next bar's open through the standard engine (spread + slippage + commissions, $150 risk, $400 daily loss, $2k DD).
Grid, fixed before running (16 per instrument): event set {high_0830 = CPI, Employment Situation, PPI, retail sales,
GDP, PCE; nfp_cpi}, range filter k in {0, 1.0} x ATR(16), target_r in {2.0, 6.0 (= effectively trail-only)},
hold_bars in {8, 16}; stop 1.5 ATR, 2 ATR trail, 1 contract.
Negative control: the identical rule fired on every weekday that has no scheduled release before 09:30 ("placebo").
Gate: train total net > 0, >= 60% of train years positive, worst annual DD < $1,000, and per-trade net exceeds the
placebo's per-trade net. Passers get one 2024-2025 validation look. 2026 never loaded.
Output: reports/NEWS_ROUND2.{json,md}; events.jsonl line.

| variant | events | k | target_r | hold | train total | +years | worst DD | trades | $/trade | placebo $/trade | gate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| MES/0 | high_0830 | 0.0 | 2.0 | 8 | -3,410 | 2/14 | 855 | 770 | -4.4 | -6.2 | fail |
| MES/1 | high_0830 | 0.0 | 2.0 | 16 | -3,669 | 2/14 | 1,005 | 770 | -4.8 | -6.5 | fail |
| MES/2 | high_0830 | 0.0 | 6.0 | 8 | -4,420 | 1/14 | 949 | 761 | -5.8 | -6.0 | fail |
| MES/3 | high_0830 | 0.0 | 6.0 | 16 | -3,838 | 2/14 | 944 | 761 | -5.0 | -6.3 | fail |
| MES/4 | high_0830 | 1.0 | 2.0 | 8 | -2,950 | 2/14 | 733 | 721 | -4.1 | -5.1 | fail |
| MES/5 | high_0830 | 1.0 | 2.0 | 16 | -3,215 | 2/14 | 883 | 721 | -4.5 | -5.3 | fail |
| MES/6 | high_0830 | 1.0 | 6.0 | 8 | -4,087 | 2/14 | 949 | 712 | -5.7 | -4.7 | fail |
| MES/7 | high_0830 | 1.0 | 6.0 | 16 | -3,410 | 2/14 | 944 | 712 | -4.8 | -4.3 | fail |
| MES/8 | nfp_cpi | 0.0 | 2.0 | 8 | -852 | 3/14 | 498 | 276 | -3.1 | -6.2 | fail |
| MES/9 | nfp_cpi | 0.0 | 2.0 | 16 | -905 | 3/14 | 504 | 276 | -3.3 | -6.5 | fail |
| MES/10 | nfp_cpi | 0.0 | 6.0 | 8 | -1,927 | 1/14 | 498 | 276 | -7.0 | -6.0 | fail |
| MES/11 | nfp_cpi | 0.0 | 6.0 | 16 | -1,755 | 4/14 | 520 | 276 | -6.4 | -6.3 | fail |
| MES/12 | nfp_cpi | 1.0 | 2.0 | 8 | -991 | 3/14 | 473 | 271 | -3.7 | -5.1 | fail |
| MES/13 | nfp_cpi | 1.0 | 2.0 | 16 | -1,044 | 3/14 | 479 | 271 | -3.9 | -5.3 | fail |
| MES/14 | nfp_cpi | 1.0 | 6.0 | 8 | -2,106 | 1/14 | 575 | 271 | -7.8 | -4.7 | fail |
| MES/15 | nfp_cpi | 1.0 | 6.0 | 16 | -1,826 | 4/14 | 572 | 271 | -6.7 | -4.3 | fail |
| MNQ/0 | high_0830 | 0.0 | 2.0 | 8 | +550 | 4/14 | 874 | 539 | +1.0 | -2.2 | fail |
| MNQ/1 | high_0830 | 0.0 | 2.0 | 16 | +255 | 4/14 | 874 | 539 | +0.5 | -2.1 | fail |
| MNQ/2 | high_0830 | 0.0 | 6.0 | 8 | -61 | 5/14 | 1,106 | 536 | -0.1 | +1.0 | fail |
| MNQ/3 | high_0830 | 0.0 | 6.0 | 16 | +338 | 6/14 | 1,041 | 536 | +0.6 | +1.9 | fail |
| MNQ/4 | high_0830 | 1.0 | 2.0 | 8 | +282 | 4/14 | 874 | 493 | +0.6 | -1.1 | fail |
| MNQ/5 | high_0830 | 1.0 | 2.0 | 16 | +128 | 4/14 | 874 | 493 | +0.3 | -1.2 | fail |
| MNQ/6 | high_0830 | 1.0 | 6.0 | 8 | -375 | 4/14 | 1,106 | 490 | -0.8 | +0.8 | fail |
| MNQ/7 | high_0830 | 1.0 | 6.0 | 16 | -277 | 5/14 | 1,041 | 490 | -0.6 | +1.2 | fail |
| MNQ/8 | nfp_cpi | 0.0 | 2.0 | 8 | -420 | 5/14 | 543 | 189 | -2.2 | -2.2 | fail |
| MNQ/9 | nfp_cpi | 0.0 | 2.0 | 16 | -390 | 5/14 | 543 | 189 | -2.1 | -2.1 | fail |
| MNQ/10 | nfp_cpi | 0.0 | 6.0 | 8 | -1,346 | 3/14 | 693 | 189 | -7.1 | +1.0 | fail |
| MNQ/11 | nfp_cpi | 0.0 | 6.0 | 16 | -1,294 | 4/14 | 759 | 189 | -6.8 | +1.9 | fail |
| MNQ/12 | nfp_cpi | 1.0 | 2.0 | 8 | -585 | 5/14 | 543 | 181 | -3.2 | -1.1 | fail |
| MNQ/13 | nfp_cpi | 1.0 | 2.0 | 16 | -500 | 5/14 | 543 | 181 | -2.8 | -1.2 | fail |
| MNQ/14 | nfp_cpi | 1.0 | 6.0 | 8 | -1,593 | 2/14 | 693 | 181 | -8.8 | +0.8 | fail |
| MNQ/15 | nfp_cpi | 1.0 | 6.0 | 16 | -1,572 | 3/14 | 759 | 181 | -8.7 | +1.2 | fail |

Passers sent to validation: none


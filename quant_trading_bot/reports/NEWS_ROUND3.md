# News round 3: FOMC-afternoon continuation / fade sleeve

News round 3 (pre-registered 2026-11-08): FOMC-afternoon continuation / fade as its own sleeve.

Motivation: round 1 showed the deployed sleeves do slightly better when FOMC afternoons are skipped on MES_MOM and
MNQ_E57 (not enough years to pass), i.e. the post-statement move behaves differently from the sleeves' trend rules.
Hypothesis A (cont): the direction of the 14:00-14:15 ET statement bar continues into the close.
Hypothesis B (fade): the statement bar's direction reverses into the close (the "FOMC whipsaw").
Decision at the close of the 14:00-14:15 bar, fill at the 14:15 open through the standard engine (spread, slippage,
commissions, $150 risk, $400 daily loss, $2k DD, forced flat 15:55 ET).
Sample: only meetings since 2013, when the statement time became a fixed 14:00 ET (2010-2012 statements were released
at 12:30 or 14:15 and our calendar only carries approximate times for them). Train = ES 2013-2019 + MES 2020-2023
(11 years, ~90 scheduled meetings; the 2020-03-03 emergency cut is in the calendar and fires one spurious day).
Grid, fixed before running (16 per instrument): direction {cont, fade} x range filter k in {0, 1.0} x ATR(16) x
target_r {2.0, 6.0} x hold_bars {3 (to 15:00), 6 (to 15:45)}; stop 1.5 ATR, 2 ATR trail, 1 contract.
Negative control: identical rule fired on every non-FOMC weekday ("placebo").
Gate: train total net > 0, >= 60% of train years positive, worst annual DD < $1,000, per-trade net > placebo per-trade.
Passers get one 2024-2025 validation look. 2026 never loaded. Small sample: anything that passes is exploratory.
Output: reports/NEWS_ROUND3.{json,md}; events.jsonl line.

| variant | dir | k | target_r | hold | train total | +years | worst DD | trades | $/trade | placebo $/trade | gate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| MES/0 | cont | 0.0 | 2.0 | 3 | -1,716 | 1/11 | 699 | 89 | -19.3 | -5.5 | fail |
| MES/1 | cont | 0.0 | 2.0 | 6 | -1,414 | 2/11 | 699 | 89 | -15.9 | -4.3 | fail |
| MES/2 | cont | 0.0 | 6.0 | 3 | -1,720 | 2/11 | 699 | 89 | -19.3 | -5.5 | fail |
| MES/3 | cont | 0.0 | 6.0 | 6 | -1,663 | 2/11 | 769 | 89 | -18.7 | -4.2 | fail |
| MES/4 | cont | 1.0 | 2.0 | 3 | -1,529 | 2/11 | 699 | 83 | -18.4 | -5.8 | fail |
| MES/5 | cont | 1.0 | 2.0 | 6 | -1,450 | 2/11 | 699 | 83 | -17.5 | -4.3 | fail |
| MES/6 | cont | 1.0 | 6.0 | 3 | -1,533 | 2/11 | 699 | 83 | -18.5 | -5.8 | fail |
| MES/7 | cont | 1.0 | 6.0 | 6 | -1,698 | 2/11 | 769 | 83 | -20.5 | -3.8 | fail |
| MES/8 | fade | 0.0 | 2.0 | 3 | -122 | 6/11 | 280 | 89 | -1.4 | -6.4 | fail |
| MES/9 | fade | 0.0 | 2.0 | 6 | -229 | 6/11 | 280 | 89 | -2.6 | -8.0 | fail |
| MES/10 | fade | 0.0 | 6.0 | 3 | -18 | 5/11 | 280 | 89 | -0.2 | -6.5 | fail |
| MES/11 | fade | 0.0 | 6.0 | 6 | -174 | 5/11 | 280 | 89 | -2.0 | -8.5 | fail |
| MES/12 | fade | 1.0 | 2.0 | 3 | -327 | 5/11 | 280 | 83 | -3.9 | -6.0 | fail |
| MES/13 | fade | 1.0 | 2.0 | 6 | -208 | 5/11 | 280 | 83 | -2.5 | -6.7 | fail |
| MES/14 | fade | 1.0 | 6.0 | 3 | -228 | 4/11 | 280 | 83 | -2.8 | -6.0 | fail |
| MES/15 | fade | 1.0 | 6.0 | 6 | -218 | 4/11 | 280 | 83 | -2.6 | -7.4 | fail |
| MNQ/0 | cont | 0.0 | 2.0 | 3 | -1,434 | 1/11 | 391 | 83 | -17.3 | -2.7 | fail |
| MNQ/1 | cont | 0.0 | 2.0 | 6 | -1,348 | 3/11 | 398 | 83 | -16.2 | -1.2 | fail |
| MNQ/2 | cont | 0.0 | 6.0 | 3 | -1,468 | 1/11 | 421 | 83 | -17.7 | -2.7 | fail |
| MNQ/3 | cont | 0.0 | 6.0 | 6 | -1,577 | 3/11 | 493 | 83 | -19.0 | -1.2 | fail |
| MNQ/4 | cont | 1.0 | 2.0 | 3 | -1,344 | 1/11 | 391 | 77 | -17.4 | -4.1 | fail |
| MNQ/5 | cont | 1.0 | 2.0 | 6 | -1,280 | 3/11 | 391 | 77 | -16.6 | -1.9 | fail |
| MNQ/6 | cont | 1.0 | 6.0 | 3 | -1,378 | 1/11 | 421 | 77 | -17.9 | -4.1 | fail |
| MNQ/7 | cont | 1.0 | 6.0 | 6 | -1,509 | 4/11 | 493 | 77 | -19.6 | -1.8 | fail |
| MNQ/8 | fade | 0.0 | 2.0 | 3 | +612 | 5/11 | 350 | 83 | +7.4 | -3.7 | fail |
| MNQ/9 | fade | 0.0 | 2.0 | 6 | +576 | 5/11 | 350 | 83 | +7.0 | -4.3 | fail |
| MNQ/10 | fade | 0.0 | 6.0 | 3 | +1,192 | 7/11 | 350 | 83 | +14.4 | -3.8 | PASS |
| MNQ/11 | fade | 0.0 | 6.0 | 6 | +1,256 | 7/11 | 350 | 83 | +15.1 | -4.8 | PASS |
| MNQ/12 | fade | 1.0 | 2.0 | 3 | +418 | 4/11 | 350 | 77 | +5.4 | -2.4 | fail |
| MNQ/13 | fade | 1.0 | 2.0 | 6 | +432 | 5/11 | 350 | 77 | +5.6 | -3.1 | fail |
| MNQ/14 | fade | 1.0 | 6.0 | 3 | +940 | 6/11 | 350 | 77 | +12.2 | -2.4 | fail |
| MNQ/15 | fade | 1.0 | 6.0 | 6 | +955 | 6/11 | 367 | 77 | +12.4 | -4.0 | fail |

Passers sent to validation: ['MNQ/10', 'MNQ/11']

- MNQ/10: 2024 event -460 (6 tr) vs placebo +134, 2025 event -263 (4 tr) vs placebo +740
- MNQ/11: 2024 event -466 (6 tr) vs placebo -19, 2025 event -263 (4 tr) vs placebo +244

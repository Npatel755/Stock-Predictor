# book_2 - Book A with the D+ v2 intraday leg (training 2010-23 only) - FAIL, not deployed

Protocol: research/book_2/PROTOCOL.md. Script: scripts/book_2_pilot.py -> reports/BOOK_2_TRAINING.json.

`book_ad` = overnight_dip_v2 (MNQ 1c) + ag_arch_d_plus_v2 (3 sleeves, 1c, $150 budget) as one 1-contract account.

| book | closed net | marked DD | when | $2k touches | years >0 | 1y breach MC | worst day |
|---|---|---|---|---|---|---|---|
| Book A (reference, book_1) | +28,317 | 2,043 | 17 Mar 2020 | 1 | 12/14 | 1.9% | - |
| book_ad (1c) | +29,373 | 2,166 | 17 Mar 2020 | 1 | 12/14 | 0.9% | -764 |
| book_ad, intraday leg at 2c ($300 budget) | +46,949 | 2,514 | 17 Mar 2020 | 4 | 12/14 | 5.0% | -863 |

Verdict: fails the pre-registered marked-DD gate (2,166 >= 2,000, one touch). The touch is the same overnight night as Book A's
(17 Mar 2020, the dip leg's intraday excursion), and D+ v2 adds +1,056 of net but also ~120 of drawdown around it, so swapping the
intraday leg does not fix the book's one floor miss - which risk_1 already showed is a single-night excursion, not a streak. Positives
recorded for the forward comparison: higher net and lower closed-equity breach odds (0.9% vs 1.9%). Nothing deployed; the staged
2c-intraday version is far outside the floor (4 touches, 5% one-year breach). Cushion staging (one leg until ~$500 banked) stays the rule.

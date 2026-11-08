# Round 6: VIX regime filters on the deployed sleeves

Round 6 (pre-registered 2026-11-08): VIX regime filters on the six deployed sleeves (QC tutorial 58 "VIX predicts
stock index returns" -> adapted as a point-in-time regime gate, not as a return forecast).

Data: CBOE VIX_History.csv (free, research/external/). Point-in-time value for trade date D = VIX close of the prior
trading day (forward-filled over holidays); rolling percentiles use the prior 252 closes, excluding D-1 itself... i.e.
every number used on day D was printed before D's session opened.
Filters (fixed before running), applied as entry blocks on each sleeve through the news-round-1 harness:
  skip_vix_gt30      block when VIX(D-1) > 30
  skip_vix_lt15      block when VIX(D-1) < 15
  only_vix_top30     trade only when VIX(D-1) >= 70th pct of the prior 252 closes
  skip_vix_top10     block when VIX(D-1) >= 90th pct
  skip_vix_bottom20  block when VIX(D-1) <= 20th pct
  only_vix_falling   trade only when VIX(D-1) < SMA10 of VIX(D-2..D-11)
Train = ES/NQ 2010-2019 + MES/MNQ 2020-2023 at today's costs. Gate per sleeve: total > baseline, worst annual DD <=
baseline, >= 60% of years beat baseline. Passers get one 2024-2025 validation look. 2026 never loaded.
Output: reports/VIX_ROUND6.{json,md}; events.jsonl line.

| sleeve | filter | total | baseline | worst DD | baseline DD | beats | trades | gate |
|---|---|---|---|---|---|---|---|---|
| MES_MOM_3c | skip_vix_gt30 | +8,222 | +7,625 | 814 | 814 | 3/14 | 380/393 | fail |
| MES_MOM_3c | skip_vix_lt15 | +8,589 | +7,625 | 677 | 814 | 8/14 | 259/393 | fail |
| MES_MOM_3c | only_vix_top30 | +2,559 | +7,625 | 647 | 814 | 9/14 | 105/393 | fail |
| MES_MOM_3c | skip_vix_top10 | +6,447 | +7,625 | 814 | 814 | 6/14 | 360/393 | fail |
| MES_MOM_3c | skip_vix_bottom20 | +6,184 | +7,625 | 718 | 814 | 6/14 | 287/393 | fail |
| MES_MOM_3c | only_vix_falling | +6,653 | +7,625 | 596 | 814 | 10/14 | 231/393 | fail |
| MES_MOM_1c | skip_vix_gt30 | +2,874 | +2,742 | 271 | 271 | 3/14 | 378/389 | fail |
| MES_MOM_1c | skip_vix_lt15 | +3,064 | +2,742 | 225 | 271 | 8/14 | 255/389 | fail |
| MES_MOM_1c | only_vix_top30 | +1,106 | +2,742 | 215 | 271 | 9/14 | 101/389 | fail |
| MES_MOM_1c | skip_vix_top10 | +2,397 | +2,742 | 271 | 271 | 5/14 | 357/389 | fail |
| MES_MOM_1c | skip_vix_bottom20 | +2,262 | +2,742 | 239 | 271 | 6/14 | 283/389 | fail |
| MES_MOM_1c | only_vix_falling | +2,472 | +2,742 | 198 | 271 | 10/14 | 228/389 | fail |
| MES_MOM_2c | skip_vix_gt30 | +5,384 | +5,048 | 542 | 542 | 3/14 | 380/393 | fail |
| MES_MOM_2c | skip_vix_lt15 | +5,691 | +5,048 | 451 | 542 | 8/14 | 259/393 | fail |
| MES_MOM_2c | only_vix_top30 | +1,915 | +5,048 | 431 | 542 | 9/14 | 105/393 | fail |
| MES_MOM_2c | skip_vix_top10 | +4,257 | +5,048 | 542 | 542 | 6/14 | 360/393 | fail |
| MES_MOM_2c | skip_vix_bottom20 | +4,088 | +5,048 | 478 | 542 | 6/14 | 287/393 | fail |
| MES_MOM_2c | only_vix_falling | +4,410 | +5,048 | 396 | 542 | 10/14 | 231/393 | fail |
| MNQ_BRK_E_2c | skip_vix_gt30 | +8,650 | +9,790 | 996 | 996 | 2/14 | 468/495 | fail |
| MNQ_BRK_E_2c | skip_vix_lt15 | +9,390 | +9,790 | 574 | 996 | 2/14 | 302/495 | fail |
| MNQ_BRK_E_2c | only_vix_top30 | +3,179 | +9,790 | 743 | 996 | 4/14 | 132/495 | fail |
| MNQ_BRK_E_2c | skip_vix_top10 | +9,706 | +9,790 | 1,238 | 996 | 8/14 | 444/495 | fail |
| MNQ_BRK_E_2c | skip_vix_bottom20 | +4,516 | +9,790 | 941 | 996 | 6/14 | 346/495 | fail |
| MNQ_BRK_E_2c | only_vix_falling | +9,202 | +9,790 | 320 | 996 | 9/14 | 269/495 | fail |
| MNQ_VOL_1c | skip_vix_gt30 | +2,632 | +2,637 | 1,160 | 1,165 | 4/14 | 3558/3656 | fail |
| MNQ_VOL_1c | skip_vix_lt15 | +2,778 | +2,637 | 970 | 1,165 | 6/14 | 2202/3656 | fail |
| MNQ_VOL_1c | only_vix_top30 | -1,387 | +2,637 | 1,331 | 1,165 | 8/14 | 925/3656 | fail |
| MNQ_VOL_1c | skip_vix_top10 | +3,423 | +2,637 | 1,184 | 1,165 | 6/14 | 3684/3656 | fail |
| MNQ_VOL_1c | skip_vix_bottom20 | +1,528 | +2,637 | 1,218 | 1,165 | 6/14 | 2513/3656 | fail |
| MNQ_VOL_1c | only_vix_falling | +3,446 | +2,637 | 765 | 1,165 | 8/14 | 2320/3656 | fail |
| MNQ_E57_1c | skip_vix_gt30 | +5,144 | +5,004 | 807 | 807 | 4/14 | 574/597 | fail |
| MNQ_E57_1c | skip_vix_lt15 | +5,268 | +5,004 | 536 | 807 | 4/14 | 361/597 | fail |
| MNQ_E57_1c | only_vix_top30 | +706 | +5,004 | 213 | 807 | 5/14 | 124/597 | fail |
| MNQ_E57_1c | skip_vix_top10 | +5,104 | +5,004 | 758 | 807 | 6/14 | 555/597 | fail |
| MNQ_E57_1c | skip_vix_bottom20 | +4,442 | +5,004 | 666 | 807 | 8/14 | 408/597 | fail |
| MNQ_E57_1c | only_vix_falling | +2,886 | +5,004 | 485 | 807 | 6/14 | 340/597 | fail |
| MNQ_BRK_E_1c | skip_vix_gt30 | +3,726 | +4,348 | 498 | 498 | 2/14 | 453/475 | fail |
| MNQ_BRK_E_1c | skip_vix_lt15 | +4,148 | +4,348 | 322 | 498 | 2/14 | 282/475 | fail |
| MNQ_BRK_E_1c | only_vix_top30 | +1,180 | +4,348 | 371 | 498 | 4/14 | 120/475 | fail |
| MNQ_BRK_E_1c | skip_vix_top10 | +4,545 | +4,348 | 619 | 498 | 8/14 | 429/475 | fail |
| MNQ_BRK_E_1c | skip_vix_bottom20 | +1,728 | +4,348 | 470 | 498 | 6/14 | 329/475 | fail |
| MNQ_BRK_E_1c | only_vix_falling | +4,275 | +4,348 | 160 | 498 | 9/14 | 261/475 | fail |
| MNQ_HYB_C_1c | skip_vix_gt30 | +2,272 | +2,370 | 455 | 455 | 2/14 | 492/514 | fail |
| MNQ_HYB_C_1c | skip_vix_lt15 | +2,573 | +2,370 | 462 | 455 | 6/14 | 336/514 | fail |
| MNQ_HYB_C_1c | only_vix_top30 | +830 | +2,370 | 307 | 455 | 6/14 | 132/514 | fail |
| MNQ_HYB_C_1c | skip_vix_top10 | +2,542 | +2,370 | 416 | 455 | 6/14 | 463/514 | fail |
| MNQ_HYB_C_1c | skip_vix_bottom20 | +2,336 | +2,370 | 457 | 455 | 8/14 | 375/514 | fail |
| MNQ_HYB_C_1c | only_vix_falling | +1,153 | +2,370 | 444 | 455 | 4/14 | 307/514 | fail |

Passers sent to validation: none


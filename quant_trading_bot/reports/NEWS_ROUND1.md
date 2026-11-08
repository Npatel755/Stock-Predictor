# News round 1: scheduled-release filters on the paper sleeves

Registered 2026-11-08 (protocol in scripts/news_round1.py). TRAIN = ES/NQ 2010-2019 + MES/MNQ 2020-2023, annual $50k accounts, today's costs. Gate: beats baseline total net, worst annual DD no worse, beats baseline in >= 60% of years. Passers get one 2024-2025 validation look. 2026 untouched.

| sleeve | variant | train total | worst annual DD | trades | years beating baseline | gate |
|---|---|---|---|---|---|---|
| MES_MOM_3c | baseline | +7,625 | 814 | 393 | -/14 | baseline |
| MES_MOM_3c | blackout_high_15 | +7,437 | 941 | 393 | 0/14 | fail |
| MES_MOM_3c | blackout_high_30 | +7,460 | 941 | 393 | 0/14 | fail |
| MES_MOM_3c | blackout_all_15 | +7,362 | 871 | 387 | 1/14 | fail |
| MES_MOM_3c | fomc_afternoon | +7,910 | 781 | 388 | 3/14 | fail |
| MES_MOM_3c | fomc_day | +7,910 | 781 | 388 | 3/14 | fail |
| MES_MOM_3c | nfp_cpi_day | +6,067 | 628 | 342 | 6/14 | fail |
| MNQ_BRK_E_2c | baseline | +9,790 | 996 | 495 | -/14 | baseline |
| MNQ_BRK_E_2c | blackout_high_15 | +9,790 | 996 | 495 | 0/14 | fail |
| MNQ_BRK_E_2c | blackout_high_30 | +9,790 | 996 | 495 | 0/14 | fail |
| MNQ_BRK_E_2c | blackout_all_15 | +7,792 | 996 | 468 | 5/14 | fail |
| MNQ_BRK_E_2c | fomc_afternoon | +9,790 | 996 | 495 | 0/14 | fail |
| MNQ_BRK_E_2c | fomc_day | +9,924 | 996 | 481 | 8/14 | fail |
| MNQ_BRK_E_2c | nfp_cpi_day | +9,650 | 1,019 | 466 | 6/14 | fail |
| MES_MOM_1c | baseline | +2,742 | 271 | 389 | -/14 | baseline |
| MES_MOM_1c | blackout_high_15 | +2,680 | 313 | 389 | 0/14 | fail |
| MES_MOM_1c | blackout_high_30 | +2,687 | 313 | 389 | 0/14 | fail |
| MES_MOM_1c | blackout_all_15 | +2,654 | 290 | 383 | 1/14 | fail |
| MES_MOM_1c | fomc_afternoon | +2,837 | 260 | 384 | 3/14 | fail |
| MES_MOM_1c | fomc_day | +2,837 | 260 | 384 | 3/14 | fail |
| MES_MOM_1c | nfp_cpi_day | +2,244 | 209 | 339 | 5/14 | fail |
| MNQ_VOL_1c | baseline | +2,637 | 1,165 | 3656 | -/14 | baseline |
| MNQ_VOL_1c | blackout_high_15 | +2,736 | 1,165 | 3654 | 2/14 | fail |
| MNQ_VOL_1c | blackout_high_30 | +2,672 | 1,165 | 3654 | 1/14 | fail |
| MNQ_VOL_1c | blackout_all_15 | +2,743 | 1,178 | 3589 | 8/14 | fail |
| MNQ_VOL_1c | fomc_afternoon | +2,637 | 1,165 | 3656 | 0/14 | fail |
| MNQ_VOL_1c | fomc_day | +2,564 | 1,148 | 3536 | 11/14 | fail |
| MNQ_VOL_1c | nfp_cpi_day | +2,346 | 1,126 | 3371 | 7/14 | fail |
| MNQ_E57_1c | baseline | +5,004 | 807 | 597 | -/14 | baseline |
| MNQ_E57_1c | blackout_high_15 | +4,989 | 838 | 595 | 2/14 | fail |
| MNQ_E57_1c | blackout_high_30 | +5,006 | 838 | 594 | 2/14 | fail |
| MNQ_E57_1c | blackout_all_15 | +4,454 | 839 | 588 | 3/14 | fail |
| MNQ_E57_1c | fomc_afternoon | +5,042 | 802 | 593 | 3/14 | fail |
| MNQ_E57_1c | fomc_day | +5,142 | 802 | 592 | 3/14 | fail |
| MNQ_E57_1c | nfp_cpi_day | +4,567 | 512 | 534 | 7/14 | fail |
| MES_MOM_2c | baseline | +5,048 | 542 | 393 | -/14 | baseline |
| MES_MOM_2c | blackout_high_15 | +4,923 | 627 | 393 | 0/14 | fail |
| MES_MOM_2c | blackout_high_30 | +4,938 | 627 | 393 | 0/14 | fail |
| MES_MOM_2c | blackout_all_15 | +4,873 | 580 | 387 | 1/14 | fail |
| MES_MOM_2c | fomc_afternoon | +5,238 | 520 | 388 | 3/14 | fail |
| MES_MOM_2c | fomc_day | +5,238 | 520 | 388 | 3/14 | fail |
| MES_MOM_2c | nfp_cpi_day | +4,146 | 418 | 342 | 6/14 | fail |
| MNQ_BRK_E_1c | baseline | +4,348 | 498 | 475 | -/14 | baseline |
| MNQ_BRK_E_1c | blackout_high_15 | +4,348 | 498 | 475 | 0/14 | fail |
| MNQ_BRK_E_1c | blackout_high_30 | +4,348 | 498 | 475 | 0/14 | fail |
| MNQ_BRK_E_1c | blackout_all_15 | +3,348 | 498 | 448 | 5/14 | fail |
| MNQ_BRK_E_1c | fomc_afternoon | +4,348 | 498 | 475 | 0/14 | fail |
| MNQ_BRK_E_1c | fomc_day | +4,408 | 498 | 462 | 8/14 | fail |
| MNQ_BRK_E_1c | nfp_cpi_day | +4,403 | 510 | 448 | 6/14 | fail |
| MNQ_HYB_C_1c | baseline | +2,370 | 455 | 514 | -/14 | baseline |
| MNQ_HYB_C_1c | blackout_high_15 | +2,362 | 463 | 514 | 0/14 | fail |
| MNQ_HYB_C_1c | blackout_high_30 | +1,869 | 468 | 512 | 0/14 | fail |
| MNQ_HYB_C_1c | blackout_all_15 | +2,362 | 463 | 514 | 0/14 | fail |
| MNQ_HYB_C_1c | fomc_afternoon | +1,945 | 405 | 509 | 2/14 | fail |
| MNQ_HYB_C_1c | fomc_day | +1,945 | 405 | 509 | 2/14 | fail |
| MNQ_HYB_C_1c | nfp_cpi_day | +1,766 | 398 | 469 | 5/14 | fail |

Passers sent to validation: none


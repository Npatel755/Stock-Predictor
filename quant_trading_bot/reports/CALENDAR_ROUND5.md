# Round 5: calendar effects (TOM, pre-holiday, OpEx) on MES/MNQ day session

Round 5 (pre-registered 2026-11-08): calendar effects from the QuantConnect library (turn of month, pre-holiday,
option-expiration week; QC tutorials 35/83/102, Quantpedia) adapted to a day-session-only MES/MNQ account.

Published versions are close-to-close equity effects, mostly earned overnight, which this account cannot hold. Two
executable adaptations, both training-only (ES/NQ 2010-2019 + MES/MNQ 2020-2023, today's costs), 2026 never loaded:
A. Day filters on the six deployed sleeves (same harness and gate as news round 1): skip_opex_week (Mon-Fri of the
   third-Friday week), skip_opex_friday, skip_tom (last trading day + first 3 of the month), only_tom, skip_preholiday
   (trading day before a weekday with no session). Gate: total > baseline, worst DD <= baseline, >= 60% of years beat.
B. Stand-alone "TOM day-session long": buy at the 09:45 ET open on turn-of-month days, 1.5 ATR(16) stop, no target,
   flat at the 16:00 bar; placebo = same on all other weekdays. Gate: total > 0, >= 60% years positive, worst annual
   DD < $1,000, per-trade net > placebo per-trade. Passers get one 2024-2025 validation look.
Trading-day calendar is derived from the bars themselves (a weekday with no 09:30 bar is a holiday).
Output: reports/CALENDAR_ROUND5.{json,md}; events.jsonl line.

## A. Day filters on the deployed sleeves (train total / worst annual DD / years beating baseline)

| sleeve | filter | total | baseline | worst DD | baseline DD | beats | gate |
|---|---|---|---|---|---|---|---|
| MES_MOM_3c | skip_opex_week | +6,486 | +7,625 | 606 | 814 | 8/14 | fail |
| MES_MOM_3c | skip_opex_friday | +7,152 | +7,625 | 814 | 814 | 4/14 | fail |
| MES_MOM_3c | skip_tom | +4,036 | +7,625 | 1,591 | 814 | 6/14 | fail |
| MES_MOM_3c | only_tom | +3,904 | +7,625 | 442 | 814 | 8/14 | fail |
| MES_MOM_3c | skip_preholiday | +7,393 | +7,625 | 758 | 814 | 3/14 | fail |
| MES_MOM_1c | skip_opex_week | +2,233 | +2,742 | 201 | 271 | 8/14 | fail |
| MES_MOM_1c | skip_opex_friday | +2,488 | +2,742 | 271 | 271 | 3/14 | fail |
| MES_MOM_1c | skip_tom | +1,527 | +2,742 | 429 | 271 | 6/14 | fail |
| MES_MOM_1c | only_tom | +1,301 | +2,742 | 147 | 271 | 8/14 | fail |
| MES_MOM_1c | skip_preholiday | +2,665 | +2,742 | 252 | 271 | 3/14 | fail |
| MES_MOM_2c | skip_opex_week | +4,368 | +5,048 | 403 | 542 | 8/14 | fail |
| MES_MOM_2c | skip_opex_friday | +4,685 | +5,048 | 542 | 542 | 4/14 | fail |
| MES_MOM_2c | skip_tom | +2,618 | +5,048 | 1,047 | 542 | 6/14 | fail |
| MES_MOM_2c | only_tom | +2,602 | +5,048 | 294 | 542 | 8/14 | fail |
| MES_MOM_2c | skip_preholiday | +4,894 | +5,048 | 505 | 542 | 3/14 | fail |
| MNQ_BRK_E_2c | skip_opex_week | +10,288 | +9,790 | 1,123 | 996 | 7/14 | fail |
| MNQ_BRK_E_2c | skip_opex_friday | +9,710 | +9,790 | 1,133 | 996 | 5/14 | fail |
| MNQ_BRK_E_2c | skip_tom | +5,504 | +9,790 | 887 | 996 | 6/14 | fail |
| MNQ_BRK_E_2c | only_tom | +4,286 | +9,790 | 330 | 996 | 7/14 | fail |
| MNQ_BRK_E_2c | skip_preholiday | +9,769 | +9,790 | 996 | 996 | 1/14 | fail |
| MNQ_VOL_1c | skip_opex_week | +1,609 | +2,637 | 1,159 | 1,165 | 5/14 | fail |
| MNQ_VOL_1c | skip_opex_friday | +1,626 | +2,637 | 1,308 | 1,165 | 6/14 | fail |
| MNQ_VOL_1c | skip_tom | -1,152 | +2,637 | 1,275 | 1,165 | 6/14 | fail |
| MNQ_VOL_1c | only_tom | +3,716 | +2,637 | 485 | 1,165 | 9/14 | PASS |
| MNQ_VOL_1c | skip_preholiday | +3,262 | +2,637 | 1,163 | 1,165 | 8/14 | fail |
| MNQ_E57_1c | skip_opex_week | +4,503 | +5,004 | 543 | 807 | 8/14 | fail |
| MNQ_E57_1c | skip_opex_friday | +5,087 | +5,004 | 771 | 807 | 5/14 | fail |
| MNQ_E57_1c | skip_tom | +4,184 | +5,004 | 494 | 807 | 8/14 | fail |
| MNQ_E57_1c | only_tom | +820 | +5,004 | 333 | 807 | 6/14 | fail |
| MNQ_E57_1c | skip_preholiday | +5,116 | +5,004 | 791 | 807 | 4/14 | fail |
| MNQ_BRK_E_1c | skip_opex_week | +4,800 | +4,348 | 562 | 498 | 8/14 | fail |
| MNQ_BRK_E_1c | skip_opex_friday | +4,374 | +4,348 | 566 | 498 | 5/14 | fail |
| MNQ_BRK_E_1c | skip_tom | +2,692 | +4,348 | 443 | 498 | 7/14 | fail |
| MNQ_BRK_E_1c | only_tom | +1,656 | +4,348 | 259 | 498 | 7/14 | fail |
| MNQ_BRK_E_1c | skip_preholiday | +4,337 | +4,348 | 498 | 498 | 1/14 | fail |
| MNQ_HYB_C_1c | skip_opex_week | +2,000 | +2,370 | 278 | 455 | 4/14 | fail |
| MNQ_HYB_C_1c | skip_opex_friday | +2,273 | +2,370 | 387 | 455 | 3/14 | fail |
| MNQ_HYB_C_1c | skip_tom | +3,442 | +2,370 | 299 | 455 | 10/14 | PASS |
| MNQ_HYB_C_1c | only_tom | -987 | +2,370 | 340 | 455 | 4/14 | fail |
| MNQ_HYB_C_1c | skip_preholiday | +2,454 | +2,370 | 446 | 455 | 3/14 | fail |

## B. TOM day-session long sleeve

| instrument | total | +years | worst DD | trades | $/trade | placebo $/trade | gate |
|---|---|---|---|---|---|---|---|
| MES | -515 | 6/14 | 845 | 444 | -1.2 | -5.8 | fail |
| MNQ | +460 | 6/14 | 559 | 401 | +1.1 | -2.9 | fail |

Passers sent to validation: ['MNQ_VOL_1c/only_tom', 'MNQ_HYB_C_1c/skip_tom']

- MNQ_VOL_1c/only_tom: 2024 filtered +618 (33 tr), baseline +2,348 (240 tr); 2025 filtered -252 (16 tr), baseline -1,136 (132 tr)
- MNQ_HYB_C_1c/skip_tom: 2024 filtered +640 (28 tr), baseline +616 (33 tr); 2025 filtered -166 (16 tr), baseline -385 (7 tr)

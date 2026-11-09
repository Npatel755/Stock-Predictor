# overnight_7 — expanding-window walk-forward of overnight_dip_v2 inside 2010–2023 (2024–26 sealed) — ROBUST

Protocol: research/overnight_7/PROTOCOL.md. Script: scripts/overnight_7_pilot.py. Raw: reports/OVERNIGHT_7_WALKFORWARD.json.
Each year 2014–2023 the rule's (k, w) — and separately its exit — were re-chosen using only 2010..Y−1 (criterion net / max(DD, $500)) and then scored on year Y.

| year | chosen (k, w) | WF net (params) | chosen exit | WF net (exit) | fixed v2 (0.5, 20, 09:45) |
|---|---|---:|---|---:|---:|
| 2014 | 0.5, 15 | 385 | 10:00 | 160 | 384 |
| 2015 | 0.5, 15 | 638 | 09:45 | 695 | 695 |
| 2016 | 0.5, 20 | 554 | 09:45 | 554 | 554 |
| 2017 | 0.5, 20 | −263 | 09:45 | −263 | −263 |
| 2018 | 0.5, 20 | 1,605 | 10:00 | 1,861 | 1,605 |
| 2019 | 0.5, 20 | 1,489 | 10:00 | 1,667 | 1,489 |
| 2020 | 0.5, 15 | 1,156 | 10:00 | 1,290 | 1,144 |
| 2021 | 0.5, 15 | 1,536 | 09:45 | 1,507 | 1,507 |
| 2022 | 0.5, 15 | 2,646 | 09:45 | 3,453 | 3,453 |
| 2023 | 1.0, 20 | 284 | 09:35 | −326 | 724 |
| **total 2014–23** | | **10,030** | | **10,597** | **11,293** |

- k = 0.5 would have been chosen in 9 of 10 years from past data alone (w flips between 15 and 20); the exit choice oscillates between 09:45 and 10:00.
- The walked-forward chains earn 89 % and 94 % of the fixed rule — the v2 cell is not a lucky pick; an investor without hindsight would have run essentially the same rule.
- Nothing tuned or deployed; 2024–26 untouched.

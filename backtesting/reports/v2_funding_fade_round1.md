# v2 funding-crowding fade: a second return source beside v1.11

Six predefined candidates fade positioning crowding: when the 24h mean of the last settled 8h funding rate ranks at or above the 90th/95th/98th percentile of its trailing 30 days (crowded longs) and, for break24h, the hour closes below the prior 24h low, go short at the next open; mirrored for crowded shorts. Geometry is fixed (2 ATR stop, 3R target, 96-hour time stop). Signals use settlements published at least one hour earlier and completed hourly candles only.

**All dates were previously inspected. This is development research, not an untouched holdout or evidence of future profitability.** v1.11 and its forward protocol are untouched. Failed candidates and the frozen shortlist/selection are retained.

Training uses 2020-2023 annual closed outcomes at 8bp fills and must be positive standalone (same-budget v1.11 replica for reference: score 410.06, median annual closed $1,199.84). The top eligible candidate per confirmation group is checked on 2024 (v1.11 same budget: $2,854.86). Execution ends December 25 in 2023 and 2024, leaving seven-day gaps. The selection is frozen before 2025-2026 outcomes.

| Candidate | Training score | Median annual closed | Training entries | Eligible training | 2024 closed net | 2024 drawdown | Eligible 2024 |
| --- | ---: | ---: | ---: | --- | ---: | ---: | --- |
| fade_p90_break24h | -2588.23 | $-417.61 | 137 | False | Not shortlisted |  | Not evaluated |
| fade_p90_none | -1521.75 | $-180.68 | 254 | False | $-1,240.55 | 3.45% | False |
| fade_p95_break24h | -1404.94 | $-186.51 | 80 | False | Not shortlisted |  | Not evaluated |
| fade_p95_none | -2653.03 | $-505.22 | 188 | False | Not shortlisted |  | Not evaluated |
| fade_p98_break24h | -1133.23 | $-259.93 | 41 | False | $-760.57 | 1.96% | False |
| fade_p98_none | -2476.09 | $-141.48 | 132 | False | Not shortlisted |  | Not evaluated |

Selected before audit: **None: no candidate passed both gates**.

| Period | Strategy | Actual slippage | Net including open marks | Closed net | Drawdown | Entries | Closed legs |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |

Improvement gate (portfolio v1.11 + fade against v1.11 alone): `{}`. Passed: **False**. No candidate was registered or promoted.

Portfolio drawdowns are the summed bar-close curve plus each sleeve's intrabar excess, an upper bound; single-sleeve drawdowns are intrabar. Annual accounts reset and are not summed as a continuous return. Funding is a crowding feature only; modeled Breakout fees and 3.3bp/day financing are unchanged.

848 earlier logged search slots, 62 earlier lab candidates and these 6 are known research exposure, not a complete trial count. Consumed data cannot become unseen again; only the sealed future period can validate the candidate.

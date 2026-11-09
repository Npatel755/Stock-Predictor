# overnight_1 — Globex overnight hold 18:05 → next 09:30 ET, training 2010–2023 (2026-11-09)

Protocol research/overnight_1/PROTOCOL.md (pre-registered). Rule basis: Topstep/Lucid allow holding past midnight but require flat before the 16:10/16:45 ET
cutoff, so the window is the 18:00 reopen → 09:30 open. 1 contract, 1.75-tick MNQ / 1-tick MES spread, 1 tick slippage/side, $0.61/side. Script
scripts/overnight_1_pilot.py. Gross raw premium: MNQ +7.0 ticks/night (t = 1.55), MES +2.6 ticks/night (t = 2.16) — both inside one round trip.

| variant | net | nights | $/night | +years | 2010–19 | largest-year share | beats placebo |
|---|---:|---:|---:|---:|---:|---:|---:|
| V1_long_all_MNQ | +1,309 | 3231 | +0.40 | 7/14 | +486 | 398% | — |
| V13_short_all_MNQ | -21,308 | 3231 | -6.60 | 1/14 | -14,092 | — | — |
| V12_exit0935_MNQ | +5,152 | 3231 | +1.59 | 9/14 | +2,595 | 112% | — |
| V11_stop_MNQ | +1,667 | 3231 | +0.52 | 7/14 | +811 | 330% | — |
| V3_sunday_MNQ | -3 | 666 | +0.00 | 6/14 | -321 | — | 97/200 |
| V4_mon_thu_MNQ | +1,311 | 2565 | +0.51 | 8/14 | +807 | 182% | 100/200 |
| V5_after_down_day_MNQ | +1,490 | 1108 | +1.34 | 9/14 | +122 | 83% | 129/200 |
| V6_after_up_day_MNQ | +1,459 | 1352 | +1.08 | 7/14 | +694 | 198% | 109/200 |
| V7_contango_MNQ | -558 | 2277 | -0.25 | 7/14 | -924 | — | 67/200 |
| V8_backwardation_MNQ | +3,659 | 195 | +18.76 | 9/12 | +1,860 | 40% | 191/200 |
| V9_reopen_dip_MNQ | +5,724 | 1136 | +5.04 | 10/14 | +2,153 | 54% | 193/200 |
| V14_stress_day_MNQ | -18 | 317 | -0.06 | 8/14 | +648 | — | 105/200 |
| V1_long_all_MES | -5,801 | 3384 | -1.71 | 4/14 | -4,136 | — | — |
| V13_short_all_MES | -27,836 | 3384 | -8.23 | 1/14 | -19,233 | — | — |
| V12_exit0935_MES | -3,406 | 3384 | -1.01 | 5/14 | -3,116 | — | — |
| V11_stop_MES | -6,137 | 3384 | -1.81 | 3/14 | -3,622 | — | — |
| V3_sunday_MES | -486 | 674 | -0.72 | 3/14 | -1,108 | — | 112/200 |
| V4_mon_thu_MES | -5,315 | 2710 | -1.96 | 4/14 | -3,027 | — | 82/200 |
| V5_after_down_day_MES | -2,106 | 1166 | -1.81 | 7/14 | -921 | — | 88/200 |
| V6_after_up_day_MES | -2,318 | 1409 | -1.64 | 4/14 | -2,471 | — | 82/200 |
| V7_contango_MES | -5,935 | 2416 | -2.46 | 4/14 | -4,356 | — | 57/200 |
| V8_backwardation_MES | +2,037 | 200 | +10.19 | 8/12 | +1,549 | 42% | 182/200 |
| V9_reopen_dip_MES | +2,084 | 1191 | +1.75 | 8/14 | +1,149 | 114% | 195/200 |
| V14_stress_day_MES | +672 | 227 | +2.96 | 7/14 | +20 | 228% | 156/200 |

## Verdict
**0 of 20 pass.** The overnight premium on the index futures is real but small over this window — ≈7 ticks/night on NQ, 2.6 on ES, neither statistically
strong — so unconditional holding nets ≈ $0.40/night on MNQ and loses on MES. Two conditional variants carry real information: holding only on nights when
the 18:00 reopen gapped down vs the 16:00 close (V9: MNQ +$5,724 / 1,136 nights / 10 of 14 years / beats 193 of 200 random night sets; MES +$2,084, 195/200)
and holding only in VIX backwardation (V8: MNQ +$3,659 / 195 nights / 9 of 12 years / 191 of 200). Both fail the gates: V9 has one year with 54% of the net
and MES only 8/14 years; V8 has ~14 nights a year. V9 is the strongest single result of the whole project after costs (≈ 10 ticks/night edge, 10/14 years)
and is a candidate for a pre-registered follow-up (reopen-dip size thresholds, combined with backwardation), with 2024–25 still sealed.

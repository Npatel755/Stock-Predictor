# qc_1 T2 — variance risk premium as a point-in-time day state (training 2010–2023)

Protocol: research/qc_1/PROTOCOL.md (pre-registered 2026-11-08). Script: scripts/qc_1_vrp_pilot.py (extstate_1 machinery).
State: prior-close VIX²/252 minus the 21-session mean of realized daily variance from ES 15-min RTH returns, ranked over the prior
504 sessions; states vrp_hi (top tercile), vrp_lo (bottom tercile), vrp_pos / vrp_neg (sign). Costs: 1.75-tick MNQ / 1-tick MES spread,
1 tick slippage, $0.61/side. Gates: net > 0, ≥10/14 years, no year > 40%, ≥95% placebo, ≥100 trades. 2024–25 untouched, 2026 never loaded.

## T1 — day direction 09:45 → 15:54 ET (placebo: 20 random-direction draws on the same days)
| product | state | side | net | days | +years/14 | placebo pct |
|---|---|---|---:|---:|---:|---:|
| MNQ | vrp_hi | long | +2,182 | 888 | 8 | 85% |
| MNQ | vrp_pos | long | -1,898 | 3193 | 5 | 75% |
| MNQ | vrp_lo | long | -3,793 | 1170 | 5 | 35% |
| MNQ | vrp_neg | long | +468 | 22 | 1 | 75% |
| MNQ | vrp_hi | short | -7,678 | 888 | 1 | 30% |
| MNQ | vrp_pos | short | -17,867 | 3193 | 2 | 25% |
| MNQ | vrp_lo | short | -3,449 | 1170 | 5 | 65% |
| MNQ | vrp_neg | short | -604 | 22 | 2 | 45% |
| MES | vrp_hi | long | -653 | 888 | 8 | 85% |
| MES | vrp_pos | long | -7,612 | 3193 | 3 | 90% |
| MES | vrp_lo | long | -5,097 | 1170 | 2 | 65% |
| MES | vrp_neg | long | +57 | 22 | 1 | 60% |
| MES | vrp_hi | short | -8,173 | 888 | 1 | 5% |
| MES | vrp_pos | short | -24,127 | 3193 | 2 | 0% |
| MES | vrp_lo | short | -6,532 | 1170 | 3 | 50% |
| MES | vrp_neg | short | -276 | 22 | 2 | 65% |

## T2 — state filter on the fixed 15m MNQ momentum rule (placebo: 20 random same-size day sets per year)
| state | days | net | trades | +years/14 | placebo mean | placebo pct |
|---|---:|---:|---:|---:|---:|---:|
| vrp_hi | 909 | +5,884 | 1136 | 7 | +4,435 | 70% |
| vrp_lo | 1213 | +2,735 | 1447 | 4 | +1,099 | 70% |
| vrp_neg | 22 | -339 | 29 | 1 | +478 | 15% |
| vrp_pos | 3285 | +7,152 | 4006 | 5 | +5,897 | 90% |

## Verdict
**REJECTED — 0 of 20 pass.** Short-side day bets lose heavily in every state (the index drifts up intraday on average); the only
positive long bet (MNQ on high-VRP days, +$2,182 / 888 days) is 8 of 14 years and beats 85% of random-direction draws (gate 95%).
As a filter, high-VRP days lift the fixed momentum rule to +$5.9k vs +$4.4k for random day sets of the same size (70th percentile);
the sign states carry nothing. The variance risk premium is an option-selling premium; it does not time intraday index direction
at micro costs. External-state family (VIX level, term structure, 200-day trend, VRP) is now closed for day-direction and day-filter use.

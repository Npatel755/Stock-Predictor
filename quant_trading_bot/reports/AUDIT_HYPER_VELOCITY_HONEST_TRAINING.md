# Hyper-Velocity Fast-Track Fortress: honest re-count for the evaluation goal (training 2010-23 only)

Script: `scripts/audit_hyper_velocity_honest_train.py` (Antigravity's rules exec'd unchanged; validation/test never loaded). Raw:
`AUDIT_HYPER_VELOCITY_HONEST_TRAINING.json`. Port check: published rules reproduce Antigravity's training counts (13.2% of 3,384
windows passed, 0 failed). 1-second resolved fills (from `RESOLVE_CRABEL_1S_TRAINING`) change little, so the resolved column is shown.

## Per attempt, all 3,384 windows of 100 sessions
| policy | passed | failed | reset at -$400 | still open (of which stuck below -$400) | headline "pass %" |
|---|---|---|---|---|---|
| P1 as published (1 micro at -$400) | 12.9% | 0% | - | 87.1% (66.0%) | 100% |
| P2 reset when the account closes at or below -$400 | 8.7% | 0% | 70.2% | 21.1% | 100% |
| P3 no floor | 18.6% | 32.6% | - | 48.8% (27.7%) | 36.4% |
| zero-edge control, P1 | 6.6% | 0% | - | 93.4% (74.9%) | **100%** |

The headline metric (passes / (passes + fails)) reads 100% pass, 0% ruin even with the edge removed.

## Time to a funded account, from every training session, counting resets (cap 252 sessions)
| policy | funded <= 21 | <= 63 (~3 mo) | <= 126 | <= 252 | median sessions | resets/fails paid |
|---|---|---|---|---|---|---|
| P1 as published | 3.0% | 9.5% | 15.2% | 21.7% | > 252 | 0 |
| P2 reset at -$400 | 7.7% | 27.0% | 46.7% | 63.9% | 139 | 4.6 |
| P3 no floor | 5.7% | 22.7% | 38.3% | 58.0% | 192 | 1.0 |
| zero-edge control, P2 | 6.4% | 22.5% | 37.9% | 57.4% | 196 | - |

Pre-declared recommendation rule (>= 50% funded within 63 sessions in both halves, >= 35% for 2022-23 starts): **not met by any
policy** (best, P2: 12.3% for 2010-16 starts, 43.0% for 2017-23, 50.6% for 2022-23).

## Notes
- No trades pass the filters in 2010-13 or 2017 (fixed 15-point range and VIX >= 15 gates). At NQ ~28,000 the range gate is met almost
  every day (on the 2026 split trade days ~ sessions: 13.1 vs 14.7), so training behaviour differs from today's; 2022-23 is the
  closest regime, and the 1-micro edge there is about flat.
- "14 trade days (~2.8 wks)" for passers is ~42 sessions (~8.5 weeks) on training.
- The edge itself is real on training (+$3.90 per micro per trade, PF 1.20, 1-second resolved), but at 12-18 micros it adds only about
  5 points of "funded within 3 months" over a zero-edge strategy of the same size (27.0% vs 22.5%).
- Validation and test have been read by at least five Fortress rounds, each designed after the previous round's holdout numbers;
  they are spent for this family.

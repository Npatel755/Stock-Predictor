# Crabel 16/28/120 (free-roll sprint, Vol-Adaptive / Hyper-Velocity Fortress): 1-second resolution, training 2010-23

Scripts: `scripts/fetch_1s_crabel_train.py` (Databento GLBX.MDP3 ohlcv-1s, by instrument_id, 09:45-15:56 ET), `scripts/resolve_crabel_1s_train.py`
(rules and verdict declared before the data was seen). Raw: `RESOLVE_CRABEL_1S_TRAINING.json`. Spend: $17.43 estimated (ledger $17.98 counting
retries as billed). Training split only; no 2024-26 data was requested.

## What was resolved
221 training days had a 1-minute bar holding both the stop and the entry or target. Antigravity's simulator never checks the stop on the entry bar,
and it takes the target before the stop. Those days were re-simulated on 1-second bars with identical rules; all other days are unambiguous on
1-minute bars.

- Data check: 81,641 / 81,641 minutes have the same high/low in the 1-second bars (100%).
- Outcome: 214 of 219 traded days resolve exactly to the published path and 5 to the worst case. 3 conflicts remain inside a single second
  (stop-first).
- Why: a breakout minute usually opens at its stop-side extreme and then runs through the level (example 2022-03-08 10:00 ET short: the high printed
  at 10:00:00, the breakout at 10:00:19).

## Result (prior-day VIX, 1 micro, 1.30 pt friction)
| fills | avg / trade | PF | net 2010-23 | free-roll 6c net | 6c days >= $150 / yr |
|---|---|---|---|---|---|
| published (optimistic) | +$4.17 | 1.213 | +$4,741 | +$28,446 | 32.3 |
| worst case (my earlier bound) | -$1.53 | 0.929 | -$1,743 | -$10,461 | 27.3 |
| **1-second resolved** | **+$3.90** | **1.198** | **+$4,436** | **+$26,616** | **32.0** |

Pre-declared verdict (resolved avg > $0 and PF >= 1.10): **the edge is real on training.** The published fills were nearly right, and the worst-case
bound I reported earlier was too pessimistic.

## What still does not hold
- The Fortress "100% pass" divides passes by passes + ruins. Over all windows the resolved figures are 9.2% within 100 sessions and 20.1% within 252.
  "0% ruin" comes from the 1-micro floor: about 84% of the non-passing accounts end near -$400 trading 1 micro.
- By year (1 micro, resolved): the money is made in 2019-21 (+$831 / +$1,383 / +$1,666). 2022 is +$29 (PF 1.01) and 2023 -$67 (PF 0.97). The 16-point
  stop and 28-point target are fixed in points, so at NQ ~28,000 they are about 0.06% / 0.10% of price, tighter than anything in training.
- The 2024-26 splits have been read by several Fortress rounds and are spent for this family.

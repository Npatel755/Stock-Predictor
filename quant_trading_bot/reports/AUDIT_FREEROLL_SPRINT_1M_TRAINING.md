# Audit: Antigravity scale-out free-roll sprint on 1-min NQ (Claude, 2026-11-09; training 2010-23 only)

Strategy audited: `scripts/research_scaleout_freeroll_runner_train.py` - Crabel 15m opening range, breakout in the direction of the opening
gap from 09:45, 16-pt stop, bank half at +28 pts, stop on the rest to entry +1, runner to +100/+120 pts, VIX >= 15, -$400 / +$1,750 day limits.
Script: `scripts/audit_freeroll_sprint_1m_train.py` -> `AUDIT_FREEROLL_SPRINT_1M_TRAINING.json`.

## Reproduction
Antigravity's code, re-implemented line for line: 6 micros, runner +120 = **+$28,861.20, worst day -$207.60** - exactly their claim.

## Defects in the original simulator
| # | defect | effect |
|---|---|---|
| 1 | Stops always fill exactly at 16 pts, even when the bar opens beyond them | worst day is always the theoretical stop |
| 2 | Target checked before the stop when one 1-min bar touches both | optimistic (no effect here in practice) |
| 3 | The entry bar is never checked for the stop | breakout bars that reverse through the stop are ignored |
| 4 | Breakout fills at the range edge even when the bar opens beyond it | small |
| 5 | VIX >= 15 gate uses the SAME day's VIX close (published 16:15 ET) | look-ahead; small effect |

## Corrected results (6 micros, runner +120)
| version | net 2010-23 | worst day | $150+ days/yr | 2010-19 / 2020-23 |
|---|---|---|---|---|
| Antigravity code as written | +$28,861 | -$208 | 31.9 | +$8,100 / +$20,762 |
| worst case: every ambiguous entry bar stopped | -$10,497 | -$208 | 26.9 | +$6,126 / -$16,622 |
| fair: OHLC path walk, all fixes, engine friction 1.61 pts | **+$23,137** | -$211 | **31.9** | +$6,922 / +$16,215 |
| entry only after a 1-min CLOSE beyond the range (no ambiguity) | **+$3,023** | -$211 | 28.4 | +$2,677 / +$346 |

- 212 of 1,137 trade days (18.6%) have an entry bar containing both the breakout level and the stop; 1-min data cannot order them.
  Under the fair path walk those days lose -$6,184, so the fair number is not flattered by them.
- The edge is ~1.7 pts per contract per trade after costs; each extra point of round-trip slippage costs ~$13.6k over 14 years at 6 micros.
  About 7 extra ticks per round trip on opening breakouts erases it.
- Delaying entry by one bar (close confirmation) removes almost all of it: the profit is concentrated in the first moments of the breakout.

## Verdict
Plausible but not proven. The headline survives fair 1-min execution, but it depends on stop-order fills right at the range edge and on
intrabar sequencing the data cannot resolve. Not deployable as a payout engine until breakout fills are checked on 1-second data
(MNQ bbo-1s 2023 was bought for orderflow_1 but is not on this machine; ~$29 to re-download) or on a forward paper record.
At 12 micros the corrected worst day is -$423 (fair) but a gap-through on a full 12-micro stop is the DLL risk to watch.

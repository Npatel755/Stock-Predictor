# extstate_2 — CBOE SKEW prior-close states (training 2010–23 only)

Protocol research/extstate_2/PROTOCOL.md; script scripts/extstate_2_pilot.py; raw reports/EXTSTATE_2_TRAINING.json. Data data/external/SKEW_History.csv (free, CBOE).
Only the CBOE close before the decision is used. 2024–26 not loaded. 27 pre-registered cells, nothing else tried.

## Result: no stand-aside and no new rule is adoptable (0 of 27 by the pre-registered rule) — but SKEW *ranks* both existing rules the same way
| state (prior close) | dip nights (v2, 490 n, $24/night) | All-Weather v2 1c days (1,097 d, +16,520) |
|---|---|---|
| SKEW 1y-pct low tercile | 165 n, **$44.8**/night, removal worse than 199/200 random | 354 d, +8,868 (54 % of net), 185/200 |
| SKEW 1y-pct high tercile | 202 n, $11.7/night, 13/200 | 447 d, +3,747, 16/200 |
| SKEW 5d change down | 260 n, $29.9 | 559 d, +11,766 (71 %), 181/200 |
| SKEW 5d change up | 230 n, $17.5 | 538 d, +4,755, 16/200 |
| SKEW below 20d mean | 212 n, **$40.6**/night, 196/200 | 412 d, +11,051 (67 %), **199/200** |
| SKEW above 20d mean | 167 n, $10.6/night, 18/200 | 416 d, +1,842, 5/200 |

- Every state is net *positive* for both rules, so rule (a) of the protocol (removed set net negative) fails everywhere: no filter.
- T2 (all nights, MNQ 18:05→09:45 by SKEW state): best is "SKEW above 20d mean" +6,897 / 1,246 n / 9 years / DD 3,711 / 154 of 200 — no unconditional SKEW premium.
- The ordering is the same across an overnight mean-reversion rule and an intraday trend/breakout rule that share no trades: when SKEW (tail-risk
  pricing) is low or falling relative to its recent past, both earn 3–4× more per unit. Low/falling SKEW = tails cheap = the market is *not* bracing,
  which is when both the reopen-dip recovery and daytime continuation have paid. High/rising SKEW: still positive, ~1/4 the rate.
- Statistical note: 27 cells; two near-200/200 readings on independent targets with the same sign is more than multiplicity would give (expected ~1 at
  the 195/200 level), but the two targets share calendar time (2020–22 contributes to both), so the coherence is partly one regime.

## Follow-up (pre-registered next, sizing_3)
SKEW is a candidate *sizing* state rather than a filter: 2 contracts when the prior close has SKEW below its 20d mean, 1 otherwise, on the
overnight dip v2 leg, the All-Weather 1c leg, and the book_a pair — judged on DD < 2k, breach MC and years, training only. Nothing deployed from extstate_2.

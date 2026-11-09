# qc_1 T1 (exec_1) — passive-limit execution of short-horizon fades, MNQ Apr–Dec 2023 (bbo-1s + trades)

Protocol: research/qc_1/PROTOCOL.md (pre-registered 2026-11-08). Script: scripts/qc_1_exec_pilot.py. Data: 235 RTH sessions,
4,581,790 quote-seconds. Hypothesis: the mass_1m fades lost ≈ one marketable round trip; posting at the bid/ask (fill only when a later
trade prints through the limit) removes spread+slippage and might make them positive. Signals fire once per threshold crossing (1-min VWAP
stretch z ∈ 1.5/2.0/2.5 in ATR units; 5-min move ≥ 2/3 ATR), fade direction; passive entry window W s, passive target T ticks, marketable
stop 12 ticks, time-out H min, flat 15:55; $0.61/side. Placebo: same passive fill model on 20 random signal sets (same count per session,
random direction). Gates: net > 0, ≥ 7/9 months, ≥ 200 fills, ≥ 95% of placebos, ≥ +2 ticks/fill over placebo mean.

## Result: **0 of 60 configurations pass**
- Passive fill rate 84%–92% of signals within W — the limit is almost always hit, which is the problem: fills are adversely selected.
- Passive net per fill -3.04 to -2.40 USD (every config negative); marketable versions -13,218 to -4,318, passive -12,720 to -4,043:
  posting saves only $211 per config on average, far less than the ~$5.40/round-trip the cost model charges, because the fills that
  arrive are the ones where price keeps going against the fade.
- Requiring a 2-tick trade-through (queue stress) costs a further $1,292 per config.
- Versus random passive entries the fades gain -0.06 ticks/fill on average (best config beats 20/20 placebos); the mom5 2.0 configs beat 20/20 but still lose $11,214+.
- No configuration had a positive month out of 9 (best 0/9).

Top 8 by passive net:
| signal | W | T | H | fills (rate) | passive net | per fill | marketable | thr=2 ticks | placebo mean | beats | +months |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| mom5 3.0 | 30 | 8 | 5 | 1508 (86%) | -4,043 | -2.68 | -4,463 | -4,870 | -4,200 | 15/20 | 0/9 |
| mom5 3.0 | 30 | 8 | 15 | 1508 (86%) | -4,061 | -2.69 | -4,469 | -4,883 | -4,200 | 14/20 | 0/9 |
| mom5 3.0 | 30 | 16 | 5 | 1507 (86%) | -4,106 | -2.72 | -4,352 | -4,702 | -4,211 | 15/20 | 0/9 |
| mom5 3.0 | 30 | 16 | 15 | 1506 (86%) | -4,111 | -2.73 | -4,318 | -4,706 | -4,205 | 15/20 | 0/9 |
| mom5 3.0 | 60 | 8 | 5 | 1573 (90%) | -4,177 | -2.65 | -4,463 | -5,119 | -4,318 | 16/20 | 0/9 |
| mom5 3.0 | 60 | 8 | 15 | 1573 (90%) | -4,191 | -2.66 | -4,469 | -5,127 | -4,317 | 16/20 | 0/9 |
| mom5 3.0 | 60 | 16 | 5 | 1572 (90%) | -4,287 | -2.73 | -4,352 | -4,949 | -4,328 | 9/20 | 0/9 |
| mom5 3.0 | 60 | 16 | 15 | 1571 (90%) | -4,290 | -2.73 | -4,318 | -4,947 | -4,325 | 8/20 | 0/9 |

## Verdict
**REJECTED.** Passive execution does not rescue short-horizon fades on MNQ: a resting limit in a 1–2-tick book fills precisely when the move
continues (adverse selection), so the spread "earned" is given back and more. Market-making-style edges need queue priority, rebates and
inventory management that a single micro contract from a retail account cannot replicate. This closes the "institutional execution transfer"
idea at this resolution; the engine's marketable-fill cost model stays as the conservative standard for all candidates.

# extstate_1 result: prior-close external state (VIX, VIX3M/VIX slope, ES 200-day) on MNQ/MES, training 2010-2023 (protocol research/extstate_1/PROTOCOL.md)

**Verdict: REJECTED (0 of 20 day-direction + 10 filter variants pass).** Validation untouched. Costs as anomaly_1. State known at prior close (CBOE VIX/VIX3M history, ES daily close from the 1-min data).

## T1 day direction (09:45 -> 15:54, 1 contract)

| product | state | side | days | net | +yrs/14 | placebo pct |
|---|---|---|---:|---:|---:|---:|
| MNQ | contango | L | 2,989 | -6,244 | 4 | 1.00 |
| MNQ | above200 | L | 2,057 | -8,644 | 3 | 0.50 |
| MNQ | vix_lo | L | 1,398 | +2,092 | 5 | 0.85 |
| MNQ | vix_dn5 | L | 1,708 | -5,523 | 5 | 0.50 |
| MNQ | contango_above200 | L | 1,953 | -6,300 | 3 | 0.60 |
| MNQ | backwardation | S | 245 | -5,868 | 4 | 0.15 |
| MNQ | below200 | S | 525 | -10,108 | 1 | 0.15 |
| MNQ | vix_hi | S | 933 | -8,392 | 2 | 0.25 |
| MNQ | vix_up5 | S | 1,470 | -13,513 | 3 | 0.15 |
| MNQ | backwardation_below200 | S | 132 | -5,946 | 1 | 0.20 |
| MES | contango | L | 2,989 | -10,389 | 2 | 0.95 |
| MES | above200 | L | 2,057 | -11,537 | 1 | 0.25 |
| MES | vix_lo | L | 1,398 | -2,386 | 3 | 0.95 |
| MES | vix_dn5 | L | 1,708 | -5,854 | 5 | 0.70 |
| MES | contango_above200 | L | 1,953 | -8,950 | 2 | 0.60 |
| MES | backwardation | S | 245 | -5,275 | 3 | 0.05 |
| MES | below200 | S | 525 | -9,706 | 1 | 0.00 |
| MES | vix_hi | S | 933 | -9,202 | 2 | 0.10 |
| MES | vix_up5 | S | 1,470 | -13,271 | 2 | 0.00 |
| MES | backwardation_below200 | S | 132 | -4,935 | 1 | 0.00 |

Every state-conditioned day bet loses, most of them worse than random direction (placebo pct 0.05-0.6): shorting backwardation / high-VIX / below-200d days in 2010-23 fought the index drift and the V-shaped recoveries; long contango/above-200 days collects the drift but it is smaller than costs on a micro.

## T2 state filter on the fixed 15m MNQ momentum rule (unfiltered: +$5,714, 4,145 trades, 5 of 14 years positive)

| state | days | net | trades | +yrs/14 | active yrs (>=10 trades) pos | placebo pct (same day-count random mask) | placebo mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| contango | 3,073 | +793 | 3,743 | 4 | 4/14 | 0.05 | +4,060 |
| backwardation | 251 | +5,166 | 319 | 7 | 7/13 | 0.95 | +1,732 |
| vix_hi | 959 | +8,850 | 1,199 | 7 | 7/14 | 0.65 | +7,193 |
| vix_lo | 1,452 | -3,811 | 1,731 | 2 | 2/14 | 0.05 | -665 |
| above200 | 2,116 | +543 | 2,547 | 4 | 4/12 | 0.20 | +2,450 |
| below200 | 543 | +8,721 | 689 | 4 | 4/8 | 0.85 | +6,965 |
| vix_up5 | 1,502 | +1,448 | 1,864 | 4 | 4/14 | 0.35 | +2,347 |
| vix_dn5 | 1,768 | +4,412 | 2,124 | 5 | 5/14 | 0.45 | +3,152 |
| contango_above200 | 2,005 | -376 | 2,415 | 4 | 4/12 | 0.25 | +816 |
| backwardation_below200 | 137 | +4,631 | 174 | 5 | 5/6 | 1.00 | +1,255 |

Finding worth recording: the two *stress* filters pass the placebo gate - trading the momentum rule only on VIX-backwardation days (+$5,166 on 319 trades, beats 95% of random day masks; backwardation & below-200d: +$4,631 on 174 trades, beats 100%). Intraday momentum on index futures earns when the vol term structure is inverted, i.e. on crisis days; on calm days (contango, low VIX) it is at or below random (+$793 / −$3,811 vs placebo means +$4,060 / −$665).
Why it still fails: backwardation occurs in only a handful of years (2010-11, 2015-16, 2018, 2020, 2022), so the filtered rule is positive in 7 of 14 calendar years and the profit is concentrated by construction - the same regime dependence, now with a named cause. 319 trades in 14 years (~23/yr) is also too thin to carry a funded account alone, and the 2010-19 half of it is not separately significant.

## Consequence
External daily state does not create an intraday edge; it explains where the existing one lives (stress regimes). The practical reading for the five paper ledgers: their trend/breakout sleeves should be expected to earn in high-VIX / backwardated periods and bleed in calm contango - a point-in-time monitor of VIX3M/VIX on the dashboard is cheap and honest, but no new candidate follows from this round. No further filter grids.

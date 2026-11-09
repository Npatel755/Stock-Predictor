# dplus_3 - opening-leg checks on ag_arch_d_plus_v2 (training 2010-23 only; protocol research/dplus_3/PROTOCOL.md)

Base (fixed engine, $150 budget, strict 1c router): +$17,576 on 1,398 trades ($12.57/trade), closed DD $783, marked DD $882 (worst 2022-08-19), 12/14 years, 0 touches of $2k.
Verdict: **nothing adopted, nothing changed.** The leg is not execution-fragile and its drawdown is its own, not the gates'.

## A. Macro-event-day stand-aside (post-hoc removal from the routed list, 200 count-matched random day removals)
| cell | days removed | trades removed | removed net | kept net | kept years>0 | kept marked DD | placebo worse /200 | adopt |
|---|---|---|---|---|---|---|---|---|
| FOMC statement days | 24 | 33 | +$691 | +$16,885 | 12 | $882 | 58 | no |
| CPI / Employment (08:30) days | 97 | 128 | +$440 | +$17,136 | 11 | $843 | 175 | no |
| all three | 120 | 160 | +$1,118 | +$16,458 | 11 | $843 | 156 | no |
Event days are net positive for D+ v2 (FOMC days are *better* than average: only 58/200 random same-count removals do worse), and the removed sets never clear the 190/200 bar. Same conclusion as news_round1 on the Codex sleeves; the AG intraday sleeves do not need an event calendar. Approximation declared: the router was not re-run after removal.

## B. Execution stress (report only)
| cell | net | $/trade | years>0 | marked DD | retention |
|---|---|---|---|---|---|
| base (1 tick slippage + 1 tick spread) | +$17,576 | 12.57 | 12 | $882 | 1.00 |
| slippage 2 ticks | +$15,851 | 11.29 | 10 | $862 | 0.90 |
| spread 2 ticks | +$17,576 | 12.57 | 12 | $882 | 1.00 |
| both | +$16,000 | 11.40 | 10 | $862 | 0.91 |
Engine fact: adverse fill = slippage + spread/2 (+ impact) ticks, rounded to the tick, so the base already pays 2 ticks/side (1.5 rounded up) and "spread 2" is identical to base; "slippage 2" (2.5 -> 3 ticks/side) costs 10 % of net. Retention 0.91 under both clears the 50 % veto by a wide margin; the leg keeps $11.40/trade with a 3-tick adverse fill. Years>0 drops to 10 because 2013 and 2015 are small positives at base.

## C. Engine risk-gate sensitivity (report only)
| cell | net | trades | marked DD |
|---|---|---|---|
| daily_loss $200 | +$17,424 | 1,398 | $882 |
| daily_loss $400 (base) / off | +$17,576 | 1,398 | $882 |
| hard_drawdown $1,000 | +$14,028 | 1,243 | $727 |
| hard_drawdown $2,000 (base) / off | +$17,576 | 1,398 | $882 |
Neither gate ever binds at 1 contract: the $882 marked DD is the strategy's own. A $1,000 per-sleeve hard lock would cut DD by $155 at the cost of 20 % of net - not worth it; left at base.

Not evidence for 2024-26 (sealed). Script: scripts/dplus_3_pilot.py; data: reports/DPLUS_3_TRAINING.json.

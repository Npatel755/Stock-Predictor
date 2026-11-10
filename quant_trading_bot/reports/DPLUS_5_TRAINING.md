# dplus_5 - gap-alignment state as a sizing input for ag_arch_d_plus_v2 (training 2010-23 only; protocol research/dplus_5/PROTOCOL.md; derived from dplus_4)

S1 = D+ v2 with 2 contracts on Crabel 15m drives that agree with the opening gap (09:30 15m-bar open vs previous RTH close), 1 contract on everything else.
Post-hoc doubling on the routed D+ v2 list; engine check: the Crabel sleeve at 2c under a $300 budget reproduces exactly 2x on all 493 common trades (max |2*n1 - n2| = $0)
and admits 41 extra trades, so the paper implementation keeps the $150-per-contract budget (same trade set as research).

| config | net | $/trade | years>0 | closed DD | marked DD | $2k touches | 1y breach (20d blocks, 2,000 paths) | net / marked DD |
|---|---|---|---|---|---|---|---|---|
| D+ v2, 1c | +$17,576 | 12.57 | 12/14 | $783 | $882 | 0 | 0.0 % | 19.9 |
| D+ v2, flat 2c (linear; engine with hard-DD lock: +$27,327 / $1,453) | +$35,152 | 25.14 | 12/14 | $1,566 | $1,765 | 0 | 7.3 % | 19.9 |
| **S1: 2c on gap-continuation Crabel drives** | **+$23,142** | 16.55 | 12/14 | $999 | **$1,027** | 0 | **0.05 %** | **22.5** |
| C1 control: 2c on gap-fade Crabel drives | +$20,116 | 14.39 | 11/14 | $887 | $1,050 | 0 | 0.05 % | 19.2 |

Gates: net/DD above both references (22.5 vs 19.9) pass; marked DD < $1,453 and 0 touches pass; beats the mirror control on net (+$3,026) and marked DD pass;
1-year breach <= 1 % pass (0.05 %); years >= 11 pass. **5 of 5.** The doubled set adds +$5,566 for +$145 of marked drawdown; the control adds +$2,540 for +$168 -
the state, not the extra size, carries the improvement. The flat-2c engine result (+$27,327 / $1,453) is the honest 2c comparison: S1 earns 85 % of it with 71 % of its drawdown.

Decision: deploy as `ag_arch_d_plus_v2_gapsize` in the Future-strategies section (needs ~$150 more cushion than D+ v2 1c; switch point from zero is immediate under a
$2k floor on training marks, but it is one-split, derived evidence - the forward record decides). Paper only, no routing. Not evidence for 2024-26 (sealed).
Script: scripts/dplus_5_pilot.py; data: reports/DPLUS_5_TRAINING.json.

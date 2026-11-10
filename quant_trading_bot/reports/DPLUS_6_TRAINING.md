# dplus_6 - does gap alignment carry to the D+ v2 trend sleeves? (training 2010-23 only; protocol research/dplus_6/PROTOCOL.md)

Verdict: **no - 0 of 2 sleeves; nothing adopted; ag_arch_d_plus_v2_gapsize unchanged.**

| sleeve | aligned trades | aligned $/trade (years>0) | opposed trades | opposed $/trade (years>0) | placebo worse /200 | real? |
|---|---|---|---|---|---|---|
| MNQ 60m trend | 673 | 9.90 (9/14) | 4 | -20.75 | 148 | no - trend direction embeds the gap; the split is degenerate |
| MES 30m trend | 151 | 13.16 (7/14) | 77 | 11.74 (7/14) | 115 | no |

| sizing cell (2c on the named set, 1c else; post-hoc doubling) | net | marked DD | 1y breach | net / DD |
|---|---|---|---|---|
| S1 gap-sized Crabel (dplus_5, deployed) | +$23,142 | $1,027 | 0.05 % | 22.5 |
| S2 + aligned 60m trend | +$29,804 | $1,681 | 4.6 % | 17.7 |
| C2 + opposed 60m trend (4 trades) | +$23,059 | $1,075 | 0.05 % | 21.5 |
| S3 + aligned MES trend | +$25,129 | $1,113 | 0.2 % | 22.6 |
| C3 + opposed MES trend | +$24,046 | $1,125 | 0.05 % | 21.4 |
| S4 all aligned 2c | +$31,791 | $1,654 | 5.5 % | 19.2 |

S2/S4 are flat 2c on the 60m sleeve in disguise (breach odds 4.6-5.5 %); S3's 22.6 vs 22.5 is within noise and its state fails the placebo, so by the
pre-registered rule it is not adopted. The gap-alignment effect is specific to the Crabel 15m open drive - the overnight move continuing through the
open - which is where the mechanism says it should live. Gap-state research on D+ is closed. Not evidence for 2024-26 (sealed).
Script: scripts/dplus_6_pilot.py; data: reports/DPLUS_6_TRAINING.json.

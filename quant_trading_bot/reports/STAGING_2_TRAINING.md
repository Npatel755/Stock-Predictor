# staging_2 - gap-sized D+ as the opening leg of the funded ladder (training 2010-23 only; protocol research/staging_2/PROTOCOL.md; derived from dplus_5)

Same provisional floor model as staging_1 (trailing $2k, lock at +$2.1k to +$100; rule semantics still need prop-firm confirmation). Legs: L1 overnight v2
(490 nights, +$11,797), L2 All-Weather 1c (1,590 trades, +$16,520), L3 D+ v2 (1,398, +$17,576), L3G = L3 with 2 contracts on the 261 gap-continuation Crabel drives (+$23,142).

157 monthly 12-month starts (variant A intraday marks = variant B closed equity here - no leg breached either way):

| policy | 12m survival | median 12m net | p10 12m net | locked within 12m | full 2010-23 path (restart on breach) |
|---|---|---|---|---|---|
| S_3 static D+ v2 1c | 100 % | +$526 | -$86 | 28 % | +$17,576, 0 breaches |
| S_3G static gap-sized D+ | 100 % | +$783 | -$26 | 32.5 % | +$23,142, 0 breaches |
| P_L3 staged from D+ v2 (documented plan) | 100 % | +$526 | -$86 | 28 % | +$63,024, 0 breaches |
| **P_L3G staged from gap-sized D+** | **100 %** | **+$783** | **-$26** | **32.5 %** | **+$67,940, 0 breaches** |

1-year block-bootstrap breach of the $2k floor (20-trading-day blocks, 2,000 paths; A intraday marks / B closed equity):

| policy | A | B |
|---|---|---|
| S_3 static D+ v2 1c | 0.1 % | 0.0 % |
| S_3G static gap-sized D+ | 0.0 % | 0.0 % |
| P_L3 staged from D+ v2 | 0.9 % | 0.3 % |
| P_L3G staged from gap-sized D+ | 1.1 % | 0.4 % |

Gates (P_L3G vs P_L3): survival >= pass (100 % = 100 %); median 12m net >= 1.2x pass (+$783 vs +$526); p10 >= pass (-$26 vs -$86); bootstrap breach A <= 1 % **FAIL (1.1 %)**.
**3 of 4 - not adopted by rule; research/DEPLOYMENT_PLAN.md unchanged (Stage 0 = D+ v2 1c).**

Reading: as a stand-alone opener the gap-sized leg dominates D+ v2 on every measure (0.0 % vs 0.1 % breach alone). The extra ladder breach odds come
from downstream: it locks the floor within 12 months in 32.5 % of starts vs 28 %, so more paths reach the Book A / SKEW-book stages, where the
ladder's drawdown actually lives. The trade on offer is +$257 of median first-year net for +0.2 pt of one-year ladder breach odds - a deployment-policy
choice recorded for Nick, not a strategy tune. The gap-sized ledger keeps building its forward record in the Future section either way.
Not evidence for 2024-26 (sealed). Script: scripts/staging_2_pilot.py; data: reports/STAGING_2_TRAINING.json.

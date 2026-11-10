# payout_1 - a configuration whose typical winning trade / day clears $150 (training 2010-23 only; protocol research/payout_1/PROTOCOL.md)

Nick's goal: "whenever it trades it will usually get a trade worth more than $150" (the 5-winning-day >= $150 payout rule). Per-trade dollars = size x
distance, so the round measured (1) what size each frozen leg needs, (2) what that size costs under the static $2k floor + $1k daily loss limit, and
(3) whether wider targets could do it with less size.

## Step 1-2: smallest size k* with median winning trade AND median winning day >= $150 (linear scaling; 157 monthly 12-month starts)
| configuration | k* | median win trade / day at k* | $150+ days / yr | marked DD (linear) | static breach | $1k DLL hit | verdict |
|---|---|---|---|---|---|---|---|
| overnight v2 | 4 | $163 / $163 | 10.7 | $7,909 | 10.2 % | 28.0 % | no |
| All-Weather 1c | 4 | $194 / $238 | 18.9 | $5,594 | 16.6 % | 20.4 % | no |
| D+ v2 | 4 | $182 / $186 | 20.6 | $3,529 | 0.6 % | 16.6 % | no (DLL) - and see engine check |
| **gap-sized D+** | **3** | **$159 / $165** | 19.6 | $3,081 | 0 % | 10.8 % (linear) | **engine-exact below** |
| Book A | 4 | $182 / $206 | 27.1 | $8,174 | 15.9 % | 29.3 % | no |
| Book A SKEW | 3 | $195 / $213 | 27.8 | $9,534 | 15.9 % | 39.5 % | no |

## Step 3: wider targets (D+ v2, 1c; cells declared in the protocol)
| cell | net | trades | median win trade | share of winners >= $150 |
|---|---|---|---|---|
| base (Crabel 3.5R, 60m 4R) | +$17,576 | 1,398 | $45.5 | 14.8 % |
| Crabel target 5R / 7R | +$17,370 / +$17,479 | 1,394 / 1,393 | $45.5 | 14.5 / 14.7 % |
| 60m trend target 6R / 8R | +$17,238 / +$17,009 | 1,393 / 1,389 | $45.5 | 14.2 / 13.9 % |
| both wider | +$17,030 | 1,388 | $45.4 | 13.9 % |
Wider targets change nothing: the winners are capped by the time exits (hold_bars), not by the targets. Per-trade dollars come from size only.

## Engine-exact check (the engine's $150-per-contract budget and its unscaled $2,000 per-sleeve hard-drawdown lock applied)
| configuration | trades | net 2010-23 | $/trade | years>0 | closed DD | median win trade | winners >= $150 | median win day | win days >= $150 | $150+ days/yr | worst day | static breach | DLL | median 12m net |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D+ v2, 3c | 1,228 | +$35,930 | 29.26 | 12/14 | $1,833 | $117 | 41 % | $122 | 44 % | 14.6 | -$807 | 0 % | 0 % | +$1,499 |
| **gap-sized D+, 3c** | 1,228 | **+$49,999** | 40.72 | 12/14 | $2,735 | **$141** | **47 %** | **$147** | **50 %** | **16.7** | -$885 | 0.6 % | 0 % | +$1,914 |
| D+ v2, 4c | 632 | +$5,482 | 8.67 | 7/14 | $3,180 | $104 | 35 % | $108 | 38 % | 6.4 | -$533 | 0 % | 0 % | $0 |
| gap-sized D+, 4c | 632 | +$12,853 | 20.34 | 9/14 | $2,591 | $136 | 47 % | $144 | 49 % | 8.5 | -$900 | 0.6 % | 0 % | +$336 |

At 4 micros the engine's per-sleeve $2,000 hard-drawdown lock (a fixed dollar amount, not scaled with size) trips constantly and removes most of the trades - 4c
is not viable on this engine, so 3 micros is the practical maximum without a new engine version. The lock is also why the linear 3c DLL estimate (10.8 %)
is wrong: engine-exact, the 3c gap-sized configuration never hits the $1k daily loss and breaches the static floor in 0.6 % of starts.

## Decision
Deploy **`ag_arch_d_plus_v2_gapsize_3c`** (3 micros; 6 on Crabel drives that agree with the opening gap) to the Future-strategies section: median winning trade
$141 and median winning day $147 - just under the $150 mark (47 % of winners and 50 % of winning days clear it, 16.7 qualifying days a year vs 3 at 1c), the
highest net per trade of anything measured ($40.72), and 0.6 % breach / 0 % DLL under the static rules. Strictly clearing $150 on the median trade needs
4 micros, which requires scaling the engine's hard-drawdown lock with size - a new engine version, not done here. Not evidence for 2024-26 (sealed).
Scripts: scripts/payout_1_pilot.py, scripts/payout_1_step3.py; data: reports/PAYOUT_1_TRAINING.json, PAYOUT_1_STEP3.json, PAYOUT_1_ENGINE.json.

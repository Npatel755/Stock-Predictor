# staging_1 - funded-account staging policy under an explicit trailing floor (training 2010-23 only)

Protocol: research/staging_1/PROTOCOL.md (pre-registered). Script: scripts/staging_1_pilot.py -> reports/STAGING_1_TRAINING.json.
Nothing in any leg was changed; this round only asks in which order the frozen, already-paper-traded configurations should be run inside
a $50k account with a $2,000 trailing floor (provisional rule model: floor = intraday high-water mark - 2,000, locks at +100 once the
account has been +2,100; variant A marks open trades at their worst excursion, variant B trails on closed equity only). The live
account's exact rule semantics must be confirmed before this is acted on; both variants are reported.

## Why the floor model changes the answer
Before the lock, *any* marked drawdown of $2,000 from the running peak ends the account, whatever has been banked - so pre-lock, the only
thing that matters is a configuration's marked drawdown. After the lock the floor stops moving and every dollar above it is real cushion,
which is when larger configurations (Book A, the SKEW-sized book, a third leg) become safe. Book A's $2,043 marked DD (book_1) is
therefore a pre-lock problem only: on the single 14-year path from 2010 the lock arrives (month 5-6) long before the 17 Mar 2020 night.

## Historical paths - an account started on the 1st of every month 2010-01 .. 2023-01 (157 starts), run 12 months or to breach

| policy | pre-lock config | 12m survival A / B | median 12m net (A) | p10 12m net | locked by 12m | months to lock | 14-yr path from 2010 (restart on breach) |
|---|---|---|---|---|---|---|---|
| S_A static Book A | L1+L2 | 95.5 % / 100 % | +1,026 | -121 | 33 % | 5.2 | +28,317, 0 breaches |
| S_1 static overnight v2 | L1 | 100 % / 100 % | +430 | -44 | 15 % | 8.2 | +11,797, 0 |
| S_2 static All-Weather 1c | L2 | 100 % / 100 % | +425 | -308 | 23 % | 6.3 | +16,520, 0 |
| S_3 static D+ v2 | L3 | 100 % / 100 % | +526 | -86 | 28 % | 7.0 | +17,576, 0 |
| P_L1 staged | L1 | 100 % / 100 % | +430 | -44 | 15 % | 8.2 | +63,811, 0 |
| P_L2 staged | L2 | 100 % / 100 % | +425 | -308 | 23 % | 6.3 | +61,543, 0 |
| P_L3 staged | L3 | 100 % / 100 % | +526 | -86 | 28 % | 7.0 | +63,024, 0 |
| P_BookA staged | L1+L2 | 94.9 % / 99.4 % | +1,002 | -125 | 33 % | 5.2 | +66,599, 0 |

Staged ladder after the lock (declared): cushion 500-1,500 Book A; 1,500-3,000 Book A with SKEW sizing; >= 3,000 SKEW book + D+ v2.
Pre-declared choice among the P(x): highest survival, tie -> median 12-month net => **P_L3** (start with D+ v2 alone).

Reading: 7 of the 157 Book-A-from-zero starts (4.5 %) die inside 12 months on intraday marks (none on closed equity - the breaches are
intraday excursions, as book_1 found); every single-leg start survives. The price is the first year: a single leg banks about half of
Book A's first-year median and reaches the lock 1-3 months later. Over the full 14 years the ladder compounds to ~2.2x Book A's net with
zero breaches on any start, because the larger configurations only run on banked cushion.

## Block bootstrap - 2,000 one-year paths from 20-trading-day blocks (same policy engine), breach probability

| policy | variant A (intraday marks) | variant B (closed equity) |
|---|---|---|
| S_A static Book A | 5.7 % | 4.1 % |
| S_1 overnight v2 alone | 2.8 % | 1.1 % |
| S_2 All-Weather 1c alone | 3.0 % | 2.1 % |
| S_3 D+ v2 alone | 0.1 % | 0.0 % |
| P_L1 staged from overnight v2 | 3.0 % | 1.2 % |
| P_L2 staged from All-Weather 1c | 4.2 % | 2.2 % |
| P_L3 staged from D+ v2 | 0.9 % | 0.3 % |
| P_BookA staged from Book A | 7.6 % | 5.1 % |

Model-conditional estimates, not forecasts. The staged ladders carry slightly more breach risk than their pre-lock leg alone because the
bootstrap can lock early and then hit a post-lock loss run at larger size.

## Pre-registered gate for adopting a staged policy as the deployment plan (P_L3 vs S_A)
- 12m survival >= S_A + 5 pts: 100.0 vs 95.5 -> +4.5 pts, **fails by 0.5 pt**.
- bootstrap breach <= half of S_A's: 0.9 % vs 2.85 % -> passes.
- median 12m net >= 80 % of S_A's: +526 vs +821 -> **fails** (first-year net is roughly halved).
Verdict: NOT adopted by the rule. Recorded as the measured trade-off for Nick's decision - the ladder removes the 4.5 % first-year
death rate of Book-A-from-zero (and cuts bootstrap breach odds ~6x) at the cost of about half the first-year net and 1-2 months later
lock; from year two on it dominates on every measure. Starting with D+ v2 alone is the lowest-risk opening (0.1 % bootstrap breach, 100 %
of 157 starts), ahead of the overnight leg alone (2.8 %, 100 %).


## Caveats
- Model-conditional, not a forecast: provisional rule semantics (lock level, intraday vs EOD basis), 14 years of one regime set, legs
  derived on this same split; the SKEW stage and D+ v2 are themselves one-split results.
- Variant A is conservative (concurrent open trades all at their worst at once); variant B is lenient. The live account sits between.
- No paper change: the ledgers already run every stage's configuration side by side, so the forward record of each stage accrues regardless.

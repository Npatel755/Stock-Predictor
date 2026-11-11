# Payout strategy at today's prices: payout_4 (day-lock) and payout_5 (price-aware D+ v5) - Claude, 2026-11-10

Training 2010-23 trades only. No 2024-26 data used (the Crabel-continuation family was scored on 2024-26 by Antigravity on 2026-11-10;
forward paper is the only clean test left). Goal: 12 payouts a year (5 days >= $150 net each, profit to withdraw) on a Topstep 50K static account.

## payout_4: locking the day at +$150 does not help (scripts/payout_4_daylock_train.py)
| rule on D+ v4 | $150+ days/yr | net 2010-23 | payouts/yr ($1k cushion) | blow-ups/yr |
|---|---|---|---|---|
| v4 as is | 19.3 | +$59,258 | 3.36 | 0.00 |
| lock the day at $160 / $200 / $300 | 29.6 / 26.4 / 22.6 | -$3,972 / +$3,438 / +$13,475 | 1.79 / 2.71 / 2.64 | 0.36 / 0.29 / 0.29 |
| bank half at $160, rest to breakeven | 22.2 | +$20,104 | 2.57 | 0.07 |
Locks add qualifying days but cut the big winners that fund the losing days: fewer payouts, more blow-ups. Side result: keeping a $1,000
cushion when withdrawing takes v4's blow-ups from 0.14/yr to 0 for almost the same payouts (3.36 vs 3.43).

## The deployed sizing does not fit today's prices
Live feed 2026-10-30..11-10 (NQ ~27,980, ES ~7,584): median stop risk per micro Crabel $384, 60m trend $492, MES $147. The engine sizes
each trade as budget / risk per contract: the 1-micro D+ ledgers ($150 budget) can trade only MES today; the 3-micro ledgers ($450) take
Crabel at 1 micro and MES at 3, and the 60m trend sleeve is blocked. In % terms today's stops sit at the 95th (Crabel), 100th (60m trend)
and 84th (MES) percentile of training - a high-volatility stretch, not just a higher price.

## payout_5: training trades re-expressed at today's price level (scripts/payout_5_price_normalized_train.py)
Each 2010-23 trade's move is scaled to today's price (same % move), with today's costs. 157 monthly 12-month starts for the breach odds.
| configuration at today's prices | $150+ days/yr | payouts/yr | payouts per 12m (p10-p90) | 12-month floor breach | worst day | max DD |
|---|---|---|---|---|---|---|
| **v4 as deployed** ($450 budget, 3 micros, x4/3 continuation) | 33.3 | 5.7 | 0-8 | **38%** | -$1,292 | $5,182 |
| 1 micro per sleeve, no budget, $400 account stop | 27.2 | 4.9 | 2-7 | 0% | -$802 | $2,231 |
| **v5: 1 micro, $300 per-micro budget, $400 account stop** | 24.3 | **4.5** | **2-6** | **0%** | -$610 | $1,628 |
| 1 micro, $250 budget | 21.6 | 3.9 | 1-5 | 0% | -$610 | $1,896 |
| MES only (what the 1-micro ledgers trade today) | 3.9 | 0.7 | 0-1 | 0% | -$313 | $1,151 |
If today's elevated volatility persisted (every trade at today's stop size), 1 micro with no budget would breach in 46% of 12-month starts
- which is why v5 keeps a budget: it trades the MNQ sleeves only when one micro risks <= $300 and sits them out in stretches like now.

## v5 in the paper runner
`ag_arch_d_plus_v2_price_aware_v5` (Future): D+ v2 sleeves, 1 micro, $300 per-micro budget, no per-sleeve drawdown lock, research routing,
account-level -$400 daily stop, account static floor $2,000. Runner replay 2010-23 at historical prices: 1,454 trades, all 1 micro, +$18,810.50,
no locks. Live-path check (bars cut mid-trade) and 12/12 tests pass. Not yet deployed to the droplet.

## What this means for 12 payouts a year
Per account, the evidence supports ~4-5 payouts a year at today's prices with a survivable floor - and only if training's R-distribution
repeats. 12 a year means ~3 accounts running v5 (correlated: they win and lose together). The deployed v4 should be read as oversized for
today's dollar volatility.

## Deployed (2026-11-10 ~05:55 UTC, Nick's standing authorisation)
v5 added to the droplet's paper runner (engine 133d385d... = previous deploy 8a9a0a66 + v5 candidates only). Dry run on a /tmp copy: 26 ledgers,
0 divergences. Live run: success, 26 ledgers, 0 divergences, 0 errors; v5 ledger has the 2026-11-09 MES trade (+$37.75 at 1 micro).
Backups: `ensemble_paper.py.bak_v4deploy`, `/opt/futures-paper/runs_backup_20261110b`.

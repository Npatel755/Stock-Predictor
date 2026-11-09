# Deployment plan - funded-account staging (decided 2026-11-09, Nick; basis reports/STAGING_1_TRAINING.md)

Status: documented plan only. Paper ledgers are unchanged (every stage already runs as its own simulated ledger). No live routing exists
or is authorised. Nothing here uses 2024-26 data.

## Precondition (must be done before any real-money step)
Confirm the prop firm's exact rules and replace the provisional model: drawdown amount, intraday-mark vs end-of-day basis, trailing /
lock level and where the floor locks, daily-loss limit and reset time, contract cap, consistency rule. staging_1 assumed: $50k account,
floor = intraday high-water mark - $2,000, locks at +$100 once the account has been +$2,100. If the real rules differ, rerun
scripts/staging_1_pilot.py with the real constants (training data only) before using the ladder.

## The ladder (frozen configurations, all on paper now)
| stage | trigger (closed equity above the locked floor) | configuration | paper ledger |
|---|---|---|---|
| 0 - opening | account start until the floor locks, and cushion < $500 | D+ v2 alone, 1 contract, $150 stop-risk budget | ag_arch_d_plus_v2 |
| 1 | cushion >= $500 | Book A: overnight dip v2 + All-Weather v2 1c | book_a |
| 2 | cushion >= $1,500 | Book A with SKEW sizing (2c when prior CBOE close has SKEW below its 20d mean) | book_a_skew |
| 3 | cushion >= $3,000 | SKEW-sized Book A + D+ v2 (1c) | book_a_skew + ag_arch_d_plus_v2 |
Downgrades apply the same way (a stage is re-evaluated at every new trade; open trades keep their size to exit).

## Why this opening
Pre-lock, banked profit does not protect the account - only the configuration's marked drawdown does. D+ v2 alone: 100 % of 157 monthly
12-month starts survived (intraday marks), 0.1 % one-year bootstrap breach, marked DD $882. Book A from zero: 95.5 % / 5.7 %, marked DD
$2,043. Cost: first-year median net about half of Book A's (+$526 vs +$1,026) and the lock ~2 months later. 14-year path of the ladder:
~+$63k, 0 breaches, vs Book A static +$28k.

## Promotion / rollback triggers for the paper record (set now, before looking)
- Any ledger whose forward 90-day realised net is below its training 10th-percentile 90-day net (reports/*_TRAINING.json breach MC
  sections) is frozen out of the ladder until reviewed; no parameter is changed in response.
- A paper-vs-research divergence (runner `divergences` > 0) on any ladder ledger blocks promotion until reconciled.
- 2024-26 are never scored to make these decisions.

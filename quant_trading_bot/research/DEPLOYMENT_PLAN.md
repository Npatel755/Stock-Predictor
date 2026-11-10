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

## Account-rules update (2026-11-09, from Nick's Topstep / Tradeify notes; basis reports/FUNDED_1_TRAINING.md)
- Target account: Topstep $50k Daily Payouts+ **Static** ($2k fixed floor, $1k daily loss limit, $4k evaluation target with 55 % best-day consistency;
  cap 50 micros / 5 minis, scaling plan after funding). Verify the current policy text before purchase - these rules are Nick's notes, not checked by Devin.
- Evaluation (sim, only the fee at risk): run gap-sized D+ (`ag_arch_d_plus_v2_gapsize` rules) at **3 micros**: engine-exact training odds 36 % pass /
  0.6 % fail per 12-month start under static rules (40 % / 3 % under trailing), median ~5-7 weeks when it passes; plan for 1-3 attempts. Not 4c (fails rise faster).
- Funded phase: the ladder above, unchanged - but with a static floor banked profit protects immediately, so Stage 1 (Book A) starts when $500 is banked,
  no lock wait. Under static + $1k DLL every ladder stage except the 2c books is clean in all 157 training starts; the 2c overnight / SKEW books hit the DLL
  in 8-23 % of years, so Stage 2 (SKEW-sized book) is held back until the DLL semantics are confirmed, or the account has no DLL (Tradeify Select Flex).
- Payouts: 5 winning days >= $150 is slow at 1c (1-5 such days a year); the 40 % consistency path is satisfied by every configuration (best day 20-35 % of net).

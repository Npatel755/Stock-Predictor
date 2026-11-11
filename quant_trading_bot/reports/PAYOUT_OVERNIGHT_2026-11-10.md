# Overnight payout research, 2026-11-10 (Claude) - toward 12 payouts a year

All studies: training 2010-23 trades only, re-expressed at today's price level (NQ 27,981 / ES 7,584, live feed 2026-11-10), 1 micro,
$300 per-micro stop-risk budget, research post-hoc routing, $400 account stop, $1,000 withdrawal buffer, static -$2,000 floor, $1k DLL.
Payout = 5 days >= $150 since the last payout with profit above the buffer. Breach odds = 151 monthly 12-month starts. Each study's
rules and gate were written in its script docstring before it ran. No 2024-26 data was used.

## Results ladder (one account)
| step | book | payouts/yr | per 12 months p10-p90 | 12-month breach | status |
|---|---|---|---|---|---|
| deployed v4 (old sizing) | 3-4 micros, $450 budget | 5.7 | 0-8 | **38%** | oversized at today's prices |
| payout_5 | **v5**: D+ sleeves, 1 micro, $300 budget | 4.5 | 2-6 | 0% | on paper |
| payout_6 | v5 + MNQ 30m afternoon trend (TRD30PM) | 5.07 | 2-7 | 1.3% | passed |
| payout_9 | **v5.2**: + 2 micros on gap-continuation Crabel | 5.5 | 3-7 | 0.7% | **on paper** |
| payout_10 | v5.2 + overnight dip, 0.55% stop, always on | 7.14 | 5-9 | 2.6% | failed 2% gate |
| payout_11 | **v5.2 + overnight dip 0.55% stop, on once balance >= $500** | **6.43** | **4-9** | **0.7%** | **on paper (separate ledger)** |

Did not help: day-locks at +$160-300 (payout_4: payouts fall to 1.8-2.7/yr), more trend/breakout sleeves (TRD30_D, BRK30: breach 4-20%),
bigger buffers or staging the intraday book (payout_7: same or fewer payouts). Unstopped overnight at today's price: worst night -$2,701,
DLL hit in 42% of years.

## 12 payouts a year
One account: the evidence supports ~6-6.5 payouts/yr (v5.2 + staged stopped overnight). Two accounts running it: ~12-13/yr. Three: ~18.
Identical books on several accounts win and lose together (breach is all-or-nothing, 0.7%/yr in this replay). Diversified books did not help
yet: the non-D+ sleeve books fail the 2% breach test on their own (payout_8). Evaluation fees and pass time are per account (Antigravity's job).

## On the paper ledger now (droplet, 28 ledgers)
- `ag_arch_d_plus_v2_price_aware_v5` (v5) and `ag_arch_d_plus_v2_price_aware_v52` (v5.2): runner replay 2010-23 matches research
  (v5.2: +$28,039.50 vs +$28,246.50 research, one day of 14 years differs by $207).
- `overnight_dip_v2_stop055`: 0.55% stop; 163 stop exits in training, identical to the research rule (0 mismatches). The $500 staging is a
  trading rule for Nick, not modelled in the ledger (paper ledgers do not withdraw).

## Caveats (read before trading any of this)
1. Every number assumes training's R-distribution and % volatility pattern repeat at today's price. Today's live volatility sits at the 84th-100th
   percentile of training, so the MNQ sleeves are mostly sitting out right now (stop risk > $300); forward paper is the real test.
2. The overnight family failed its one-shot 2024-25 validation (Devin, overnight_2), and 2024-26 has since been viewed for the Crabel family
   (Antigravity's Fortress). No clean holdout is left for these legs.
3. Multiplicity: payout_4-11 are 8 studies and ~45 cells on the same training split. Gains were kept only where a pre-declared gate passed.

## Later the same night: account size, stress, evaluation (payout_12..15)
- **Account size (hypothetical floors, payout_12):** best book within 2% breach - $2,000 floor: v5.2 (5.25/12m; 6.2 with the staged overnight
  rule); $3,000: v5.2 + overnight 6.94; $4,500: all sleeves + overnight 7.5; 2 micros on a $4,500 floor: 8.45 at 2.6% breach. No single account
  reaches 12 with the evidenced edges - there are only ~40 qualifying days a year at 1 micro.
- **Stress (payout_13), recommended setup R = v5.2 + staged overnight:** base 6.21 payouts/12m, 0.7% breach; costs +2 ticks/side 6.04 / 0.7%;
  edge -25% 5.11 / 2.6%; both 4.94 / 3.3% (passes the pre-declared robustness bar); **volatility x1.5 all year 4.48 / 11.3%** - the main tail risk.
- **High-vol guard (payout_14):** no budget / account-stop setting keeps breach <= 2% normally and <= 5% at 1.5x volatility; tighter budgets leave
  fewer winners to build the cushion. Recorded as a monitored risk, not tuned further.
- **Evaluation (payout_15), 50K static, $4k target, at today's prices:** R passes 90.7% within 12 months (fail 0.7%, open 8.6%), median 102
  trading days to pass (p75 159), then ~35 trading days to the first payout; start to first payout median ~142 trading days (~6.8 months).

## Plan that reaches 12 payouts a year
Two 50K static accounts, each running v5.2 + the stopped overnight leg (night leg on once ~$500 is banked), $400 account stop, keep $1,000
when withdrawing: ~6.2 payouts per account per year in this replay (p10 4), ~12.4 combined; both evaluations ~5 months at 1 micro.
Biggest risk: a sustained high-volatility year (~10% breach in the x1.5 stress). Forward paper (v5.2 and overnight_dip_v2_stop055 ledgers)
is the only clean evidence left.

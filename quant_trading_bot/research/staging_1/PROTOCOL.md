# staging_1 - funded-account staging policy under an explicit trailing floor (pre-registered 2026-11-09, training 2010-23 only)

Question: given the legs already measured, what sequence of configurations maximises the odds of surviving a $50k funded account with a
$2,000 trailing floor, and what does that cost in net? This is a risk-policy round: no signal, parameter or exit is changed; every leg is
the frozen version already on paper. 2024-26 are never read.

Funded rule model (provisional - the live account's exact semantics must be confirmed before anything is acted on; both variants reported):
- start 0 (relative), floor = HWM - 2,000; HWM over intraday marks (variant A, conservative: each open trade marked at its worst excursion,
  concurrent opens summed) or over closed equity only (variant B, "EOD-trailing").
- floor locks at +100 once HWM >= 2,100 (common "trail to lock" rule); after the lock the floor never moves.
- breach = equity mark <= floor at any event; the account is then dead for the path.
- cushion = closed equity - floor (only meaningful after the lock; before it a >= $2,000 marked drawdown from peak breaches regardless of profit).

Legs (frozen, 1c unless noted): L1 overnight_dip_v2 (MNQ, 18:05 -> 09:45), L2 ag_all_weather_v2_1c, L3 ag_arch_d_plus_v2 ($150 budget),
SKEW state = prior CBOE close below its 20d mean (extstate_2/sizing_3).

Policies (all declared here, nothing scanned):
- S_A  static Book A (L1+L2) from day one (reference, book_1).
- S_1 / S_2 / S_3  static single leg L1 / L2 / L3 forever.
- P(x) staged, x in {L1, L2, L3, BookA} is the pre-lock configuration:
    before lock: x;  after lock, by cushion: < 500 -> x;  500-1,500 -> Book A;  1,500-3,000 -> Book A with SKEW sizing (2c in the SKEW state);
    >= 3,000 -> SKEW-sized Book A + L3. Stage is evaluated at each trade's entry; the trade keeps its size to exit. Downgrades apply the same way.
Pre-declared choice rule among the P(x): highest 12-month survival (variant A), tie -> higher median 12-month net. The chosen x is reported with
the whole table; no further variants are run on this split.

Scoring (training only):
1. Historical paths: an account started on the first trading day of every month 2010-01 .. 2023-01 (157 starts), run 12 months or to breach:
   survival %, median / 10th-pct closed net at 12 months, median months to lock. Also the single 14-year path from 2010-01 (breaches counted
   as restart-after-breach events, informational).
2. Block bootstrap: 2,000 one-year paths built from 20-trading-day blocks of trade-days (trade assigned to its entry day), same policy
   engine: breach probability per policy, variants A and B.
Pass criterion for a staged policy to be adopted as the documented deployment plan (paper ledgers unchanged): 12-month survival (variant A)
>= static Book A + 5 points AND bootstrap breach <= half of static Book A's, with median 12-month net >= 80% of static Book A's.
Deliverable: reports/STAGING_1_TRAINING.md/json. No paper change: the ledgers already cover each stage's configuration.

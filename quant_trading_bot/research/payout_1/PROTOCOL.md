# payout_1 - configurations whose typical winning trade / day clears $150 (pre-registered 2026-11-09, training 2010-23 only)

Nick's goal: "whenever it trades it will usually get a trade worth more than $150" - i.e. the median winning trade (and the median winning day) >= $150,
so the 5-winning-day (>= $150) payout rule fills quickly.
Step 1 (measurement, frozen legs from staging_2): for each configuration {overnight v2, All-Weather 1c, D+ v2, gap-sized D+, Book A, Book A SKEW} and
each size k = 1..6 micros (linear scaling; engine check for the chosen k afterwards): median winning trade, share of winning trades >= $150, median winning
day, share of winning days >= $150, $150+ days per year; and the cost: marked DD, worst day, 1-year breach (static $2k) and $1k-DLL hit rate over 157
monthly starts, median 12m net. k* = smallest k with median winning trade >= $150 AND median winning day >= $150.
Step 2 (selection rule, declared): among (config, k*) pairs, prefer the one with the lowest static-floor breach + DLL hit rate; ties by net per marked DD.
Report the Pareto frontier, not just the winner. If no pair keeps breach + DLL <= 5 %, say so - size cannot be conjured without drawdown.
Step 3 (only if step 2 leaves no acceptable pair): a wider-target variant of the D+ trend sleeve (target_r 5 / 7 instead of 3.5, exits otherwise frozen) -
reported as a separate candidate with placebo; parameter cells declared here, not scanned further.
Deliverable: reports/PAYOUT_1_TRAINING.md/json; a paper ledger only if a pair passes step 2 with breach + DLL <= 5 % (Future strategies, separate name).

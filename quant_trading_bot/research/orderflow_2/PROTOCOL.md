# orderflow_2: signed-volume (trade-aggressor) order flow on MNQ (registered 2026-11-08, before the trades file is opened)

Data (approved by Nick, $117.50, second Databento account): GLBX.MDP3 `trades`, MNQ.c.0 continuous front month, 2023-04-01 -> 2024-01-01.
Each record = one trade with price, size, aggressor side (A = seller hit bid, B = buyer lifted offer). This is the true signed volume
that orderflow_1's BBO-1s last-trade proxy could only approximate; orderflow_1 (L1 size imbalance) was REJECTED.

Integrity before any signal: row count/day, RTH session coverage vs the 2023 calendar, timestamps UTC -> ET, price/tick sanity,
side distribution (N share), roll dates vs the BBO-1s file, and a cross-check of per-minute signed volume against the BBO-1s last-trade side.

Features (past-only, computed at the end of each 1-minute / 5-minute bucket, used from the next bucket on):
- VPIN-style signed-volume imbalance over trailing {1, 5, 15} min: (buy_vol - sell_vol)/(buy_vol + sell_vol)
- cumulative delta divergence: price makes a new 15-min high while trailing 15-min delta is <= 0 (and symmetric)
- large-trade imbalance: same ratio over trades with size >= 90th percentile of the prior 20 sessions
- exhaustion: buy-volume z-score (prior 20 sessions same time of day) > 2 with no new high in the bucket
Predictive test (RTH, Apr-Dec 2023): forward mid change over 1, 5, 15 min by feature decile; monotonicity, top-vs-bottom decile spread
in ticks vs round-trip cost (spread 1.75 ticks + 2 ticks slippage + $1.22 = ~5.4 ticks), HAC t-stat; separately for continuation
(trade with the imbalance) and reversal (fade it) readings.
Executable rules (fixed grid, 1 contract, marketable fills at the BBO-1s quote + 1 tick slippage, $0.61/side, 10-s reaction delay):
- continuation: enter with imbalance >= q in {0.3, 0.5, 0.7} (1/5/15-min window), exit at {2, 5, 15} min or 4-tick stop -> 27
- reversal: enter against imbalance >= q, same exits -> 27
- delta divergence fade: exit {5, 15} min or 4-tick stop -> 2;  exhaustion fade: same -> 2
58 configs x 20 placebo runs (same entry count, random entry times within RTH, random side). Months Apr-Dec = 9 monthly P&Ls.
Decision rule (fixed): SUPPORTED only if a monotone decile relation exists with top-bottom spread > round-trip cost and |t| > 4 AND an
executable config nets > 0 in >= 7 of 9 months and beats 95% of placebos; PROXY-ONLY if predictive significance without an
executable config; REJECTED otherwise. Nothing is promoted to the paper ledger from this pilot; 2024+ order-flow data untouched.

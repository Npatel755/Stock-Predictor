# overnight_4 — stress / robustness of overnight_dip_v2 (pre-registered 2026-11-09, before any run; training 2010-2023 only, 2024-26 sealed)

Subject (frozen from overnight_3, on paper as `overnight_dip_v2`): long 1 MNQ 18:05 ET bar open -> next 09:45 open on nights where BOTH the MNQ and MES
18:00 reopen gaps are <= -0.5 x sd of their previous 20 gaps. No parameter is re-chosen in this round; everything below is diagnostic and reported as is.
1. Plateau: threshold k in {0.25, 0.375, 0.5, 0.625, 0.75, 1.0} x sd, window w in {10, 15, 20, 30, 40} nights (30 cells, k=0.5/w=20 is the rule). A robust
   rule has every neighbour (k 0.375-0.625, w 15-30) with net > 0, >= 10 positive years and DD < $2,000. Cells are reported, not selected.
2. Intrabar drawdown: equity marked at the overnight low (18:05 -> 09:45 low) each night; max intrabar DD on 2010-23 and by year.
3. Funded breach Monte Carlo: stationary block bootstrap (mean block 10 nights) of the 2010-23 nightly net, 5,000 paths of 1 year (~35 nights) and 2 years;
   P(closed DD >= $2,000), P(intrabar DD >= $2,000), 5/50/95th percentile of annual net; same with 2020-22 removed (regime-free view).
4. Tail: worst 10 nights, count of nights <= -$400 and <= -$500 (daily-loss style limits), share of net from the top 5 % of nights.
5. Calendar: nights lost to a missing 18:00 or 09:45 bar; Sunday vs weekday net; results for 2019 note the Jan-May MNQ data gap.
6. Execution sensitivity: net with 2 ticks slippage per side and with 3 ticks (vs 1 in the rule).
Decision rule (pre-declared): v2 stays on paper regardless; if any neighbour in the plateau is negative, or P(intrabar DD >= $2k within 1 year) > 25 %,
the report flags v2 as "fragile" and the paper comparison with v1 is the only remaining evidence. No tuning follows from this round.

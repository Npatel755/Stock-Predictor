# overnight_9 — intrabar protective stops for overnight_dip_v2 (pre-registered 2026-11-09, training 2010–23 only)

Motivation: the binding constraint on the book and on SKEW-state sizing is drawdown, and the overnight leg has none of the intraday sleeves' stop
protection (worst night −$666; marked DD drives book_1's $2,043). Untested so far: a protective stop on the 1-minute path (overnight_3 tested exit
times and an any-time gap-fill exit; overnight_4 measured intrabar DD but changed no rule).

Rule under test: overnight_dip_v2 exactly (MNQ, 18:05 -> 09:45, MNQ and MES reopen <= -0.5 sd), plus one exit change:
  S1 stop at entry − 1.0 × sd20 × ref_close   S2 stop at 1.5 × sd20   S3 stop at 2.0 × sd20   (sd20 = the night's own gap sd; triggered on a 1-min low <= stop; fill = stop − 1 tick slippage − half spread)
  F1 gap-fill exit only after 08:30 ET (first 1-min high >= ref close from 08:30 on; fill at ref close − costs), else 09:45.
Metrics on the same 490 nights: net, $/night, positive years, max-year share, closed DD, marked (session-low) DD, worst night, stop-hit rate.
Pass: net >= 90 % of v2 (>= +10,617) AND marked DD <= 90 % of v2's marked DD AND positive years >= 12 AND max-year share <= 40 %.
If a stop passes, second stage (declared now): recompute book_a (portfolio_4) and the SKEW-state 2c book (sizing_3) with the stopped leg; same gates as those rounds.
No threshold search beyond the three listed; 2024–26 not loaded. Deploy only at Devin's discretion as a new version beside v2.

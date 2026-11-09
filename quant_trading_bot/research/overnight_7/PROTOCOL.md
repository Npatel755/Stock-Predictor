# overnight_7 — walk-forward check of overnight_dip_v2 (pre-registered 2026-11-09; training 2010-2023 only; 2024-26 sealed)

Question: would the v2 rule (both MNQ and MES reopen gaps <= -k x sd of the previous w gaps, hold 18:05 -> 09:45) have been chosen by an investor
who only saw the past? Expanding-window walk-forward inside 2010-2023: for each year Y in 2014..2023, pick (k, w) from the grid k in {0.375, 0.5, 0.625, 0.75, 1.0},
w in {15, 20, 30} by maximising net / max(DD, 500) on 2010..Y-1, then score year Y with that choice. Report the chain of chosen parameters, the
out-of-sample-within-training net by year, and the same for the fixed v2 (k=0.5, w=20). Also the exit choice (09:30 / 09:35 / 09:45 / 10:00) walked forward the same way.
Reading rule: if the walk-forward chain net is within 20 % of the fixed rule and the chosen parameters are stable (k in 0.375-0.625 most years), v2 is a robust
choice rather than a lucky cell; otherwise flag it. Nothing is tuned or deployed from this round; 2024-26 never scored.

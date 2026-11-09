# archc_2 — stress-day exclusion for Architecture C and the combined book (pre-registered 2026-11-09; training 2010-2023; 2024-26 sealed)

From archc_1 (failure learning): restricting Architecture C to high-volatility days did WORSE than random same-count days, and portfolio_1 failed the $2k
floor only because the intraday sleeves and the overnight dip both lost in March 2020. Hypothesis: the intraday sleeves should stand aside on stress days.
Champion: ag_arch_c (trade-level router, engine default costs; training +16,070 / DD 1,596). Day state = prior trading day's CBOE close (point-in-time).
Variants (all reported):  V1 skip days with VIX >= 25   V2 skip days with VIX >= 30   V3 skip days with VIX/VIX3M > 1.0 (backwardation)   V4 skip days with VIX >= 25 OR backwardation
Gates for a variant to be deployed (Devin's discretion thereafter): net >= 0.9 x champion, closed DD <= 0.8 x champion DD, >= 11 positive years, largest year <= 40 %,
and the removed days must be genuinely bad: their net must be below the 5th percentile of 20 same-count random-day nets drawn from the champion's trade days.
Portfolio_2 (informational, pre-declared): each passing variant combined with overnight_dip_v2 as in portfolio_1 (daily sum, combined DD, block-bootstrap MC);
"qualifies as one $2k-floor account" if combined DD < $2,000 and P(DD >= $2k in 1 yr) <= 10 %. Multiplicity: 4 trials. 2024-26 never scored.

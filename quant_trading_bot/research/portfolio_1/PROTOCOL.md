# portfolio_1 — overnight_dip_v2 + ag_arch_c as one 1-contract account (pre-registered 2026-11-09; training 2010-2023 only; 2024-26 sealed)

Thesis: archc_1 showed the intraday sleeves earn on ordinary trend days and lose on stress days, while the overnight dip rule earns on stress nights;
the two never hold at the same time (overnight exits 09:45, Architecture C's earliest fill is 10:00), so one funded account can run both at 1 contract.
No parameter of either rule is changed. Inputs: nightly net of overnight_dip_v2 (scripts/overnight_3_pilot.py construction, COMBO rule) and the
trade list of ag_arch_c (scripts/replicate_antigravity_arch_c.py, default engine costs for both — like-for-like), 2010-2023.
Reported: per-year net of each and the sum; correlation of monthly P&L; combined closed DD and intrabar-approximate DD (overnight marked at the night low);
worst day; share of years both negative; block-bootstrap (mean block 10 trading days) breach MC on the combined daily P&L, 5,000 paths x 1 and 2 years,
P(DD >= $2,000), annual net p5/p50/p95; the same excluding 2020-22. Overlap check: count of days where an overnight position is still open when an
intraday trade would fill (must be 0 by construction; any violation is reported).
Decision rule: the combination is "worth running as one account" if combined DD < $2,000 and P(DD >= $2k in 1 yr) <= 10 % and monthly correlation <= 0.3.
Whatever the result, nothing is deployed from this round (both are already on paper separately); it informs sizing only. No validation scoring.

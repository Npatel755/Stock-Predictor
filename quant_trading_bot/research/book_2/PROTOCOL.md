# book_2 - Book A with the drawdown-first D+ v2 intraday leg (pre-registered 2026-11-09, training 2010-23 only)

Question: does replacing Book A's intraday leg (ag_all_weather_v2_1c) with ag_arch_d_plus_v2 (3 sleeves, 1c, marked DD 882 alone) give a book
that stays under the $2k marked floor with lower breach odds, at comparable net? Derived from dplus_1/2 on the same split - one-split evidence.

Candidate `book_ad`: overnight_dip_v2 (MNQ 1c, 18:05->09:45, MNQ+MES co-dip <= -0.5 sd) + ag_arch_d_plus_v2 under one 1-contract account.
The legs do not overlap in time (night exits 09:45, D+ sleeves start 10:00), so the book is the daily sum; marked DD uses book_1 conventions
(night marked at the lowest 1-minute low to 09:45, intraday marked at stop risk at entry).

Reference (recorded, book_1 / portfolio_4): Book A closed net +28,317, marked DD 2,043 (one $2k touch 17 Mar 2020), 1y breach 1.9% (closed-equity).

Gates (all must hold): marked DD < 2,000 and 0 touches of $2k; closed net >= 0.9 x 28,317 = 25,486; >= 11 of 14 years positive;
1-year block-bootstrap breach probability of a $2k closed-equity floor <= 2%; both halves (2010-16, 2017-23) positive.
Report-only (no gate): the same book with the intraday leg at 2 contracts (future-section candidate) - marked DD, touches, breach.
Outcome if pass: deploy `book_ad` beside book_a as a separate ledger (simulated only), never a replacement. If fail: record and stop.

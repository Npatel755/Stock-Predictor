# m2k_1 — transfer of the frozen rules to the Russell (M2K) and Dow (MYM) micros (pre-registered 2026-11-09, before any RTY/YM file is opened)

Why: the funded floor is a dollar constraint; MNQ's notional (~$56k) makes one contract's worst night/DD large. M2K (~$12k) and MYM (~$24k) carry the same
index mechanisms at a third / half the dollar risk per contract. Nick approved buying RTY + YM Databento GLBX.MDP3 ohlcv-1m continuous (RTY.c.0, YM.c.0),
Jun 2010 – Dec 2025, if the quote is under $40 (cap $125 total, $45.94 spent).

Data handling: files stored under data/market/crossasset/ (gitignored). Research reads only bars before 2024-01-01. 2024–25 rows stay unread (spent for
the overnight family anyway); there is no 2026 in the purchase. Pre-2019 RTY/YM full-size bars stand in for the micros (same as NQ/ES for MNQ/MES).
Economics: M2K tick 0.10 = $0.50, $5/pt; MYM tick 1.0 = $0.50, $0.50/pt. Spread assumption 2 ticks (thinner books than MNQ), slippage 1 tick/side,
commission $0.61/side. Round-trip cost per contract ≈ $3.22 + spread.

Tests (frozen rules; NO parameter changes — this is a transfer test, not a search):
 T1 overnight dip, own-instrument form: reopen 18:00 ≤ −0.5 × sd20 of prior gaps vs 16:00 close, long 18:05 → 09:45, 1 contract. On M2K and MYM.
 T2 overnight dip, co-dip form (v2): own dip AND MES dip (MES bars already owned). On M2K and MYM.
 T3 All-Weather v2 1c sleeves (30m breakout lb8 th as deployed, 60m trend lb as deployed, backwardation stand-aside, always 1c) on M2K and MYM.
 T4 books: overnight_dip_v2 (MNQ) + T2 passers summed; DD and 1-y breach MC as in portfolio_4.
Gates: overnight (T1/T2): net > 0, ≥ 100 nights, ≥ 11/14 positive years, max-year ≤ 40 %, closed DD < 2,000, 2010–19 net > 0, ≥ 190/200 same-count
random-night placebos. Sleeves (T3): net > 0, ≥ 9/14 years, max-year ≤ 40 %, DD < 2,000, 2010–19 > 0, removed/kept vs 20 random same-count day sets.
Books (T4): DD < 2,000 and 1-y breach ≤ 2 %. Deploy to paper at Devin's discretion as new ledgers; 2024–26 not scored.

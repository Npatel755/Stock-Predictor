# xasset_3 — bond-conditioned overnight leg inside Book A (pre-registered 2026-11-09; derived from xasset_2; training 2010–23 only)

Question (yes/no): does Book A (overnight_dip_v2 + ag_all_weather_v2_1c, 1c router) stay under the $2,000 marked floor with lower breach odds when the
overnight leg skips nights whose ZN (10-yr note) regular-day return (16:00 ET vs prior 16:00, Sunday nights use Friday) is negative?
Scoring: risk_1 machinery (book_1 intraday-trailing marks: overnight leg at every 1-min low, intraday stops assumed hit).
Rule B1: skip night if ZN day return < 0 (missing → trade). Control C1: skip if ZN day return > 0 (should hurt). Placebo: 200 random same-count night skips.
Pass: marked DD < 2,000 AND retained closed net ≥ 0.8 AND B1 marked DD below ≥ 190/200 placebo skips AND C1 fails (retained < B1 and DD not lower).
If pass: deploy as `book_a_bond` beside book_a (separate version; not a replacement); else record. 2024–26 not loaded.

## Addendum (2026-11-09, before deployment): feed-definition robustness
The live runner can only get a settlement-like daily ZN close (yfinance ZN=F daily), whose day-change sign agrees with the Databento 16:00 ET bar on 92 % of
2021–23 days but with the 15:00 ET bar on 97 %. B1 is therefore re-scored with the 15:00 ET close (ZN_DEF=15); deployment requires that variant to pass the same
gate. The deployed rule is the settlement-close definition; both results are reported. No other change.

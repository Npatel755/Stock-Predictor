# Antigravity "Architecture C" — fixed-engine replication (training 2010–2023 only)

Sender spec (scripts/audit_architecture_c_all_splits.py, reports/ARCHITECTURE_C_ALL_SPLITS.json): strict 1-contract router, priority
S1 Crabel open-drive (09:30 open in the bottom/top 20 % of the 09:30–10:00 range and 10:00 close in the opposite 20 %; signal from the 09:45 bar close,
fill at the 10:00 open; stop 2.0 ATR14, target 4R, hold 12 bars, flat 15:55) > S2 MNQ 30m EWMA trend (spans 8/16 over ATR14, |z| ≥ 0.75, decisions
09:45–12:00, stop 1.5 / target 3.5R / hold 8) > S3 MNQ 60m EWMA trend (spans 6/12, |z| ≥ 0.75, 10:00–12:00, stop 1.25 / target 4R / hold 8).
Micro costs $0.61/side, 1.75-tick spread, 1 tick slippage per side. Script here: scripts/replicate_antigravity_arch_c.py (router applied at trade
level: a trade is rejected if its decision bar falls while an accepted trade is open). 2024–26 were not loaded (the sender has already scored them).

| | net 2010–23 | trades | $/trade | +years | 2010–19 | largest year | closed DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| S1 Crabel (mine) | 6,468 | 638 | 10.1 | 8/14 | 847 | 45 % (2021) | 973 |
| S2 trend 30m (mine) | 7,372 | 999 | 7.4 | 10/14 | 2,029 | 46 % | 1,344 |
| S3 trend 60m (mine) | 5,973 | 899 | 6.6 | 10/14 | 2,675 | 29 % | 1,325 |
| **Architecture C routed (mine)** | **16,070** | 1,980 | 8.1 | 11/14 | 5,050 | 42 % (2021: 6,741) | 1,596 |
| Architecture C (sender, 2010–23) | 14,397 | 1,524 | 9.4 | – | 3,692 | 46 % | 1,146 (16.9-yr) |

By year (mine): 2010 −261 · 2011 −200 · 2012 +18 · 2013 −604 · 2014 +657 · 2015 +719 · 2016 +267 · 2017 +906 · 2018 +2,699 · 2019 +849 · 2020 +807 · 2021 +6,741 · 2022 +3,389 · 2023 +84.

## Reading
- The look-ahead of Champion 2 is gone (Crabel uses the 09:45 bar's close for a 10:00 fill) and the result reproduces within router differences. Real.
- Still not an edge to fund: ≈$4/trade before 2020 (under one MNQ tick), four flat/negative years 2010–13, 2021 = 42 % of the net (cap 40 %), 2023 ≈ 0,
  and the sender has scored 2024–26 (their two audits disagree there: 2026 5 trades / +$824 / DD 1,146 vs 92 trades / +$5,306 / DD 3,998 — the second breaches the floor).
- Same profile as the Quad already on paper (trend sleeves 2020–22-heavy) plus a Crabel sleeve that is 2021-heavy. Suitable for a paper ledger only if Nick wants it; no validation claim can be made.

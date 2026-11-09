# archc_1 — improving Architecture C (pre-registered 2026-11-09 before any run; training 2010-2023 only; 2024-26 sealed)

Champion (on paper as `ag_arch_c` v1.0.0, frozen): strict 1-contract router, S1 Crabel open-drive (tails 0.20, 09:45-bar signal, 10:00 fill, stop 2.0 ATR,
target 4R, hold 12 x 15m) > S2 MNQ 30m EWMA trend (lb16, |z| >= 0.75, decisions 09:45-12:00, stop 1.5, target 3.5R, hold 8) > S3 MNQ 60m EWMA trend
(lb12, 0.75, 10:00-12:00, stop 1.25, target 4R, hold 8). Fixed-engine training 2010-23: +16,070 / 1,980 trades / 11 of 14 years / closed DD 1,596 /
2010-19 +5,050 / largest year 42 % (reports/ANTIGRAVITY_ARCH_C_REPLICATION.md). Weak spots to probe: 2010-13 flat, 2021 share > 40 %, ~$4/trade pre-2020.
Costs: the stated micro costs ($0.61/side, 1.75-tick MNQ spread, 1 tick slippage per side) applied to the champion and every variant alike inside the run (the engine default used in the replication is $0.50 / 1 tick, so the champion is re-scored here); router trade-level as in scripts/replicate_antigravity_arch_c.py. Placebo for selection variants: 20 same-count random-day sets.
Variants (one change each; all reported):
 Ablation:  A1 drop S1   A2 drop S2   A3 drop S3   A4 priority S2 > S3 > S1 (trend first)
 Crabel:    B1 tails 0.15 / 0.85   B2 tails 0.25 / 0.75   B3 add range >= 1.0 ATR14 filter   B4 long-only Crabel   B5 Crabel stop 1.5 ATR / hold 20 (sender's first spec)
 Exits:     C1 all sleeves hold +50 %   C2 all sleeves target 3R   C3 all sleeves trailing stop 2 ATR (engine trailing_atr=2.0)
 State:     D1 trade only when prior-day VIX >= 15   D2 only when VIX/VIX3M >= 0.9 (not deep contango)   D3 only when prior 20-day realized vol of NQ >= its 1-yr median (point-in-time)
 Sizing:    E1 2 contracts when VIX >= 25 (report DD)
Gates (challenger beats champion on training, same costs): net > champion net, >= 11 of 14 years, largest year <= 40 %, closed DD <= 1,800, 2010-19 net > champion 2010-19, trades >= 500,
and for state filters (D) the placebo gate (>= 19 of 20 same-count random-day sets). Multiplicity: 18 trials; a single passer is suggestive, reported as such.
Stress for any passer: block-bootstrap breach MC as in overnight_4. Promotion: a passer goes to paper as `ag_arch_c_v2` beside v1; no live routing; 2024-26 never scored.

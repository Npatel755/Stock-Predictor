# Antigravity "Enhanced Architecture C" — fixed-engine replication (training 2010–2023 only)

Sender spec (scripts/audit_enhanced_c_all_splits.py): Architecture C with Crabel hold 8 / target 3.5R (was 12 / 4R), 30m trend target 3R (was 3.5R) with
decisions 10:00–12:00 (was 09:45–12:00), 60m trend hold 6 (was 8; irrelevant — the 15:55 flatten comes first). Router and costs as before.
Script: scripts/replicate_antigravity_enhanced_c.py (same engine/router as reports/ANTIGRAVITY_ARCH_C_REPLICATION.md). 2024–26 not loaded.

| | net 2010–23 | trades | $/trade | +yrs | 2010–19 | largest yr | closed DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| Architecture C (mine) | 16,070 | 1,980 | 8.1 | 11/14 | 5,050 | 42 % | 1,596 |
| **Enhanced C (mine)** | **16,535** | 1,983 | 8.3 | 11/14 | 5,279 | 38 % | 1,589 |
| Enhanced C (sender, 2010–23) | 16,048 | 1,543 | 10.4 | – | 3,862 | 38 % | 1,070 (16.9-yr) |

By year (mine): 2010 −280 · 2011 −171 · 2012 +22 · 2013 −575 · 2014 +593 · 2015 +854 · 2016 +300 · 2017 +647 · 2018 +2,584 · 2019 +1,306 · 2020 +1,249 · 2021 +6,269 · 2022 +3,562 · 2023 +177.

## Reading
- Reproduces (sender +16.0k vs mine +16.5k on 2010–23). The change is a +3 % exit tweak with identical drawdown and trade count — not a new strategy.
- Same economics as Architecture C: ≈$4.6/trade before 2020, four flat/negative years 2010–13, 2021 = 38 %. The sender's 2024–26 "sealed" results are
  not blind (those splits have been scored on every iteration) and the exit tweak was chosen with all splits visible.
- Not added to paper: `ag_arch_c` (and `ag_arch_c_lite`) already carry this mechanism forward; a near-duplicate ledger adds no information.

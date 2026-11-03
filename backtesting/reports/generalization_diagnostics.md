# Generalization diagnostics

The historical candidate pool and all of these dates have already participated in research. This is a retrospective selection-procedure diagnostic, not a new holdout. The frozen strategy is unchanged.

| Outer period | Chosen only from preceding inner blocks | Test net | Entries | Drawdown |
| --- | --- | ---: | ---: | ---: |
| 2023-01-01 00:00:00+00:00 to 2023-07-01 00:00:00+00:00 | v1.8 | $1,093.37 | 44 | 1.57% |
| 2023-07-01 00:00:00+00:00 to 2024-01-01 00:00:00+00:00 | v1.10 | $-248.37 | 36 | 3.16% |
| 2024-01-01 00:00:00+00:00 to 2024-07-01 00:00:00+00:00 | No trade | $0.00 | 0 | 0.00% |
| 2024-07-01 00:00:00+00:00 to 2025-01-01 00:00:00+00:00 | v1.11 | $1,967.62 | 41 | 1.77% |
| 2025-01-01 00:00:00+00:00 to 2025-07-01 00:00:00+00:00 | v1.11 | $2,510.56 | 41 | 1.80% |
| 2025-07-01 00:00:00+00:00 to 2026-01-01 00:00:00+00:00 | v1.8 | $3,216.79 | 44 | 1.33% |
| 2026-01-01 00:00:00+00:00 to 2026-07-01 00:00:00+00:00 | v1.10 | $741.39 | 49 | 3.51% |
| 2026-07-01 00:00:00+00:00 to 2026-10-28 00:00:00+00:00 | v1.11 | $648.74 | 26 | 1.64% |

Outer periods reset the account; their sums are not a continuous return. A seven-day chronological gap separates selection from evaluation. Inner scores exclude open and overlapping trade outcomes. No outer-period result changes the choice for that period.

Retrospective one-sided centered seven-day-block bootstrap p: 0.000199998. Bonferroni adjustment using 848 logged slots: 0.169598; adjusted upper Monte Carlo bound: 0.236405.

848 logged slots are a trial-count proxy, not a complete independent trial history. Bootstrap stationarity and block assumptions apply. This retrospective diagnostic cannot certify future edge.

Immediate parameter neighbors within 10% of selected net: 0.75. Worst neighbor/selected ratio: 0.7703485133613878.

These diagnostics cannot undo earlier inspection or prove a future edge. The locked future window remains pending, and historical profit alone cannot promote a new version.

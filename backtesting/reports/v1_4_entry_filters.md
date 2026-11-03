# Entry-filter research after ETH v1.4

All years were inspected/reused. 2026 participates in selection. Filters do not create an untouched holdout or future performance evidence. No risk, capital, fee or fill assumption changes; no saved profile overwrites.

Screened 48 fixed filter configurations. Selected diagnostic: **min_rvol_1.5**. Historical improvement gate passed: **False**.

| Full 2023-01-01 to 2026-10-28 exclusive | Net P&L | Entries | Intrabar drawdown |
| --- | ---: | ---: | ---: |
| Saved v1.4 | $6,034.44 | 465 | 4.92% |
| Filtered candidate | $7,793.34 | 439 | 4.78% |
| Saved v1.4 at 4bp | $4,721.92 | 465 | 5.16% |
| Filtered at 4bp | $6,497.82 | 439 | 4.98% |

Selected filter settings: `{"direction": "both", "max_atr_bps": 0.0, "min_atr_bps": 0.0, "min_rvol": 1.5, "min_signed_slope_bps": null, "min_trend_gap_bps": 0.0, "weekends": true}`.

| Reused-data check, independently reset accounts | Net P&L |
| --- | ---: |
| 2025_h1 | $1,187.97 |
| 2025_h2 | $2,062.92 |
| 2026_selection | $-218.57 |
| earlier_2020_2022 | $3,767.41 |

Entry filters use only completed-hour ATR, signed close-to-EMA distance, signed six-hour EMA slope, prior-20-hour relative volume and UTC day/direction. Neutral-filter replay was regression-tested against the original simulator. Entries can differ after a rejected setup because flat-position availability changes; this is a full broker replay, not deletion of losing ledger rows.

The saved v1.4 profile is unchanged. A generic exporter explicitly rejects filtered candidates so that no filtered backtest can silently become an unfiltered Pine strategy. A passed historical gate would still require a filter-aware export, reconciliation and future observations before any deployment claim. Earlier/half-year checks reset accounts; fold sums are not continuous account performance. No live orders occur.

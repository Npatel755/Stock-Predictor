# Volume/trend neighborhood above the $10,089.87 baseline

All 2023-2026 data including weak 2026 H1 is reused selection history. 2018-2019 spot data has already been inspected but does not select this grid. No independent forward-validation claim. Geometry, risk, account size, fees, financing and fills remain fixed; no saved-version changes.

Requested floor: **$10,089.87**. Exact saved v1.6 reference: **$10,089.87**. Merely beating the rounded floor does not count as improvement.

Screened 18 fixed filters. Selected diagnostic: **rvol2.4_trendgap200.0**. Full historical improvement gate: **True**.

| Same original 2023-01-01 to 2026-10-28 exclusive period | Net P&L | Entries | Intrabar drawdown |
| --- | ---: | ---: | ---: |
| Saved v1.6 | $10,089.87 | 367 | 3.76% |
| Changed trend candidate | $10,799.67 | 345 | 3.57% |
| Saved v1.6 at 4bp | $8,963.46 | 367 | 3.84% |
| Candidate at 4bp | $9,705.57 | 345 | 3.64% |
| Saved v1.6 at 8bp | $6,888.40 | 367 | 3.99% |
| Candidate at 8bp | $7,690.09 | 345 | 3.78% |

Filters: `{"direction": "both", "max_atr_bps": 0.0, "min_atr_bps": 0.0, "min_rvol": 2.4, "min_signed_slope_bps": null, "min_trend_gap_bps": 200.0, "weekends": true}`.

| Reused-data check, independently reset account | Net P&L | Entries |
| --- | ---: | ---: |
| 2025_h1 | $2,264.92 | 49 |
| 2025_h2 | $2,734.04 | 42 |
| 2026_h1 | $314.98 | 52 |
| 2026_h2 | $609.60 | 25 |
| 2026_h1_4bp | $182.77 | 52 |
| earlier_2020_2022 | $5,882.04 | 267 |

Trend distance is direction-signed hourly close versus EMA150. Volume thresholds vary against the prior-20-hour average, excluding the signal hour. Signals use the completed hour, not future candles. These are full broker replays rather than deletion of losing trades. Account risk and all costs remain unchanged.

Saved v1.6 and its downloads remain unchanged. Fold sums are not continuous account returns. A failed gate is retained even if headline P&L exceeds the current baseline. A qualifying improvement would be saved as v1.7, preserving v1.6.

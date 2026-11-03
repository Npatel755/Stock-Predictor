# Trend-quality follow-up above the $9,900 baseline

All 2023-2026 data including weak 2026 H1 is reused selection history. 2018-2019 spot data has already been inspected but does not select this grid. No independent forward-validation claim. Geometry, RVOL2, risk, account size, fees, financing and fills remain fixed; no saved-version changes.

Requested floor: **$9,900.00**. Exact saved v1.5 reference: **$9,971.43**. Merely beating the rounded floor does not count as improvement.

Screened 24 fixed filters. Selected diagnostic: **trendgap200.0_slopeNone**. Full historical improvement gate: **True**.

| Same original 2023-01-01 to 2026-10-28 exclusive period | Net P&L | Entries | Intrabar drawdown |
| --- | ---: | ---: | ---: |
| Saved v1.5 | $9,971.43 | 397 | 4.02% |
| Changed trend candidate | $10,089.87 | 367 | 3.76% |
| Saved v1.5 at 4bp | $8,735.76 | 397 | 4.11% |
| Candidate at 4bp | $8,963.46 | 367 | 3.84% |
| Saved v1.5 at 8bp | $6,468.48 | 397 | 4.28% |
| Candidate at 8bp | $6,888.40 | 367 | 3.99% |

Filters: `{"direction": "both", "max_atr_bps": 0.0, "min_atr_bps": 0.0, "min_rvol": 2.0, "min_signed_slope_bps": null, "min_trend_gap_bps": 200.0, "weekends": true}`.

| Reused-data check, independently reset account | Net P&L | Entries |
| --- | ---: | ---: |
| 2025_h1 | $2,183.01 | 50 |
| 2025_h2 | $2,260.03 | 48 |
| 2026_h1 | $114.33 | 54 |
| 2026_h2 | $597.53 | 26 |
| earlier_2020_2022 | $3,286.63 | 312 |

Trend distance is direction-signed hourly close versus EMA150; slope is direction-signed change of that EMA over six completed hours. Volume remains at least twice the prior-20-hour average. Signals use the completed hour, not future candles. These are full broker replays rather than deletion of losing trades. Account risk and all costs remain unchanged.

Saved v1.5 and its downloads remain unchanged. Fold sums are not continuous account returns. A failed gate is retained even if headline P&L exceeds $9,900. The existing volume-only exporter rejects active trend filters rather than silently dropping them; a faithful export would be needed before any changed candidate can be offered as a TradingView strategy.

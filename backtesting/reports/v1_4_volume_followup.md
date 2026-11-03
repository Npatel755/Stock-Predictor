# Volume-filter and geometry follow-up

All years including 2026 are reused selection data. No independent future validation, no live orders, no saved profile overwrite. Extra filters never modify sizing, costs or broker fills.

Screened 18 fixed configurations. Frozen selection: **geometry0_rvol2.0_weekendsTrue**. Historical improvement gate: **True**.

| Same 2023-01-01 to 2026-10-28 exclusive period | Net P&L | Entries | Intrabar drawdown |
| --- | ---: | ---: | ---: |
| Saved v1.4 | $6,034.44 | 465 | 4.92% |
| Candidate | $9,971.43 | 397 | 4.02% |
| Saved v1.4 at 4bp | $4,721.92 | 465 | 5.16% |
| Candidate at 4bp | $8,735.76 | 397 | 4.11% |

Rule: `{"family": "channel_breakout", "lookback": 96, "max_holding_bars": 0, "reward_r": 4.5, "slow": 150, "stop_atr": 1.5, "trail_atr": 3.0}`.

Filters: `{"direction": "both", "max_atr_bps": 0.0, "min_atr_bps": 0.0, "min_rvol": 2.0, "min_signed_slope_bps": null, "min_trend_gap_bps": 0.0, "weekends": true}`.

| Reused-data check, independently reset accounts | Net P&L |
| --- | ---: |
| 2025_h1 | $1,981.65 |
| 2025_h2 | $2,278.30 |
| 2026_selection | $582.55 |
| earlier_2020_2022 | $3,760.53 |

No profile/export was changed. These are reused historical selection checks, including 2026; fold sums are not a continuous account return. Filters operate on completed hourly signals and use prior-20-hour mean volume. The same broker simulation recalculates position availability, fees, slippage, financing and daily gates. Pine/export reconciliation and future observations remain absent. The generic exporter refuses to omit filters; a faithful export is required before a filtered candidate can be offered for TradingView.

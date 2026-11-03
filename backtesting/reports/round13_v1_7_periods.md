# Channel/EMA period research after ETH v1.7

All 2023-2026 observations are reused selection history. The 2018-2019 spot proxy was previously inspected and is not used in this search. No fresh forward-validation claim. RVOL2.4 and signed 200bp trend thresholds, exit geometry, account size, risk, costs and execution code remain fixed. Each period pair recomputes its own channel, EMA, warm-up and signed trend distance.

Frozen 12-configuration grid, including the unchanged control. 5 passed the main screen; 5 passed the complete gate. Selection: **channel72_ema250**. Gate: **True**.

| Same original perpetual period | Net P&L | Entries | Intrabar drawdown |
| --- | ---: | ---: | ---: |
| Saved v1.7 | $10,799.67 | 345 | 3.57% |
| Selected diagnostic | $11,541.24 | 357 | 3.37% |
| Saved v1.7 at 4bp | $9,705.57 | 345 | 3.64% |
| Saved v1.7 at 8bp | $7,690.09 | 345 | 3.78% |
| 2025_h1 | $2,480.80 | 50 | 1.79% |
| 2025_h2 | $3,216.79 | 44 | 1.33% |
| 2026_h1 | $554.45 | 53 | 3.90% |
| 2026_h2 | $763.15 | 30 | 1.51% |
| 2026_h1_4bp | $405.63 | 53 | 3.94% |
| earlier_2020_2022 | $6,941.96 | 267 | 2.06% |
| full_4bp | $10,381.91 | 357 | 3.44% |
| full_8bp | $8,248.25 | 357 | 3.76% |

Selected rule: `{"family": "channel_breakout", "lookback": 72, "max_holding_bars": 0, "reward_r": 4.5, "slow": 250, "stop_atr": 1.5, "trail_atr": 3.0}`.

Fixed filters: `{"direction": "both", "max_atr_bps": 0.0, "min_atr_bps": 0.0, "min_rvol": 2.4, "min_signed_slope_bps": null, "min_trend_gap_bps": 200.0, "weekends": true}`.

Stops and targets are fixed from the signal close; entries use the next open. Trailing changes occur only after completed closes and affect later ticks. Replaying every candidate permits changed exit timing to alter later entry availability and financing. Reset-fold sums are not continuous account returns.

The highest-net complete-gate pass can be verified and saved separately under the next version. A failed candidate never replaces a numbered strategy. Pine compilation and TradingView matching remain unverified.

# ETH v1.8 frozen volume and trend filter follow-up

All 2023-2026 observations are reused selection history. The 2018-2019 spot proxy was previously inspected and is not used in this search. No fresh forward-validation claim. Only declared rule/filter dimensions vary. Account size, risk, fees, slippage, financing, OHLC policy and execution code remain fixed.

Frozen 24-configuration grid, including the unchanged control. 1 passed the main screen; 1 passed the complete gate. Selection: **min_rvol=2.8_min_trend_gap_bps=200.0**. Gate: **True**.

| Same original perpetual period | Net P&L | Entries | Intrabar drawdown |
| --- | ---: | ---: | ---: |
| Saved v1.8 | $11,541.24 | 357 | 3.37% |
| Selected diagnostic | $11,749.94 | 322 | 3.15% |
| Saved v1.8 at 4bp | $10,381.91 | 357 | 3.44% |
| Saved v1.8 at 8bp | $8,248.25 | 357 | 3.76% |
| 2025_h1 | $2,330.74 | 43 | 1.81% |
| 2025_h2 | $2,935.45 | 40 | 1.31% |
| 2026_h1 | $847.12 | 50 | 3.52% |
| 2026_h2 | $719.07 | 27 | 1.51% |
| 2026_h1_4bp | $698.39 | 50 | 3.57% |
| earlier_2020_2022 | $7,337.90 | 218 | 2.01% |
| full_4bp | $10,661.99 | 322 | 3.22% |
| full_8bp | $8,661.51 | 322 | 3.35% |

Selected rule: `{"family": "channel_breakout", "lookback": 72, "max_holding_bars": 0, "reward_r": 4.5, "slow": 250, "stop_atr": 1.5, "trail_atr": 3.0}`.

Selected filters: `{"direction": "both", "max_atr_bps": 0.0, "min_atr_bps": 0.0, "min_rvol": 2.8, "min_signed_slope_bps": null, "min_trend_gap_bps": 200.0, "weekends": true}`.

Stops and targets are fixed from the signal close; entries use the next open. Trailing changes occur only after completed closes and affect later ticks. Replaying every candidate permits changed exit timing to alter later entry availability and financing. Reset-fold sums are not continuous account returns.

The highest-net complete-gate pass can be verified and saved separately under the next version. A failed candidate never replaces a numbered strategy. Pine compilation and TradingView matching remain unverified.

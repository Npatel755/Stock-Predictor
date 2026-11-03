# ETH v1.10 frozen target and trailing-stop follow-up

All 2023-2026 observations are reused selection history. The 2018-2019 spot proxy was previously inspected and is not used in this search. No fresh forward-validation claim. Only declared rule/filter dimensions vary. Account size, risk, fees, slippage, financing, OHLC policy and execution code remain fixed.

Frozen 16-configuration grid, including the unchanged control. 1 passed the main screen; 1 passed the complete gate. Selection: **reward_r=5.5_trail_atr=3.0**. Gate: **True**.

| Same original perpetual period | Net P&L | Entries | Intrabar drawdown |
| --- | ---: | ---: | ---: |
| Saved v1.10 | $12,690.41 | 316 | 3.07% |
| Selected diagnostic | $12,814.03 | 310 | 3.05% |
| Saved v1.10 at 4bp | $11,573.92 | 316 | 3.11% |
| Saved v1.10 at 8bp | $9,522.61 | 316 | 3.24% |
| 2025_h1 | $2,510.56 | 41 | 1.80% |
| 2025_h2 | $3,612.57 | 39 | 1.29% |
| 2026_h1 | $783.13 | 48 | 3.50% |
| 2026_h2 | $648.74 | 26 | 1.64% |
| 2026_h1_4bp | $639.94 | 48 | 3.55% |
| earlier_2020_2022 | $7,967.53 | 209 | 2.20% |
| full_4bp | $11,685.39 | 310 | 3.10% |
| full_8bp | $9,613.48 | 310 | 3.18% |

Selected rule: `{"family": "channel_breakout", "lookback": 72, "max_holding_bars": 0, "reward_r": 5.5, "slow": 250, "stop_atr": 1.5, "trail_atr": 3.0}`.

Selected filters: `{"direction": "both", "max_atr_bps": 0.0, "min_atr_bps": 0.0, "min_rvol": 2.8, "min_signed_slope_bps": null, "min_trend_gap_bps": 200.0, "weekends": true}`.

Stops and targets are fixed from the signal close; entries use the next open. Trailing changes occur only after completed closes and affect later ticks. Replaying every candidate permits changed exit timing to alter later entry availability and financing. Reset-fold sums are not continuous account returns.

The highest-net complete-gate pass can be verified and saved separately under the next version. A failed candidate never replaces a numbered strategy. Pine compilation and TradingView matching remain unverified.

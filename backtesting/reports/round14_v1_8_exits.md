# ETH v1.8 frozen exit-geometry follow-up

All 2023-2026 observations are reused selection history. The 2018-2019 spot proxy was previously inspected and is not used in this search. No fresh forward-validation claim. Only declared rule/filter dimensions vary. Account size, risk, fees, slippage, financing, OHLC policy and execution code remain fixed.

Frozen 36-configuration grid, including the unchanged control. 1 passed the main screen; 1 passed the complete gate. Selection: **stop_atr=1.5_reward_r=5.0_trail_atr=3.0**. Gate: **True**.

| Same original perpetual period | Net P&L | Entries | Intrabar drawdown |
| --- | ---: | ---: | ---: |
| Saved v1.8 | $11,541.24 | 357 | 3.37% |
| Selected diagnostic | $12,113.22 | 350 | 3.25% |
| Saved v1.8 at 4bp | $10,381.91 | 357 | 3.44% |
| Saved v1.8 at 8bp | $8,248.25 | 357 | 3.76% |
| 2025_h1 | $2,599.62 | 48 | 1.78% |
| 2025_h2 | $3,543.29 | 43 | 1.32% |
| 2026_h1 | $448.72 | 52 | 3.88% |
| 2026_h2 | $562.72 | 29 | 1.64% |
| 2026_h1_4bp | $304.34 | 52 | 3.93% |
| earlier_2020_2022 | $7,109.73 | 265 | 2.35% |
| full_4bp | $10,933.97 | 350 | 3.33% |
| full_8bp | $8,765.64 | 350 | 3.46% |

Selected rule: `{"family": "channel_breakout", "lookback": 72, "max_holding_bars": 0, "reward_r": 5.0, "slow": 250, "stop_atr": 1.5, "trail_atr": 3.0}`.

Selected filters: `{"direction": "both", "max_atr_bps": 0.0, "min_atr_bps": 0.0, "min_rvol": 2.4, "min_signed_slope_bps": null, "min_trend_gap_bps": 200.0, "weekends": true}`.

Stops and targets are fixed from the signal close; entries use the next open. Trailing changes occur only after completed closes and affect later ticks. Replaying every candidate permits changed exit timing to alter later entry availability and financing. Reset-fold sums are not continuous account returns.

The highest-net complete-gate pass can be verified and saved separately under the next version. A failed candidate never replaces a numbered strategy. Pine compilation and TradingView matching remain unverified.

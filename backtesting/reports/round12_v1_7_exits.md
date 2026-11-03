# Exit-geometry research after ETH v1.7

All 2023-2026 observations are reused selection history. The 2018-2019 spot proxy was previously inspected and is not used in this search. No fresh forward-validation claim. Entry filters, account size, risk, fees, slippage, financing, OHLC policy and execution code remain fixed.

Frozen 36-configuration grid, including the unchanged control. 0 passed the main screen; 0 passed the complete gate. Selection: **stop1.5_reward5.0_trail3.0**. Gate: **False**.

| Same original perpetual period | Net P&L | Entries | Intrabar drawdown |
| --- | ---: | ---: | ---: |
| Saved v1.7 | $10,799.67 | 345 | 3.57% |
| Selected diagnostic | $10,938.07 | 341 | 3.85% |
| Saved v1.7 at 4bp | $9,705.57 | 345 | 3.64% |
| Saved v1.7 at 8bp | $7,690.09 | 345 | 3.78% |

Selected rule: `{"family": "channel_breakout", "lookback": 96, "max_holding_bars": 0, "reward_r": 5.0, "slow": 150, "stop_atr": 1.5, "trail_atr": 3.0}`.

Fixed filters: `{"direction": "both", "max_atr_bps": 0.0, "min_atr_bps": 0.0, "min_rvol": 2.4, "min_signed_slope_bps": null, "min_trend_gap_bps": 200.0, "weekends": true}`.

Stops and targets are fixed from the signal close; entries use the next open. Trailing changes occur only after completed closes and affect later ticks. Replaying every candidate permits changed exit timing to alter later entry availability and financing. Reset-fold sums are not continuous account returns.

The highest-net complete-gate pass can be verified and saved separately under the next version. A failed candidate never replaces a numbered strategy. Pine compilation and TradingView matching remain unverified.

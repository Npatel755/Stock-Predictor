# ETH v1.9 frozen volume and trend filter follow-up

All 2023-2026 observations are reused selection history. The 2018-2019 spot proxy was previously inspected and is not used in this search. No fresh forward-validation claim. Only declared rule/filter dimensions vary. Account size, risk, fees, slippage, financing, OHLC policy and execution code remain fixed.

Frozen 24-configuration grid, including the unchanged control. 2 passed the main screen; 2 passed the complete gate. Selection: **min_rvol=2.8_min_trend_gap_bps=200.0**. Gate: **True**.

| Same original perpetual period | Net P&L | Entries | Intrabar drawdown |
| --- | ---: | ---: | ---: |
| Saved v1.9 | $12,113.22 | 350 | 3.25% |
| Selected diagnostic | $12,690.41 | 316 | 3.07% |
| Saved v1.9 at 4bp | $10,933.97 | 350 | 3.33% |
| Saved v1.9 at 8bp | $8,765.64 | 350 | 3.46% |
| 2025_h1 | $2,355.45 | 41 | 1.81% |
| 2025_h2 | $3,445.63 | 39 | 1.30% |
| 2026_h1 | $741.39 | 49 | 3.51% |
| 2026_h2 | $474.21 | 26 | 1.64% |
| 2026_h1_4bp | $597.10 | 49 | 3.56% |
| earlier_2020_2022 | $7,691.12 | 214 | 2.28% |
| full_4bp | $11,573.92 | 316 | 3.11% |
| full_8bp | $9,522.61 | 316 | 3.24% |

Selected rule: `{"family": "channel_breakout", "lookback": 72, "max_holding_bars": 0, "reward_r": 5.0, "slow": 250, "stop_atr": 1.5, "trail_atr": 3.0}`.

Selected filters: `{"direction": "both", "max_atr_bps": 0.0, "min_atr_bps": 0.0, "min_rvol": 2.8, "min_signed_slope_bps": null, "min_trend_gap_bps": 200.0, "weekends": true}`.

Stops and targets are fixed from the signal close; entries use the next open. Trailing changes occur only after completed closes and affect later ticks. Replaying every candidate permits changed exit timing to alter later entry availability and financing. Reset-fold sums are not continuous account returns.

The highest-net complete-gate pass can be verified and saved separately under the next version. A failed candidate never replaces a numbered strategy. Pine compilation and TradingView matching remain unverified.

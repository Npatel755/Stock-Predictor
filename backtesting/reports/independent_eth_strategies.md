# Independent ETH strategy-family experiment

All historical years are reused/inspected; this is additional model selection, not untouched forward validation. Independent signal families still share market exposure and broker assumptions.

Screened 12 fixed configurations across EMA crossover, channel breakout and Bollinger reversion. Selected **channel_breakout_7** using training shortlist and reused 2025 selection, before the 2026 audit.

Historical promotion gate passed: **False**.

| Period | DVS v1.2 | Independent candidate |
| --- | ---: | ---: |
| 2020, independent accounts | $431.18 | $3,449.76 |
| 2021, independent accounts | $-2,012.47 | $1,667.69 |
| 2022, independent accounts | $-1,512.58 | $695.60 |
| 2023, independent accounts | $1,338.39 | $-73.11 |
| 2024, independent accounts | $656.27 | $3,169.70 |
| 2025 H1, independent accounts | $25.50 | $83.83 |
| 2025 H2, independent accounts | $1,639.91 | $1,427.18 |
| audit_2026 | Not recomputed in this run | $-383.91 |
| continuous_2020_2026 | Not recomputed in this run | $10,036.72 |
| recent_october | Not recomputed in this run | $-284.82 |

2025 continuous 4bp-extra-slippage stress: $1,206.22.

Frozen selected rule: `{"family": "channel_breakout", "lookback": 55, "max_holding_bars": 0, "reward_r": 3.0, "slow": 200, "stop_atr": 2.0, "trail_atr": 3.0}`.

Every rule uses confirmed hourly signals and five-minute OHLC execution, next-open entries, $100 planned risk including estimated costs, $50,000 capital, max 5x leverage, 4bp/side commission, two ticks plus 2bp extra market/stop slippage, financing and stop-first ambiguity handling. Shared personal daily gates are not contractual funded-account compliance checks. Annual folds reset accounts; their sum is not a continuous account return. Cash is a zero-return alternative.

Stops/targets are based on the hourly signal close and ATR, not a future fill. Trailing updates occur only after the current five-minute candle closes. There are no DVS pivot/bias/retest requirements. No independent strategy is promoted solely for winning this reused-data search. Signals, fills and Pine compilation still require external reconciliation. No live orders or v1.2 edits occur.

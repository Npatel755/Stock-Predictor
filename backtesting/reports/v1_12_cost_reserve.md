# ETH v1.12 cost-reserve research candidate

One predefined change: fixed 8bp slippage in sizing, versus a fixed 2bp baseline budget. Actual market/stop fills are independently stressed at 2, 4 and 8bp. Both retain two ticks, fees and financing. Signal, stop, target and trail parameters are unchanged.

**Not promoted. Future profitability remains unproven.** 2023-2026 observations are consumed development data; no new venue or BTC test was retuned. A separate candidate-specific 180-day prospective protocol was registered before replay. The v1.11 lock is unchanged.

The older stress tests raised both fill costs and the sizing estimate together. Their results remain valid for known higher costs. These new tests ask a different question: what if execution is worse than the budget used when sizing? They must not be compared as identical scenarios.

| Period | Fixed sizing budget | Actual fill slippage | Net P&L | Entries | Intrabar drawdown | Max estimated initial-stop risk at 8bp |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| full | 2.0bp | 2.0bp | $12,814.03 | 310 | 3.05% | $116.76 |
| full | 2.0bp | 4.0bp | $12,050.81 | 310 | 3.20% | $116.76 |
| full | 2.0bp | 8.0bp | $10,524.39 | 310 | 3.48% | $116.76 |
| full | 8.0bp | 2.0bp | $11,720.87 | 310 | 2.79% | $100.00 |
| full | 8.0bp | 4.0bp | $11,018.41 | 310 | 2.92% | $100.00 |
| full | 8.0bp | 8.0bp | $9,613.48 | 310 | 3.18% | $100.00 |
| 2023 | 2.0bp | 2.0bp | $1,543.86 | 73 | 3.05% | $116.58 |
| 2023 | 2.0bp | 4.0bp | $1,338.40 | 73 | 3.20% | $116.58 |
| 2023 | 2.0bp | 8.0bp | $927.48 | 73 | 3.48% | $116.58 |
| 2023 | 8.0bp | 2.0bp | $1,391.06 | 73 | 2.79% | $100.00 |
| 2023 | 8.0bp | 4.0bp | $1,203.65 | 73 | 2.92% | $100.00 |
| 2023 | 8.0bp | 8.0bp | $828.84 | 73 | 3.18% | $100.00 |
| 2024 | 2.0bp | 2.0bp | $3,715.16 | 83 | 1.71% | $115.41 |
| 2024 | 2.0bp | 4.0bp | $3,517.34 | 83 | 1.75% | $115.41 |
| 2024 | 2.0bp | 8.0bp | $3,121.70 | 83 | 1.83% | $115.41 |
| 2024 | 8.0bp | 2.0bp | $3,402.84 | 83 | 1.62% | $100.00 |
| 2024 | 8.0bp | 4.0bp | $3,220.18 | 83 | 1.66% | $100.00 |
| 2024 | 8.0bp | 8.0bp | $2,854.86 | 83 | 1.73% | $100.00 |
| 2025 | 2.0bp | 2.0bp | $6,123.14 | 80 | 1.80% | $111.48 |
| 2025 | 2.0bp | 4.0bp | $5,958.65 | 80 | 1.84% | $111.48 |
| 2025 | 2.0bp | 8.0bp | $5,629.68 | 80 | 1.92% | $111.48 |
| 2025 | 8.0bp | 2.0bp | $5,664.25 | 80 | 1.73% | $100.00 |
| 2025 | 8.0bp | 4.0bp | $5,510.99 | 80 | 1.76% | $100.00 |
| 2025 | 8.0bp | 8.0bp | $5,204.48 | 80 | 1.84% | $100.00 |
| 2026 | 2.0bp | 2.0bp | $1,431.87 | 74 | 3.50% | $116.76 |
| 2026 | 2.0bp | 4.0bp | $1,236.42 | 74 | 3.63% | $116.76 |
| 2026 | 2.0bp | 8.0bp | $845.52 | 74 | 3.89% | $116.76 |
| 2026 | 8.0bp | 2.0bp | $1,262.72 | 74 | 3.27% | $100.00 |
| 2026 | 8.0bp | 4.0bp | $1,083.58 | 74 | 3.39% | $100.00 |
| 2026 | 8.0bp | 8.0bp | $725.30 | 74 | 3.64% | $100.00 |

Full-period metrics reproduce the frozen v1.11 main result exactly. Annual tests reset accounts, use causal preceding indicator history, and are not added to the full-period return.

Planned stop risk is an estimate. Next-open gaps, stop gaps, financing, spread/depth and costs beyond the assumed reserve can exceed $100. This test does not observe an order book or actual Breakout fills. An 8bp reserve is a fixed stress assumption, not a claimed normal fill rate.

The candidate must earn lower stressed drawdown while retaining at least 90% of positive baseline stressed net, plus the separately registered positive-net, drawdown, trade-count and confidence checks. Historical outcomes cannot promote it or revise its protocol.

[Breakout execution guidance](https://intercom.help/breakoutprop/en/articles/16110234-why-does-my-fill-price-differ-from-the-quoted-price).

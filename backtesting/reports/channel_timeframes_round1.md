# Coarse channel timeframes

Twelve predefined variants: 1h/4h/daily signals, prior 20/55-candle channels, EMA200 direction, two fixed exit profiles. No RVOL or trend-distance threshold. $100 planned risk, fixed 8bp sizing; fees, financing, two ticks and 2/4/8bp actual slippage.

**Consumed development history, not independent validation.** Train on 2020-2023 annual closed outcomes at 8bp. Top candidate per timeframe enters 2024; selection freezes before 2025-2026. Training and 2024 end December 25 to leave seven-day gaps. All failed and undersampled candidates remain in the record.

| Candidate | Penalized training score | Eligible |
| --- | ---: | --- |
| channel_1h_20_balanced | -8248.96 | False |
| channel_1h_20_patient | -6221.09 | False |
| channel_1h_55_balanced | -1629.52 | False |
| channel_1h_55_patient | -1897.17 | False |
| channel_4h_20_balanced | 49.28 | True |
| channel_4h_20_patient | 164.18 | True |
| channel_4h_55_balanced | -853.00 | False |
| channel_4h_55_patient | -176.77 | False |
| channel_24h_20_balanced | -578.38 | False |
| channel_24h_20_patient | -963.93 | False |
| channel_24h_55_balanced | -191.28 | False |
| channel_24h_55_patient | -452.14 | False |

Selected: **channel_4h_20_patient**.

| Period | Strategy | Fill cost | Net including open marks | Closed net | Drawdown | Entries |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| audit_2025 | challenger | 2.0bp | $863.52 | $863.52 | 1.38% | 41 |
| audit_2025 | original_2bp_budget | 2.0bp | $6,123.14 | $6,123.14 | 1.80% | 80 |
| audit_2025 | baseline_8bp_budget | 2.0bp | $5,664.25 | $5,664.25 | 1.73% | 80 |
| audit_2025 | challenger | 4.0bp | $839.99 | $839.99 | 1.39% | 41 |
| audit_2025 | original_2bp_budget | 4.0bp | $5,958.65 | $5,958.65 | 1.84% | 80 |
| audit_2025 | baseline_8bp_budget | 4.0bp | $5,510.99 | $5,510.99 | 1.76% | 80 |
| audit_2025 | challenger | 8.0bp | $792.94 | $792.94 | 1.41% | 41 |
| audit_2025 | original_2bp_budget | 8.0bp | $5,629.68 | $5,629.68 | 1.92% | 80 |
| audit_2025 | baseline_8bp_budget | 8.0bp | $5,204.48 | $5,204.48 | 1.84% | 80 |
| audit_2026 | challenger | 2.0bp | $820.44 | $863.04 | 1.85% | 36 |
| audit_2026 | original_2bp_budget | 2.0bp | $1,431.87 | $1,431.87 | 3.50% | 74 |
| audit_2026 | baseline_8bp_budget | 2.0bp | $1,262.72 | $1,262.72 | 3.27% | 74 |
| audit_2026 | challenger | 4.0bp | $793.36 | $836.36 | 1.87% | 36 |
| audit_2026 | original_2bp_budget | 4.0bp | $1,236.42 | $1,236.42 | 3.63% | 74 |
| audit_2026 | baseline_8bp_budget | 4.0bp | $1,083.58 | $1,083.58 | 3.39% | 74 |
| audit_2026 | challenger | 8.0bp | $739.21 | $783.02 | 1.91% | 36 |
| audit_2026 | original_2bp_budget | 8.0bp | $845.52 | $845.52 | 3.89% | 74 |
| audit_2026 | baseline_8bp_budget | 8.0bp | $725.30 | $725.30 | 3.64% | 74 |
| full_development | challenger | 2.0bp | $2,619.78 | $2,662.38 | 1.80% | 165 |
| full_development | original_2bp_budget | 2.0bp | $13,166.91 | $13,166.91 | 3.03% | 312 |
| full_development | baseline_8bp_budget | 2.0bp | $12,027.66 | $12,027.66 | 2.78% | 312 |
| full_development | challenger | 4.0bp | $2,503.42 | $2,546.42 | 1.83% | 165 |
| full_development | original_2bp_budget | 4.0bp | $12,397.38 | $12,397.38 | 3.17% | 312 |
| full_development | baseline_8bp_budget | 4.0bp | $11,319.60 | $11,319.60 | 2.91% | 312 |
| full_development | challenger | 8.0bp | $2,270.71 | $2,314.52 | 1.90% | 165 |
| full_development | original_2bp_budget | 8.0bp | $10,858.31 | $10,858.31 | 3.46% | 312 |
| full_development | baseline_8bp_budget | 8.0bp | $9,903.46 | $9,903.46 | 3.16% | 312 |

All comparative replays use causal 2020-2022 indicator warm-up. Annual accounts reset. This does not promote a version, open the future holdout or guarantee future profits.

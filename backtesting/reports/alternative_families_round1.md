# Alternative strategy families: bounded chronological development

24 predefined candidates: six families, 1h/4h signals, two fixed exit profiles. Fixed $100 planned risk, 8bp sizing budget, real five-minute ETH futures execution, fees, financing and stop-first ambiguity handling. No future data is used.

**All dates were previously inspected. This is development research, not an untouched holdout or evidence of future profitability.** The original strategy and forward protocols are preserved. Failed candidates and the exact shortlist/selection are retained.

Training selection uses 2020-2023 annual closed outcomes at 8bp fills. The top training candidate per family is checked on 2024. Both 2023 and 2024 execution end December 25, leaving a seven-day gap before the next selection/evaluation stage. Open outcomes are excluded from selection. The final choice is frozen before 2025-2026 diagnostic outcomes. These diagnostics never change that choice.

| Candidate | Training score | Eligible training | 2024 closed net | Eligible 2024 |
| --- | ---: | --- | ---: | --- |
| trend_pullback_1h_balanced | -7512.10 | False | Not shortlisted | Not evaluated |
| trend_pullback_1h_patient | -4387.63 | False | Not shortlisted | Not evaluated |
| trend_pullback_4h_balanced | -1031.04 | False | Not shortlisted | Not evaluated |
| trend_pullback_4h_patient | -346.46 | False | $990.53 | False |
| rsi_pullback_1h_balanced | -6184.44 | False | Not shortlisted | Not evaluated |
| rsi_pullback_1h_patient | -3485.99 | False | Not shortlisted | Not evaluated |
| rsi_pullback_4h_balanced | -197.20 | False | Not shortlisted | Not evaluated |
| rsi_pullback_4h_patient | 240.46 | True | $444.55 | True |
| squeeze_breakout_1h_balanced | -5533.54 | False | Not shortlisted | Not evaluated |
| squeeze_breakout_1h_patient | -4606.05 | False | Not shortlisted | Not evaluated |
| squeeze_breakout_4h_balanced | -1684.72 | False | Not shortlisted | Not evaluated |
| squeeze_breakout_4h_patient | -1226.31 | False | $-171.06 | False |
| supertrend_1h_balanced | -2973.52 | False | Not shortlisted | Not evaluated |
| supertrend_1h_patient | -2711.31 | False | Not shortlisted | Not evaluated |
| supertrend_4h_balanced | -23.63 | False | $365.52 | False |
| supertrend_4h_patient | -98.94 | False | Not shortlisted | Not evaluated |
| range_reversion_1h_balanced | -168.82 | False | Not shortlisted | Not evaluated |
| range_reversion_1h_patient | -279.76 | False | Not shortlisted | Not evaluated |
| range_reversion_4h_balanced | -188.13 | False | Not shortlisted | Not evaluated |
| range_reversion_4h_patient | -77.69 | False | $0.00 | False |
| time_series_momentum_1h_balanced | -7280.06 | False | Not shortlisted | Not evaluated |
| time_series_momentum_1h_patient | -6973.66 | False | Not shortlisted | Not evaluated |
| time_series_momentum_4h_balanced | -1170.05 | False | Not shortlisted | Not evaluated |
| time_series_momentum_4h_patient | -231.37 | False | $114.33 | False |

Selected before audit: **rsi_pullback_4h_patient**.

| Period | Strategy | Actual slippage | Net including open marks | Closed net | Intrabar drawdown | Entries |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| audit_2025 | challenger | 2.0bp | $623.12 | $586.43 | 0.94% | 27 |
| audit_2025 | v1.11_original_budget | 2.0bp | $6,123.14 | $6,123.14 | 1.80% | 80 |
| audit_2025 | v1.12_8bp_budget | 2.0bp | $5,664.25 | $5,664.25 | 1.73% | 80 |
| audit_2025 | challenger | 4.0bp | $607.03 | $570.84 | 0.96% | 27 |
| audit_2025 | v1.11_original_budget | 4.0bp | $5,958.65 | $5,958.65 | 1.84% | 80 |
| audit_2025 | v1.12_8bp_budget | 4.0bp | $5,510.99 | $5,510.99 | 1.76% | 80 |
| audit_2025 | challenger | 8.0bp | $574.83 | $539.66 | 0.99% | 27 |
| audit_2025 | v1.11_original_budget | 8.0bp | $5,629.68 | $5,629.68 | 1.92% | 80 |
| audit_2025 | v1.12_8bp_budget | 8.0bp | $5,204.48 | $5,204.48 | 1.84% | 80 |
| audit_2026 | challenger | 2.0bp | $507.43 | $393.26 | 1.13% | 22 |
| audit_2026 | v1.11_original_budget | 2.0bp | $1,431.87 | $1,431.87 | 3.50% | 74 |
| audit_2026 | v1.12_8bp_budget | 2.0bp | $1,262.72 | $1,262.72 | 3.27% | 74 |
| audit_2026 | challenger | 4.0bp | $491.20 | $377.45 | 1.14% | 22 |
| audit_2026 | v1.11_original_budget | 4.0bp | $1,236.42 | $1,236.42 | 3.63% | 74 |
| audit_2026 | v1.12_8bp_budget | 4.0bp | $1,083.58 | $1,083.58 | 3.39% | 74 |
| audit_2026 | challenger | 8.0bp | $458.74 | $345.82 | 1.16% | 22 |
| audit_2026 | v1.11_original_budget | 8.0bp | $845.52 | $845.52 | 3.89% | 74 |
| audit_2026 | v1.12_8bp_budget | 8.0bp | $725.30 | $725.30 | 3.64% | 74 |
| full_development | challenger | 2.0bp | $2,302.64 | $2,188.48 | 1.84% | 97 |
| full_development | v1.11_original_budget | 2.0bp | $13,166.91 | $13,166.91 | 3.03% | 312 |
| full_development | v1.12_8bp_budget | 2.0bp | $12,027.66 | $12,027.66 | 2.78% | 312 |
| full_development | challenger | 4.0bp | $2,232.74 | $2,118.98 | 1.86% | 97 |
| full_development | v1.11_original_budget | 4.0bp | $12,397.38 | $12,397.38 | 3.17% | 312 |
| full_development | v1.12_8bp_budget | 4.0bp | $11,319.60 | $11,319.60 | 2.91% | 312 |
| full_development | challenger | 8.0bp | $2,092.92 | $1,979.99 | 1.92% | 97 |
| full_development | v1.11_original_budget | 8.0bp | $10,858.31 | $10,858.31 | 3.46% | 312 |
| full_development | v1.12_8bp_budget | 8.0bp | $9,903.46 | $9,903.46 | 3.16% | 312 |

Historical comparison checks: `{'higher_main': False, 'higher_stressed': False, 'drawdown_limit': True, 'positive_later_annual_closed': True}`. Historical comparison passed: **False**. No version is automatically promoted.

All comparisons have causal prior 2020-2022 indicator warm-up before the 2023 benchmark. This can differ from the saved $12,814.03 run, which initialized indicators at the start of 2023; neither history nor initialization is adjusted after outcomes. Annual accounts reset and their nets are not summed as a continuous return.

848 earlier logged search slots, plus one cost-reserve hypothesis and these 24 alternatives, are known research exposure. This is not a complete independent trial count. A new winner would need its own preregistered future test; consumed venue/asset data cannot become unseen again.

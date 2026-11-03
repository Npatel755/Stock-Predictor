# Structural robustness: wider stops, fresh-breakout guard, parameter ensembles

Ten predefined candidates keep the frozen v1.11 channel/EMA250/RVOL/trend-gap entries and change structure only: (a) initial stop 2.0/2.5/3.0 ATR with the target distance held at 8.25 ATR and the 3 ATR trail unchanged; (b) a guard that rejects an entry preceded by more than two same-direction raw channel breakouts in the prior 72 completed hours, with each stop width; (c) ensembles of neighbouring channel-length/RVOL settings traded as independent $100/n-risk sub-accounts. Fixed $100 planned risk, 8bp sizing budget, real five-minute ETH futures execution, fees, financing and stop-first ambiguity handling. No future data is used.

**All dates were previously inspected. This is development research, not an untouched holdout or evidence of future profitability.** The original strategy and forward protocols are preserved. Failed candidates and the exact shortlist/selection are retained.

Motivation from the consumed v1.11 ledger: trades stopped within two hours lose about $4.8k of $9.4k total stop losses at a 5% win rate because the 1.5 ATR stop sits inside the median 2.8 ATR breakout candle, while no causal entry feature predicts trade R well enough to filter on.

Training selection uses 2020-2023 annual closed outcomes at 8bp fills and must beat the same-budget v1.11 replica. The top eligible candidate per group is checked on 2024. Both 2023 and 2024 execution end December 25, leaving a seven-day gap before the next stage. The final choice is frozen before 2025-2026 diagnostic outcomes, which never change it.

Same-budget v1.11 replica training score: 410.06 (median annual closed net $1,199.84).

| Candidate | Group | Training score | Median annual closed | Eligible training | 2024 closed net | 2024 drawdown | Eligible 2024 |
| --- | --- | ---: | ---: | --- | ---: | ---: | --- |
| stop2_target8.25 | stop_geometry | 459.51 | $1,142.00 | True | $1,930.06 | 1.58% | True |
| stop2.5_target8.25 | stop_geometry | 230.18 | $886.92 | False | Not shortlisted |  | Not evaluated |
| stop3_target8.25 | stop_geometry | 268.20 | $847.52 | False | Not shortlisted |  | Not evaluated |
| fresh72_stop1.5 | fresh_breakout_guard | 231.13 | $920.22 | False | Not shortlisted |  | Not evaluated |
| fresh72_stop2 | fresh_breakout_guard | 364.11 | $955.66 | False | $1,438.88 | 1.01% | False |
| fresh72_stop2.5 | fresh_breakout_guard | 325.25 | $943.54 | False | Not shortlisted |  | Not evaluated |
| fresh72_stop3 | fresh_breakout_guard | 53.79 | $732.77 | False | Not shortlisted |  | Not evaluated |
| ensemble_lookback_3 | parameter_ensemble | 641.00 | $1,371.42 | True | Not shortlisted |  | Not evaluated |
| ensemble_rvol_3 | parameter_ensemble | 555.60 | $1,299.87 | True | Not shortlisted |  | Not evaluated |
| ensemble_grid_9 | parameter_ensemble | 769.52 | $1,453.13 | True | $2,279.73 | 1.54% | True |

Selected before audit: **ensemble_grid_9**.

| Period | Strategy | Actual slippage | Net including open marks | Closed net | Drawdown | Entries | Closed trades |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| audit_2025 | challenger | 2.0bp | $5,024.47 | $5,024.47 | 1.76% | 723 | 723 |
| audit_2025 | v1.11_original_budget | 2.0bp | $6,123.14 | $6,123.14 | 1.80% | 80 | 80 |
| audit_2025 | v1.12_8bp_budget | 2.0bp | $5,664.25 | $5,664.25 | 1.73% | 80 | 80 |
| audit_2025 | challenger | 4.0bp | $4,869.88 | $4,869.88 | 1.80% | 723 | 723 |
| audit_2025 | v1.11_original_budget | 4.0bp | $5,958.65 | $5,958.65 | 1.84% | 80 | 80 |
| audit_2025 | v1.12_8bp_budget | 4.0bp | $5,510.99 | $5,510.99 | 1.76% | 80 | 80 |
| audit_2025 | challenger | 8.0bp | $4,560.72 | $4,560.72 | 1.87% | 723 | 723 |
| audit_2025 | v1.11_original_budget | 8.0bp | $5,629.68 | $5,629.68 | 1.92% | 80 | 80 |
| audit_2025 | v1.12_8bp_budget | 8.0bp | $5,204.48 | $5,204.48 | 1.84% | 80 | 80 |
| audit_2026 | challenger | 2.0bp | $1,017.23 | $1,017.23 | 3.39% | 655 | 655 |
| audit_2026 | v1.11_original_budget | 2.0bp | $1,431.87 | $1,431.87 | 3.50% | 74 | 74 |
| audit_2026 | v1.12_8bp_budget | 2.0bp | $1,262.72 | $1,262.72 | 3.27% | 74 | 74 |
| audit_2026 | challenger | 4.0bp | $840.87 | $840.87 | 3.51% | 655 | 655 |
| audit_2026 | v1.11_original_budget | 4.0bp | $1,236.42 | $1,236.42 | 3.63% | 74 | 74 |
| audit_2026 | v1.12_8bp_budget | 4.0bp | $1,083.58 | $1,083.58 | 3.39% | 74 | 74 |
| audit_2026 | challenger | 8.0bp | $488.15 | $488.15 | 3.75% | 655 | 655 |
| audit_2026 | v1.11_original_budget | 8.0bp | $845.52 | $845.52 | 3.89% | 74 | 74 |
| audit_2026 | v1.12_8bp_budget | 8.0bp | $725.30 | $725.30 | 3.64% | 74 | 74 |
| full_development | challenger | 2.0bp | $10,761.15 | $10,761.15 | 2.83% | 2806 | 2806 |
| full_development | v1.11_original_budget | 2.0bp | $13,166.91 | $13,166.91 | 3.03% | 312 | 312 |
| full_development | v1.12_8bp_budget | 2.0bp | $12,027.66 | $12,027.66 | 2.78% | 312 | 312 |
| full_development | challenger | 4.0bp | $10,050.19 | $10,050.19 | 2.95% | 2806 | 2806 |
| full_development | v1.11_original_budget | 4.0bp | $12,397.38 | $12,397.38 | 3.17% | 312 | 312 |
| full_development | v1.12_8bp_budget | 4.0bp | $11,319.60 | $11,319.60 | 2.91% | 312 | 312 |
| full_development | challenger | 8.0bp | $8,628.28 | $8,628.28 | 3.20% | 2806 | 2806 |
| full_development | v1.11_original_budget | 8.0bp | $10,858.31 | $10,858.31 | 3.46% | 312 | 312 |
| full_development | v1.12_8bp_budget | 8.0bp | $9,903.46 | $9,903.46 | 3.16% | 312 | 312 |

Historical comparison checks: `{'higher_main': False, 'higher_stressed': False, 'drawdown_limit': True, 'positive_later_annual_closed': True}`. Historical comparison passed: **False**. No version is automatically promoted.

Ensemble drawdowns are the summed bar-close curve plus each member intrabar excess, an upper bound; single-rule drawdowns are intrabar. All comparisons have causal prior 2020-2022 indicator warm-up before the 2023 benchmark and can differ from the saved $12,814.03 run. Annual accounts reset and their nets are not summed as a continuous return.

848 earlier logged search slots, 46 earlier lab candidates and these 10 are known research exposure, not a complete independent trial count. A selected candidate would need its own preregistered future test; consumed data cannot become unseen again.

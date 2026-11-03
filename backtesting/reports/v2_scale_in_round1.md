# v2 scale-in candidates: half risk at the signal, half after follow-through

Six predefined candidates keep every frozen v1.11 entry, filter, target and trailing rule and change only how the $100 planned risk is deployed: a $50 core leg at the signal and a $50 add-on leg after price closes trigger_r (0.5/1.0/1.5) initial-risk units in favour, either moving the core stop to breakeven with the add-on stopped at the core entry, or keeping the original stop for both. Both legs fill at the next open and target the core target. Two independent Broker sub-accounts are summed into one $50,000 account, so execution, fees, financing and stop-first handling are the shared frozen code.

**All dates were previously inspected. This is development research, not an untouched holdout or evidence of future profitability.** v1.11 and its forward protocol are untouched. Failed candidates and the frozen shortlist/selection are retained.

Training uses 2020-2023 annual closed outcomes at 8bp fills and must beat the same-budget v1.11 replica (score 410.06, median annual closed $1,199.84). The top eligible candidate per add-on-stop group is checked on 2024 (v1.11 same budget: $2,854.86). Execution ends December 25 in 2023 and 2024, leaving seven-day gaps. The selection is frozen before 2025-2026 outcomes.

| Candidate | Training score | Median annual closed | Eligible training | 2024 closed net | 2024 drawdown | Eligible 2024 |
| --- | ---: | ---: | --- | ---: | ---: | --- |
| scalein_t0.5_breakeven | -1174.00 | $218.69 | False | Not shortlisted |  | Not evaluated |
| scalein_t0.5_original | 517.08 | $1,048.70 | True | $2,078.81 | 1.25% | True |
| scalein_t1_breakeven | 405.92 | $874.21 | False | Not shortlisted |  | Not evaluated |
| scalein_t1_original | 338.07 | $838.61 | False | Not shortlisted |  | Not evaluated |
| scalein_t1.5_breakeven | 439.33 | $887.92 | True | $1,940.97 | 1.15% | True |
| scalein_t1.5_original | 340.12 | $774.33 | False | Not shortlisted |  | Not evaluated |

Selected before audit: **scalein_t0.5_original**.

| Period | Strategy | Actual slippage | Net including open marks | Closed net | Drawdown | Core entries | Closed legs |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| audit_2025 | challenger | 2.0bp | $4,207.77 | $4,207.77 | 1.37% | 80 | 137 |
| audit_2025 | v1.11_original_budget | 2.0bp | $6,123.14 | $6,123.14 | 1.80% | 80 | 80 |
| audit_2025 | v1.12_8bp_budget | 2.0bp | $5,664.25 | $5,664.25 | 1.73% | 80 | 80 |
| audit_2025 | challenger | 4.0bp | $4,050.72 | $4,050.72 | 1.40% | 80 | 137 |
| audit_2025 | v1.11_original_budget | 4.0bp | $5,958.65 | $5,958.65 | 1.84% | 80 | 80 |
| audit_2025 | v1.12_8bp_budget | 4.0bp | $5,510.99 | $5,510.99 | 1.76% | 80 | 80 |
| audit_2025 | challenger | 8.0bp | $3,791.75 | $3,791.75 | 1.45% | 80 | 137 |
| audit_2025 | v1.11_original_budget | 8.0bp | $5,629.68 | $5,629.68 | 1.92% | 80 | 80 |
| audit_2025 | v1.12_8bp_budget | 8.0bp | $5,204.48 | $5,204.48 | 1.84% | 80 | 80 |
| audit_2026 | challenger | 2.0bp | $1,182.15 | $1,182.15 | 2.45% | 74 | 116 |
| audit_2026 | v1.11_original_budget | 2.0bp | $1,431.87 | $1,431.87 | 3.50% | 74 | 74 |
| audit_2026 | v1.12_8bp_budget | 2.0bp | $1,262.72 | $1,262.72 | 3.27% | 74 | 74 |
| audit_2026 | challenger | 4.0bp | $1,030.63 | $1,030.63 | 2.55% | 74 | 116 |
| audit_2026 | v1.11_original_budget | 4.0bp | $1,236.42 | $1,236.42 | 3.63% | 74 | 74 |
| audit_2026 | v1.12_8bp_budget | 4.0bp | $1,083.58 | $1,083.58 | 3.39% | 74 | 74 |
| audit_2026 | challenger | 8.0bp | $818.52 | $818.52 | 2.62% | 74 | 115 |
| audit_2026 | v1.11_original_budget | 8.0bp | $845.52 | $845.52 | 3.89% | 74 | 74 |
| audit_2026 | v1.12_8bp_budget | 8.0bp | $725.30 | $725.30 | 3.64% | 74 | 74 |
| full_development | challenger | 2.0bp | $9,733.03 | $9,733.03 | 2.11% | 311 | 502 |
| full_development | v1.11_original_budget | 2.0bp | $13,166.91 | $13,166.91 | 3.03% | 312 | 312 |
| full_development | v1.12_8bp_budget | 2.0bp | $12,027.66 | $12,027.66 | 2.78% | 312 | 312 |
| full_development | challenger | 4.0bp | $9,059.47 | $9,059.47 | 2.21% | 311 | 502 |
| full_development | v1.11_original_budget | 4.0bp | $12,397.38 | $12,397.38 | 3.17% | 312 | 312 |
| full_development | v1.12_8bp_budget | 4.0bp | $11,319.60 | $11,319.60 | 2.91% | 312 | 312 |
| full_development | challenger | 8.0bp | $7,923.52 | $7,923.52 | 2.30% | 311 | 501 |
| full_development | v1.11_original_budget | 8.0bp | $10,858.31 | $10,858.31 | 3.46% | 312 | 312 |
| full_development | v1.12_8bp_budget | 8.0bp | $9,903.46 | $9,903.46 | 3.16% | 312 | 312 |

Historical comparison checks: `{'higher_main': False, 'higher_stressed': False, 'drawdown_limit': True, 'positive_later_annual_closed': True}`. Historical comparison passed: **False**. No candidate was registered or promoted.

Scale-in drawdowns are the summed core+add-on bar-close curve plus each leg's intrabar excess, an upper bound; v1.11 drawdowns are intrabar. Closed legs count core and add-on exits separately. Annual accounts reset and are not summed as a continuous return.

848 earlier logged search slots, 56 earlier lab candidates and these 6 are known research exposure, not a complete trial count. Consumed data cannot become unseen again; only the sealed future period can validate the candidate.

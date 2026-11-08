# Top 15 Robust 500k Finalists: Validation & Test Evaluation

Evaluated all 15 top training finalists across MNQ 2024–2025 Validation and 2026 Test partitions with **strictly zero tuning**.
All parameters, indicators, stops, targets, holding periods, and execution rules remained 100% frozen.

> [!NOTE]
> **Validation (2024–2025)** and **Test (2026)** were evaluated under fixed single-use reservations.
> Per project research policy, 2026 test split is disclosed as a previously observed reused test period.

## Comprehensive Multi-Split Performance Matrix

| # | Candidate ID | Family | Training Net (2020–23) | Train DD | Val Net (2024–25) | Val Intrabar DD | Val PF | Val Trades | Test Net (2026) | Test Intrabar DD | Test PF | Test Trades | Val+Test Net | All-Split Total Net |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | `mass_da4b2da7ac857a8faa56` | hybrid | $3,073.50 | $471.38 | **$52.00** | $345.38 | 1.19 | 9 | $0.00 | $0.00 | 0.00 | 0 | $52.00 | $3,125.50 |
| 2 | `mass_489c855396f8c5011677` | hybrid | $3,073.50 | $471.50 | **$52.00** | $345.50 | 1.19 | 9 | $0.00 | $0.00 | 0.00 | 0 | $52.00 | $3,125.50 |
| 3 | `mass_c3cc1820a1dfec3418ec` | hybrid | $3,075.00 | $416.88 | **$189.00** | $180.38 | 1.74 | 9 | $0.00 | $0.00 | 0.00 | 0 | $189.00 | $3,264.00 |
| 4 | `mass_bafb5efef1abe7bda10e` | hybrid | $2,927.00 | $471.25 | **$52.00** | $345.25 | 1.19 | 9 | $0.00 | $0.00 | 0.00 | 0 | $52.00 | $2,979.00 |
| 5 | `mass_66b04ece059553dcf9a0` | momentum | $3,834.00 | $467.25 | **$276.50** | $180.25 | 2.52 | 9 | $0.00 | $0.00 | 0.00 | 0 | $276.50 | $4,110.50 |
| 6 | `mass_449f46d359f427350fca` | hybrid | $2,830.50 | $471.25 | **$189.00** | $268.25 | 1.68 | 9 | $0.00 | $0.00 | 0.00 | 0 | $189.00 | $3,019.50 |
| 7 | `mass_2a7ad27564f6adb8b201` | momentum | $2,920.00 | $409.25 | **$189.00** | $180.25 | 1.74 | 9 | $0.00 | $0.00 | 0.00 | 0 | $189.00 | $3,109.00 |
| 8 | `mass_3b5c5c79a1cca93fae90` | hybrid | $2,900.00 | $439.00 | **$55.50** | $342.00 | 1.20 | 9 | $0.00 | $0.00 | 0.00 | 0 | $55.50 | $2,955.50 |
| 9 | `mass_a304d5feb29f080cc06a` | hybrid | $2,862.50 | $409.25 | **$189.00** | $180.25 | 1.74 | 9 | $0.00 | $0.00 | 0.00 | 0 | $189.00 | $3,051.50 |
| 10 | `mass_df8dec7746923f1b782c` | momentum | $2,909.50 | $422.25 | **$967.00** | $449.75 | 1.88 | 35 | **$57.00** | $369.75 | 1.17 | 5 | $1,024.00 | $3,933.50 |
| 11 | `mass_8bd94e865854ee746283` | momentum | $2,804.50 | $438.75 | **$55.50** | $341.75 | 1.20 | 9 | $0.00 | $0.00 | 0.00 | 0 | $55.50 | $2,860.00 |
| 12 | `mass_2f41b3bd02298beda570` | hybrid | $2,801.50 | $438.88 | **$192.50** | $264.88 | 1.70 | 9 | $0.00 | $0.00 | 0.00 | 0 | $192.50 | $2,994.00 |
| 13 | `mass_e57ba183f302b3ba886b` | momentum | $4,935.50 | $533.25 | **$2,605.00** | $432.25 | 2.41 | 55 | **$2,898.50** | $394.25 | 3.39 | 31 | $5,503.50 | $10,439.00 |
| 14 | `mass_f0e51652ed49a60492f7` | trend | $3,504.50 | $514.50 | **$473.00** | $437.00 | 1.26 | 55 | $-261.00 | $261.00 | 0.00 | 2 | $212.00 | $3,716.50 |
| 15 | `mass_5c0ca9b808275b8a44ce` | hybrid | $4,733.50 | $568.25 | $-1,456.50 | $1,654.25 | 0.53 | 99 | **$251.50** | $425.25 | 1.37 | 29 | $-1,205.00 | $3,528.50 |

## Parameter Specifications for Top Finalists

| # | Candidate ID | Family | Lookback | Threshold | Stop ATR | Target R | Hold | Session (ET) | Contracts | Trail ATR |
|---|---|---|---:|---:|---:|---:|---:|---|---:|---:|
| 1 | `mass_da4b2da7ac857a8faa56` | hybrid | 8 | 1.5 | 3.0 | 4.0 | 4 | 09:45–15:45 | 2 | 0.0 |
| 2 | `mass_489c855396f8c5011677` | hybrid | 8 | 1.5 | 3.0 | 4.0 | 4 | 09:45–15:45 | 3 | 0.0 |
| 3 | `mass_c3cc1820a1dfec3418ec` | hybrid | 8 | 1.5 | 3.0 | 1.0 | 4 | 09:45–15:45 | 2 | 0.0 |
| 4 | `mass_bafb5efef1abe7bda10e` | hybrid | 8 | 1.5 | 3.0 | 3.0 | 4 | 09:45–15:45 | 1 | 0.0 |
| 5 | `mass_66b04ece059553dcf9a0` | momentum | 8 | 1.5 | 3.0 | 1.0 | 16 | 09:45–15:45 | 1 | 0.0 |
| 6 | `mass_449f46d359f427350fca` | hybrid | 8 | 1.5 | 3.0 | 2.0 | 4 | 09:45–15:45 | 1 | 0.0 |
| 7 | `mass_2a7ad27564f6adb8b201` | momentum | 8 | 1.5 | 3.0 | 1.0 | 4 | 09:45–15:45 | 1 | 2.0 |
| 8 | `mass_3b5c5c79a1cca93fae90` | hybrid | 8 | 1.5 | 3.0 | 4.0 | 4 | 09:45–15:45 | 3 | 2.0 |
| 9 | `mass_a304d5feb29f080cc06a` | hybrid | 8 | 1.5 | 3.0 | 1.0 | 4 | 09:45–15:45 | 1 | 2.0 |
| 10 | `mass_df8dec7746923f1b782c` | momentum | 48 | 1.0 | 1.5 | 4.0 | 12 | 10:00–12:00 | 1 | 1.0 |
| 11 | `mass_8bd94e865854ee746283` | momentum | 8 | 1.5 | 3.0 | 4.0 | 4 | 09:45–15:45 | 1 | 2.0 |
| 12 | `mass_2f41b3bd02298beda570` | hybrid | 8 | 1.5 | 3.0 | 2.0 | 4 | 09:45–15:45 | 2 | 2.0 |
| 13 | `mass_e57ba183f302b3ba886b` | momentum | 16 | 1.5 | 1.0 | 4.0 | 12 | 09:45–15:45 | 1 | 2.0 |
| 14 | `mass_f0e51652ed49a60492f7` | trend | 8 | 1.0 | 2.0 | 1.5 | 2 | 09:45–11:30 | 3 | 0.0 |
| 15 | `mass_5c0ca9b808275b8a44ce` | hybrid | 24 | 1.0 | 2.0 | 1.5 | 16 | 14:00–15:45 | 1 | 0.0 |

## Detailed Observations & Out-of-Sample Parity

1. **Zero Tuning Protocol**: No parameters were modified, fitted, or adjusted against validation or test data. All 15 strategies were frozen directly from the 500k training search.
2. **Execution Realism**: Evaluated with micro contract economics ($2/pt MNQ, $0.50/side commissions, $0.50/pt slippage, $150 trade risk cap, $300 daily loss, $1,800 hard drawdown).

## Artifacts

- Frozen Manifest: `runs/top15_500k_val_test_v1/frozen_candidates.json`
- Validation Results: `runs/top15_500k_val_test_v1/validation_results.json`
- Test Results: `runs/top15_500k_val_test_v1/test_results.json`
- Full Summary: `reports/top15_500k_val_test_summary.json`
# 500,000 Additional Training Configurations

**500,000 new configurations completed; 870,000 distinct active configurations across all completed mass searches.** 5,343 met the anti-overfitting training research gates.

No validation/test prices or protected outcome records were read by this search. Generation, ranking and selection used training inputs only. Tested across MNQ, MES, NQ, and ES across all 10 strategy families. All prior 370k active configurations were excluded; seeds 20261201 through 20261250 were fixed before training-price access.

## Selection policy & Anti-Overfitting Defense

Prioritizes high profit factor (>=1.30), low intrabar drawdown (<$2,000), clean turnover (80-800 trades), and multi-year consistency to eliminate low-margin churn and prevent curve-fitting. Ranks qualified candidates by Robustness Metric: `(net_pnl * (profit_factor - 1.0)) / max(intrabar_dd, 500)`. Includes Cross-Contract Transfer analysis for large-to-micro mappings.

## Training result

Selected `mass_da4b2da7ac857a8faa56`: MNQ / hybrid.

| Metric | New base | New 2x costs | Saved benchmark |
|---|---:|---:|---:|
| Aggregate net | $3,073.50 | $2,896.50 | $6,893.50 |
| Worst annual cash DD | $393.00 | $345.00 | $1,686.00 |
| Worst annual closing DD | $438.00 | $395.50 | $1,749.50 |
| Worst annual intrabar DD | $471.38 | $430.25 | $1,799.00 |
| Profit factor | 2.63 | 2.66 | — |
| Trades | 102 | 98 | — |
| Evaluation-phase gates | False | False | — |

Research/post-evaluation gates: **PASS**. Survived 2x costs: **PASS**. Unseen performance and exact funded-account eligibility are **NOT ESTABLISHED**.

Frozen parameters:

```json
{
  "config_id": "mass_da4b2da7ac857a8faa56",
  "experiment_order": 59712,
  "family": "hybrid",
  "hold_bars": 4,
  "instrument": "MNQ",
  "lookback": 8,
  "max_contracts": 2,
  "session_end": 945,
  "session_start": 585,
  "stop_atr": 3.0,
  "target_r": 4.0,
  "threshold": 1.5,
  "trailing_atr": 0.0
}
```

| Training year | Net | Cash DD | Intrabar DD | Trades | Consistency ratio |
|---|---:|---:|---:|---:|---:|
| 2020 | $861.50 | $106.50 | $177.00 | 31 | 29.89% |
| 2021 | $1,816.50 | $155.50 | $218.38 | 40 | 15.77% |
| 2022 | $64.50 | $0.50 | $93.88 | 1 | 100.00% |
| 2023 | $331.00 | $393.00 | $471.38 | 30 | 71.60% |

## Top 15 Robust Training Finalists

| # | Candidate ID | Market | Family | Net P&L | Intrabar DD | Profit Factor | Trades | Target R | Stop ATR | Trail ATR |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | `mass_da4b2da7ac857a8faa56` | MNQ | hybrid | $3,073.50 | $471.38 | 2.63 | 102 | 4.0 | 3.0 | 0.0 |
| 2 | `mass_489c855396f8c5011677` | MNQ | hybrid | $3,073.50 | $471.50 | 2.63 | 102 | 4.0 | 3.0 | 0.0 |
| 3 | `mass_c3cc1820a1dfec3418ec` | MNQ | hybrid | $3,075.00 | $416.88 | 2.61 | 109 | 1.0 | 3.0 | 0.0 |
| 4 | `mass_bafb5efef1abe7bda10e` | MNQ | hybrid | $2,927.00 | $471.25 | 2.55 | 102 | 3.0 | 3.0 | 0.0 |
| 5 | `mass_66b04ece059553dcf9a0` | MNQ | momentum | $3,834.00 | $467.25 | 2.15 | 109 | 1.0 | 3.0 | 0.0 |
| 6 | `mass_449f46d359f427350fca` | MNQ | hybrid | $2,830.50 | $471.25 | 2.50 | 102 | 2.0 | 3.0 | 0.0 |
| 7 | `mass_2a7ad27564f6adb8b201` | MNQ | momentum | $2,920.00 | $409.25 | 2.43 | 110 | 1.0 | 3.0 | 2.0 |
| 8 | `mass_3b5c5c79a1cca93fae90` | MNQ | hybrid | $2,900.00 | $439.00 | 2.44 | 102 | 4.0 | 3.0 | 2.0 |
| 9 | `mass_a304d5feb29f080cc06a` | MNQ | hybrid | $2,862.50 | $409.25 | 2.40 | 109 | 1.0 | 3.0 | 2.0 |
| 10 | `mass_df8dec7746923f1b782c` | MNQ | momentum | $2,909.50 | $422.25 | 2.36 | 95 | 4.0 | 1.5 | 1.0 |
| 11 | `mass_8bd94e865854ee746283` | MNQ | momentum | $2,804.50 | $438.75 | 2.39 | 103 | 4.0 | 3.0 | 2.0 |
| 12 | `mass_2f41b3bd02298beda570` | MNQ | hybrid | $2,801.50 | $438.88 | 2.38 | 102 | 2.0 | 3.0 | 2.0 |
| 13 | `mass_e57ba183f302b3ba886b` | MNQ | momentum | $4,935.50 | $533.25 | 1.83 | 202 | 4.0 | 1.0 | 2.0 |
| 14 | `mass_f0e51652ed49a60492f7` | MNQ | trend | $3,504.50 | $514.50 | 2.12 | 164 | 1.5 | 2.0 | 0.0 |
| 15 | `mass_5c0ca9b808275b8a44ce` | MNQ | hybrid | $4,733.50 | $568.25 | 1.91 | 274 | 1.5 | 2.0 | 0.0 |

## Artifacts and limits

[All 500k ranked results](../runs/training_search_500k_v1/ranked.csv) · [Frozen 500k configuration manifest](../runs/training_search_500k_v1/configurations.jsonl) · [Protocol](../runs/training_search_500k_v1/protocol.json)

> [!IMPORTANT]
> **Validation and Test data remain completely unopened, unreserved, and untouched.** Zero tuning or selection has occurred on validation or test sets.

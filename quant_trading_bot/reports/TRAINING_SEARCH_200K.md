# 200,000 Additional Training Configurations

**200,000 new configurations completed; 370,000 distinct active configurations across all completed mass searches.** 2,131 met the anti-overfitting training research gates.

No validation/test prices or protected outcome records were read by this search. Generation, ranking and selection used training inputs only. The original families, parameter domains, execution logic, costs and risk limits were preserved. All prior 170k active configurations were excluded; seeds 20261123 through 20261142 were fixed before training-price access.

## Selection policy

Prioritizes high profit factor (>=1.30), low intrabar drawdown (<$2,000), clean turnover (80-800 trades), and multi-year consistency to eliminate low-margin churn and prevent curve-fitting. Ranks qualified candidates by Robustness Metric: `(net_pnl * (profit_factor - 1.0)) / max(intrabar_dd, 500)`.

## Training result

Selected `mass_7bf2833bf4365b60bedb`: MNQ / momentum.

| Metric | New base | New 2x costs | Saved benchmark |
|---|---:|---:|---:|
| Aggregate net | $2,888.00 | $2,822.00 | $6,893.50 |
| Worst annual cash DD | $393.00 | $339.50 | $1,686.00 |
| Worst annual closing DD | $438.00 | $388.00 | $1,749.50 |
| Worst annual intrabar DD | $471.25 | $422.50 | $1,799.00 |
| Profit factor | 2.53 | 2.64 | — |
| Trades | 103 | 99 | — |
| Evaluation-phase gates | False | False | — |

Research/post-evaluation gates: **PASS**. Survived 2x costs: **PASS**. Unseen performance and exact funded-account eligibility are **NOT ESTABLISHED**.

Frozen parameters:

```json
{
  "instrument": "MNQ",
  "family": "momentum",
  "lookback": 8,
  "threshold": 1.5,
  "stop_atr": 3.0,
  "target_r": 2.0,
  "hold_bars": 4,
  "session_start": 585,
  "session_end": 945,
  "max_contracts": 1,
  "trailing_atr": 0.0,
  "config_id": "mass_7bf2833bf4365b60bedb",
  "experiment_order": 19599
}
```

| Training year | Net | Cash DD | Intrabar DD | Trades | Consistency ratio |
|---|---:|---:|---:|---:|---:|
| 2020 | $830.50 | $116.00 | $193.50 | 31 | 28.30% |
| 2021 | $1,593.50 | $155.50 | $218.25 | 40 | 15.31% |
| 2022 | $64.50 | $0.50 | $93.75 | 1 | 100.00% |
| 2023 | $399.50 | $393.00 | $471.25 | 31 | 62.08% |

## Top 10 Robust Training Finalists

| # | Candidate ID | Market | Family | Net P&L | Intrabar DD | Profit Factor | Trades | Target R | Stop ATR | Trail ATR |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | `mass_7bf2833bf4365b60bedb` | MNQ | momentum | $2,888.00 | $471.25 | 2.53 | 103 | 2.0 | 3.0 | 0.0 |
| 2 | `mass_72d38b7e1c9c48d13c66` | MNQ | momentum | $2,964.00 | $438.88 | 2.47 | 103 | 3.0 | 3.0 | 2.0 |
| 3 | `mass_d1924ffa4a9fa8c4b947` | MNQ | momentum | $2,219.50 | $322.00 | 2.68 | 86 | 4.0 | 1.5 | 1.0 |
| 4 | `mass_92ec7fd1a2da8a1e4e69` | MNQ | momentum | $2,477.00 | $401.75 | 2.42 | 97 | 4.0 | 1.0 | 0.0 |
| 5 | `mass_b49390bd3c4cfb168db8` | MNQ | momentum | $8,216.50 | $920.00 | 1.79 | 230 | 2.0 | 1.0 | 0.0 |
| 6 | `mass_48e6ce6113d2a8d1cbc5` | MNQ | hybrid | $4,728.50 | $619.75 | 1.91 | 270 | 3.0 | 2.0 | 2.0 |
| 7 | `mass_33bf8e2fc3fc425f8ce2` | MNQ | breakout | $8,328.00 | $893.00 | 1.74 | 265 | 3.0 | 1.5 | 2.0 |
| 8 | `mass_02074f03022e239ffbd8` | MNQ | hybrid | $2,245.50 | $417.75 | 2.53 | 91 | 1.5 | 1.0 | 0.0 |
| 9 | `mass_fc56e640b1875576a674` | MNQ | momentum | $2,245.50 | $417.75 | 2.53 | 91 | 1.5 | 1.0 | 0.0 |
| 10 | `mass_a4c3f51975fc9bf3fdf5` | MNQ | momentum | $2,829.00 | $401.50 | 2.20 | 115 | 3.0 | 1.0 | 1.0 |

## Artifacts and limits

[All 200k ranked results](../runs/training_search_200k_v1/ranked.csv) · [Frozen 200k configuration manifest](../runs/training_search_200k_v1/configurations.jsonl) · [Protocol](../runs/training_search_200k_v1/protocol.json)

No protected period was reopened to confirm or adjust this result. Previously observed periods cannot become fresh holdouts by relabeling.
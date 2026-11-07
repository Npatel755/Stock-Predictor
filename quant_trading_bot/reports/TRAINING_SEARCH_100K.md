# 100,000 additional training configurations

**100,000 new configurations completed;170,000 distinct active configurations across the completed mass searches.** 544 met the research/post-evaluation training gates; 53 also met the50% evaluation-account consistency gate at base costs.

No validation/test prices or protected outcome records were read by this search. Generation, ranking and selection used training inputs only. The original families, parameter domains, execution logic, costs and risk limits were preserved. All prior70k active configurations were excluded; seeds20261113 through20261122 were fixed before training-price access.

## Selection policy

All markets use the same2020/2021/2022/2023 training evaluation years with separate$50,000 accounts. Net sums the four accounts; drawdown is the worst individual year, not a continuous four-year account drawdown. Every fold must have positive net, at least30 trades and no permanent risk/funded-scenario breach. Cash, closing and intrabar drawdowns must each remain strictly below$2,000. The internal hard drawdown margin remains$1,800.

The user-provided50% consistency rule applies only to the **account evaluation phase**. It remains reported on every candidate and cost scenario; it does not modify signals or executions. A chronological data split is not an account phase. Research/post-evaluation qualification omits that one phase-specific classification gate; evaluation-phase qualification additionally requires it. The user-provided phase scope is not independently verified contractual compliance.

Rank research-qualified candidates by base net profit descending, then intrabar drawdown ascending. Check in that order; select the first whose original base reproduces, independent ledger/fill checks pass and the same research gates survive doubled costs. The legacy composite score is retained as a diagnostic and does not determine this ranking.

## Training result

Selected `mass_40950c7086a169459879`: MNQ / trend.

| Metric | New base | New2x costs | Saved training benchmark |
|---|---:|---:|---:|
| Aggregate net | $13,920.50 | $6,677.50 | $9,972.50 |
| Worst annual cash DD | $1,479.00 | $1,680.50 | $1,470.00 |
| Worst annual closing DD | $1,519.00 | $1,727.50 | $1,469.00 |
| Worst annual intrabar DD | $1,593.00 | $1,765.50 | $1,478.00 |
| Trades | 1303 | 1302 | — |
| Evaluation-phase gates | True | False | — |

Higher TRAIN net than saved benchmark: **True**. Research/post-evaluation gates: **PASS**. Evaluation-account-phase status is shown separately above. Unseen performance and exact funded-account eligibility are **NOT ESTABLISHED**.

Frozen parameters:

```json
{
  "instrument": "MNQ",
  "family": "trend",
  "lookback": 16,
  "threshold": 0.75,
  "stop_atr": 1.0,
  "target_r": 1.5,
  "hold_bars": 16,
  "session_start": 585,
  "session_end": 945,
  "max_contracts": 3,
  "trailing_atr": 0.0,
  "config_id": "mass_40950c7086a169459879",
  "experiment_order": 33075
}
```

| Training year | Net | Cash DD | Intrabar DD | Trades | Consistency ratio |
|---|---:|---:|---:|---:|---:|
| 2020 | $2,261.50 | $1,430.50 | $1,510.50 | 294 | 33.94% |
| 2021 | $2,676.00 | $1,034.00 | $1,097.50 | 307 | 24.40% |
| 2022 | $5,733.50 | $1,465.50 | $1,517.50 | 339 | 16.38% |
| 2023 | $3,249.50 | $1,479.00 | $1,593.00 | 363 | 21.13% |

[Saved frozen candidate and cost stress](../runs/training_search_100k_v1/selected_training_candidate.json) · [Training curves](../runs/training_search_100k_v1/selected_training_curves.png) · [Trade logs](../runs/training_search_100k_v1/selected_training_trades.csv)


## Artifacts and limits

[All100k ranked results](../runs/training_search_100k_v1/ranked.csv) · [Frozen100k configuration manifest](../runs/training_search_100k_v1/configurations.jsonl) · [Protocol](../runs/training_search_100k_v1/protocol.json)

Distinct active parameter configurations are not independent edges. The full CSV includes failures, inactive candidates and risk locks. Retrospective training selection across many correlated trials creates substantial selection bias. No protected period was reopened to confirm or adjust this result. Previously observed periods cannot become fresh holdouts by relabeling. Fees and exact funded-account contract rules remain unresolved; no live execution is authorized.

[Dashboard](http://127.0.0.1:8511/#training-100k)

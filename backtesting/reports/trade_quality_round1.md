# Trade-quality regression filters

Ridge, XGBoost and a small two-layer neural network; two fixed expected-net thresholds each. Models and RobustScaler fit closed 2020-2022 baseline trades only. Outcomes overlapping December 25, 2022 are excluded, leaving a seven-day gap before 2023. No target clipping. Inputs are causal, price-scale-independent signal context.

**All dates are consumed research history, not a new holdout.** Six fixed candidates use the two 2023 halves for selection. The selected model/threshold are frozen before 2024-2026 diagnostics and are never refit on their outcomes. Entry filtering is fully re-simulated, including new opportunities after rejected trades, with original exits and broker costs.

Closed training trades: 209. Fitting warnings: `{'ridge': [], 'xgboost': [], 'neural_mlp': ["Stochastic Optimizer: Maximum iterations (500) reached and the optimization hasn't converged yet."]}`.

| Filter | Selection closed net at 8bp | Unfiltered baseline | Eligible |
| --- | ---: | ---: | --- |
| ridge_threshold0.0 | $1,829.65 | $1,170.35 | False |
| ridge_threshold0.25 | $373.24 | $1,170.35 | False |
| xgboost_threshold0.0 | $867.27 | $1,170.35 | False |
| xgboost_threshold0.25 | $663.40 | $1,170.35 | False |
| neural_mlp_threshold0.0 | $1,170.35 | $1,170.35 | False |
| neural_mlp_threshold0.25 | $0.00 | $1,170.35 | False |

Selected before later diagnostics: **None: no model passed the fixed selection gate**.

| Period | Strategy | Actual fill cost | Net including open marks | Closed net | Drawdown | Entries |
| --- | --- | ---: | ---: | ---: | ---: | ---: |

Shared comparisons have causal 2020-2022 indicator warm-up. Annual accounts reset; annual sums are not full-period returns. Original 2bp sizing and conservative 8bp sizing are labeled separately. A forecast is not a calibrated profit guarantee. A small neural network does not establish a deep-learning advantage on a few hundred trades.

No strategy version is promoted. Frozen baseline, external tests and prospective protocols remain intact. Additional research slots: six model/threshold pairs, beyond the 24-family experiment and earlier history.

[XGBoost Python API](https://xgboost.readthedocs.io/en/stable/python/python_api.html).

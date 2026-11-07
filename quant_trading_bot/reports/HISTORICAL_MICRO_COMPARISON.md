# Superseded micro-trained comparison record

This historical report predates the reference-transfer and final-test evaluations. Its test-status statements describe that earlier point in research. Current status is in MODEL_COMPARISON.md and reports/FINAL_REPORT.md.

# Measured MES / MNQ research

The implemented bounded campaign found **no deployable trading strategy**. This finding applies to the declared data, costs, features, model budgets and execution assumptions; it does not establish that all possible ML strategies fail.

The active source is the user-provided Databento export GLBX-20261106-FX6FM5XWUX. Training uses available micro history from May 2019 through 2023; selection uses 2024–2025; 2026 remains reserved and unevaluated. ES/NQ reference history is separately labeled. The chronological split has no overlapping timestamps and every selected bar is accounted for. See [DATA_SPLIT_REPORT.md](DATA_SPLIT_REPORT.md).

The corrected primary comparisons completed 96 candidates across MES and MNQ at declared 5- and 15-minute resolutions. The 5-minute sensitivity campaign was registered after the user freed disk space. Estimators, pruning and calibration fit training observations only. Training is capped at the latest 100000 observations per fit, so elapsed training history differs by resolution. Feature, label and holding horizons are bar-based and also scale with resolution. Costs are configurable research assumptions. Model families within each experiment share the same one-contract cap and independent risk limits. Validation blocks restart capital/risk state; the aggregate curves below are attribution curves and must not be described as one continuous funded-account record.

| Instrument | Minutes | Candidate | Validation net P&L | Max drawdown | Trades | Profit factor | Eligible |
|---|---:|---|---:|---:|---:|---:|---|
| MES | 5 | baseline_adx | $-6,912.05 | $7,009.61 | 895 | 0.462 | False |
| MES | 5 | baseline_bollinger | $-7,484.73 | $7,486.21 | 987 | 0.246 | False |
| MES | 5 | baseline_compression | $-7,972.65 | $7,972.65 | 1035 | 0.223 | False |
| MES | 5 | baseline_donchian | $-7,809.70 | $7,809.70 | 1055 | 0.286 | False |
| MES | 5 | baseline_ema | $-4,414.68 | $4,451.55 | 517 | 0.430 | False |
| MES | 5 | baseline_intraday_momentum | $-8,037.47 | $8,038.16 | 1068 | 0.517 | False |
| MES | 5 | baseline_momentum | $-6,455.60 | $6,455.60 | 890 | 0.411 | False |
| MES | 5 | baseline_multi_timeframe | $-5,546.94 | $5,564.27 | 686 | 0.450 | False |
| MES | 5 | baseline_opening_range | $-7,865.49 | $7,869.47 | 1181 | 0.576 | False |
| MES | 5 | baseline_previous_session | $-6,757.19 | $6,819.95 | 911 | 0.523 | False |
| MES | 5 | baseline_rsi | $-8,070.70 | $8,073.43 | 1080 | 0.362 | False |
| MES | 5 | baseline_sma | $-4,753.09 | $4,753.09 | 621 | 0.471 | False |
| MES | 5 | baseline_vol_momentum | $-5,934.50 | $5,934.50 | 800 | 0.388 | False |
| MES | 5 | baseline_vol_reversion | $-6,781.31 | $6,782.79 | 989 | 0.248 | False |
| MES | 5 | baseline_volume_momentum | $-6,568.57 | $6,568.57 | 908 | 0.287 | False |
| MES | 5 | baseline_vwap | $-5,199.70 | $5,202.89 | 680 | 0.385 | False |
| MES | 5 | ensemble_equal_weight | $-6,148.49 | $6,148.49 | 756 | 0.361 | False |
| MES | 5 | meta_donchian_meta | $-1,094.91 | $1,112.64 | 79 | 0.275 | False |
| MES | 5 | ml_lightgbm | $-1,841.70 | $1,844.66 | 230 | 0.077 | False |
| MES | 5 | ml_logistic | $-1,206.64 | $1,258.54 | 116 | 0.404 | False |
| MES | 5 | ml_ridge | $0.00 | $0.00 | 0 | n/a | False |
| MES | 5 | ml_tree | $-1,927.82 | $1,927.82 | 233 | 0.091 | False |
| MES | 5 | ml_xgboost | $-1,977.96 | $1,980.69 | 249 | 0.020 | False |
| MES | 5 | regime_regime_switch | $-6,496.49 | $6,497.97 | 956 | 0.439 | False |
| MES | 15 | baseline_adx | $-5,772.52 | $5,832.09 | 663 | 0.471 | False |
| MES | 15 | baseline_bollinger | $-6,681.00 | $6,681.00 | 775 | 0.376 | False |
| MES | 15 | baseline_compression | $-7,085.28 | $7,098.01 | 907 | 0.345 | False |
| MES | 15 | baseline_donchian | $-6,980.61 | $7,032.81 | 909 | 0.407 | False |
| MES | 15 | baseline_ema | $-5,742.00 | $5,771.93 | 675 | 0.485 | False |
| MES | 15 | baseline_intraday_momentum | $-7,853.40 | $7,853.40 | 835 | 0.444 | False |
| MES | 15 | baseline_momentum | $-5,739.17 | $5,743.15 | 673 | 0.431 | False |
| MES | 15 | baseline_multi_timeframe | $-5,511.62 | $5,566.09 | 703 | 0.506 | False |
| MES | 15 | baseline_opening_range | $-7,875.02 | $7,878.44 | 913 | 0.484 | False |
| MES | 15 | baseline_previous_session | $-7,523.42 | $7,582.99 | 998 | 0.537 | False |
| MES | 15 | baseline_rsi | $-7,087.30 | $7,087.30 | 870 | 0.441 | False |
| MES | 15 | baseline_sma | $-5,629.06 | $5,714.32 | 714 | 0.509 | False |
| MES | 15 | baseline_vol_momentum | $-4,840.89 | $4,841.12 | 566 | 0.421 | False |
| MES | 15 | baseline_vol_reversion | $-6,072.49 | $6,072.49 | 731 | 0.360 | False |
| MES | 15 | baseline_volume_momentum | $-7,095.43 | $7,095.43 | 817 | 0.387 | False |
| MES | 15 | baseline_vwap | $-6,722.93 | $6,722.93 | 817 | 0.454 | False |
| MES | 15 | ensemble_equal_weight | $-5,425.75 | $5,425.75 | 675 | 0.454 | False |
| MES | 15 | meta_donchian_meta | $0.00 | $0.00 | 0 | n/a | False |
| MES | 15 | ml_lightgbm | $0.00 | $0.00 | 0 | n/a | False |
| MES | 15 | ml_logistic | $0.00 | $0.00 | 0 | n/a | False |
| MES | 15 | ml_ridge | $0.00 | $0.00 | 0 | n/a | False |
| MES | 15 | ml_tree | $-226.79 | $254.75 | 26 | 0.465 | False |
| MES | 15 | ml_xgboost | $0.00 | $0.00 | 0 | n/a | False |
| MES | 15 | regime_regime_switch | $-5,479.93 | $5,479.93 | 617 | 0.438 | False |
| MNQ | 5 | baseline_adx | $-7,049.76 | $7,059.72 | 1769 | 0.452 | False |
| MNQ | 5 | baseline_bollinger | $-8,017.58 | $8,031.02 | 1402 | 0.253 | False |
| MNQ | 5 | baseline_compression | $-8,018.82 | $8,018.82 | 1383 | 0.256 | False |
| MNQ | 5 | baseline_donchian | $-8,015.94 | $8,015.94 | 1586 | 0.322 | False |
| MNQ | 5 | baseline_ema | $-7,990.82 | $7,990.82 | 1783 | 0.407 | False |
| MNQ | 5 | baseline_intraday_momentum | $-6,741.50 | $6,741.50 | 800 | 0.127 | False |
| MNQ | 5 | baseline_momentum | $-8,016.74 | $8,016.74 | 1581 | 0.344 | False |
| MNQ | 5 | baseline_multi_timeframe | $-8,020.16 | $8,020.16 | 1979 | 0.444 | False |
| MNQ | 5 | baseline_opening_range | $-7,068.56 | $7,078.52 | 914 | 0.168 | False |
| MNQ | 5 | baseline_previous_session | $-7,982.66 | $7,992.62 | 1479 | 0.330 | False |
| MNQ | 5 | baseline_rsi | $-8,011.30 | $8,022.20 | 1320 | 0.254 | False |
| MNQ | 5 | baseline_sma | $-8,034.90 | $8,034.90 | 1860 | 0.420 | False |
| MNQ | 5 | baseline_vol_momentum | $-8,020.96 | $8,020.96 | 1574 | 0.338 | False |
| MNQ | 5 | baseline_vol_reversion | $-8,001.14 | $8,011.10 | 1616 | 0.297 | False |
| MNQ | 5 | baseline_volume_momentum | $-8,055.10 | $8,055.10 | 1515 | 0.279 | False |
| MNQ | 5 | baseline_vwap | $-7,997.94 | $8,005.72 | 1561 | 0.322 | False |
| MNQ | 5 | ensemble_equal_weight | $-8,045.54 | $8,045.54 | 1626 | 0.352 | False |
| MNQ | 5 | meta_donchian_meta | $-110.40 | $110.40 | 10 | 0.000 | False |
| MNQ | 5 | ml_lightgbm | $-376.20 | $376.20 | 55 | 0.226 | False |
| MNQ | 5 | ml_logistic | $-121.44 | $121.44 | 11 | 0.000 | False |
| MNQ | 5 | ml_ridge | $0.00 | $0.00 | 0 | n/a | False |
| MNQ | 5 | ml_tree | $-601.08 | $616.68 | 102 | 0.293 | False |
| MNQ | 5 | ml_xgboost | $-182.04 | $198.72 | 26 | 0.215 | False |
| MNQ | 5 | regime_regime_switch | $-7,067.46 | $7,088.84 | 1549 | 0.389 | False |
| MNQ | 15 | baseline_adx | $-8,051.96 | $8,051.96 | 1299 | 0.269 | False |
| MNQ | 15 | baseline_bollinger | $-8,021.54 | $8,021.54 | 1026 | 0.155 | False |
| MNQ | 15 | baseline_compression | $-8,033.50 | $8,033.50 | 1175 | 0.216 | False |
| MNQ | 15 | baseline_donchian | $-8,040.36 | $8,040.36 | 1134 | 0.202 | False |
| MNQ | 15 | baseline_ema | $-8,023.52 | $8,023.52 | 1513 | 0.339 | False |
| MNQ | 15 | baseline_intraday_momentum | $-8,029.56 | $8,029.56 | 889 | 0.095 | False |
| MNQ | 15 | baseline_momentum | $-7,981.84 | $8,011.72 | 1521 | 0.339 | False |
| MNQ | 15 | baseline_multi_timeframe | $-8,005.00 | $8,024.92 | 1475 | 0.326 | False |
| MNQ | 15 | baseline_opening_range | $-8,037.24 | $8,037.24 | 881 | 0.090 | False |
| MNQ | 15 | baseline_previous_session | $-7,993.20 | $8,003.16 | 1230 | 0.249 | False |
| MNQ | 15 | baseline_rsi | $-8,046.62 | $8,046.62 | 1028 | 0.159 | False |
| MNQ | 15 | baseline_sma | $-8,009.82 | $8,015.56 | 1483 | 0.331 | False |
| MNQ | 15 | baseline_vol_momentum | $-8,003.66 | $8,023.58 | 1479 | 0.324 | False |
| MNQ | 15 | baseline_vol_reversion | $-8,045.88 | $8,045.88 | 1197 | 0.221 | False |
| MNQ | 15 | baseline_volume_momentum | $-8,030.66 | $8,039.54 | 1204 | 0.231 | False |
| MNQ | 15 | baseline_vwap | $-8,048.46 | $8,048.46 | 1199 | 0.229 | False |
| MNQ | 15 | ensemble_equal_weight | $-8,021.92 | $8,028.64 | 1448 | 0.316 | False |
| MNQ | 15 | meta_donchian_meta | $-1.08 | $11.04 | 2 | 0.902 | False |
| MNQ | 15 | ml_lightgbm | $-546.36 | $546.36 | 59 | 0.084 | False |
| MNQ | 15 | ml_logistic | $-22.08 | $22.08 | 2 | 0.000 | False |
| MNQ | 15 | ml_ridge | $0.00 | $0.00 | 0 | n/a | False |
| MNQ | 15 | ml_tree | $0.00 | $0.00 | 0 | n/a | False |
| MNQ | 15 | ml_xgboost | $-224.04 | $224.04 | 26 | 0.118 | False |
| MNQ | 15 | regime_regime_switch | $-8,023.08 | $8,023.08 | 1252 | 0.253 | False |

Flat no-trade results are abstention benchmarks, not trading edges. Negative validation outcomes are retained. A model with fewer losses because it rarely trades has not demonstrated positive expectancy. See each run's calibration, fold, regime/year attribution, bootstrap/Reality Check, cost/latency stress, funded-scenario and Monte Carlo artifacts before interpreting the ranking.

## Extended studies

Completed 53 of 53 registered extended attempts; 0 failed attempts remain visible. These exploratory studies include horizon/target alternatives, neural networks, PPO/DQN, training-only nested search and feature diagnostics, causal regime allocation, cross-market features and a shared-account replay. Their budgets and full failures are recorded in `C:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot\runs\extended_20261106T205647Z`. Short neural/RL runs test feasibility and out-of-sample behavior; they do not establish convergence or deployment readiness.

| Instrument | Study | Status | Validation net P&L | Trades |
|---|---|---|---:|---:|
| MES | return_h1 | completed | $-768.18 | 42 |
| MES | three_way_h1 | completed | $-210.60 | 15 |
| MES | return_h3 | completed | $-3,428.35 | 365 |
| MES | three_way_h3 | completed | $-94.74 | 6 |
| MES | return_h5 | completed | $-6,542.73 | 812 |
| MES | three_way_h5 | completed | $-168.36 | 9 |
| MES | return_h10 | completed | $-6,633.06 | 939 |
| MES | three_way_h10 | completed | $-635.22 | 43 |
| MES | return_h20 | completed | $-6,015.33 | 752 |
| MES | three_way_h20 | completed | $-1,016.76 | 94 |
| MES | triple_barrier_h20 | completed | $-5,613.12 | 553 |
| MES | mlp | completed | $-6,597.60 | 690 |
| MES | tcn | completed | $-7,317.71 | 774 |
| MES | lstm | completed | $-85.08 | 27 |
| MES | gru | completed | $-5,432.58 | 527 |
| MES | transformer | completed | $-5,867.06 | 664 |
| MES | inner_search_logistic | completed | n/a | n/a |
| MES | inner_search_lightgbm | completed | n/a | n/a |
| MES | inner_search_xgboost | completed | n/a | n/a |
| MES | feature_ablation | completed | n/a | n/a |
| MES | permutation_importance | completed | n/a | n/a |
| MES | cross_market_logistic | completed | $-358.83 | 27 |
| MES | regime_kmeans | completed | $0.00 | 0 |
| MES | regime_gmm | completed | $-4,829.84 | 571 |
| MES | ppo | completed | $0.00 | 0 |
| MES | dqn | completed | $-1,549.37 | 178 |
| MNQ | return_h1 | completed | $-3,618.00 | 400 |
| MNQ | three_way_h1 | completed | $-209.76 | 19 |
| MNQ | return_h3 | completed | $-8,005.06 | 1114 |
| MNQ | three_way_h3 | completed | $-232.92 | 23 |
| MNQ | return_h5 | completed | $-8,005.56 | 1314 |
| MNQ | three_way_h5 | completed | $-468.00 | 50 |
| MNQ | return_h10 | completed | $-8,002.20 | 1380 |
| MNQ | three_way_h10 | completed | $-811.32 | 83 |
| MNQ | return_h20 | completed | $-8,010.62 | 1478 |
| MNQ | three_way_h20 | completed | $-1,379.76 | 144 |
| MNQ | triple_barrier_h20 | completed | $-8,024.52 | 1463 |
| MNQ | mlp | completed | $-7,021.72 | 768 |
| MNQ | tcn | completed | $-8,040.88 | 897 |
| MNQ | lstm | completed | $-165.60 | 15 |
| MNQ | gru | completed | $-8,039.58 | 1202 |
| MNQ | transformer | completed | $-8,020.40 | 1360 |
| MNQ | inner_search_logistic | completed | n/a | n/a |
| MNQ | inner_search_lightgbm | completed | n/a | n/a |
| MNQ | inner_search_xgboost | completed | n/a | n/a |
| MNQ | feature_ablation | completed | n/a | n/a |
| MNQ | permutation_importance | completed | n/a | n/a |
| MNQ | cross_market_logistic | completed | $-781.44 | 86 |
| MNQ | regime_kmeans | completed | $0.00 | 0 |
| MNQ | regime_gmm | completed | $0.00 | 0 |
| MNQ | ppo | completed | $0.00 | 0 |
| MNQ | dqn | completed | $-8,021.14 | 1441 |
| MES+MNQ | shared_account_ema | completed | $-32.31 | 14 |

The shared-account EMA diagnostic has one balance and one risk state, gross correlated exposure reservation, no implicit price filling, and explicit timestamp exclusions. It is a continuous diagnostic and differs from the reset-fold comparison. Primary/extended choices and earlier interrupted/corrected runs all contribute selection opportunities; local per-run adjusted p-values do not correct every research decision across the whole campaign.

## Verification and limits

The current source passes its full automated suite. Actual 2025 market replay also matches batch accounting across an explicit checkpoint restart for both instruments. Replay exposed a Windows checkpoint-file sharing lock; a bounded file-replacement retry fixed it. The original frozen research and model artifacts remain unchanged. `paper_compatibility.json` verifies that this exact storage-only patch is the sole source difference and records the parent artifact and unchanged model-weight hashes; derived paper-verification artifacts carry the new source identity. That historical replay is not forward paper evidence. Physical split checks read test timestamps and hashes for integrity, not test price columns or performance.

The initial campaign was superseded after corrections to scheduled-exit timing and label completion timestamps. The final 15-minute campaign explicitly flattens at 16:30 ET, an available bar open before the published 16:45 cutoff; the generic 16:40 setting rounds late at this resolution. These execution corrections are disclosed additional research attempts, not hidden discarded results. An intermediate rerun failed on a 44.4 MiB allocation; its record is retained. Prediction batching, fold-limited inference, releasing completed curves and verified feature-cache reuse resolved the resource issue without changing split boundaries or model settings. Source snapshots and hashes distinguish these versions.

To fit the disk budget, reproducible per-bar equity curves from superseded runs were retired after logging their hashes and sizes in `reports/retired_superseded_curves.json`. Their metrics, trades, model artifacts, source snapshots and features remain; the final campaign's curves and all original market data remain available.

The provider's customization documentation confirms DLL-off removes the provider daily cap, while 50% evaluation consistency is a purchase add-on. These are the settings confirmed by the user. The independent $300 research daily stop remains a risk choice. See [official customization](https://support.lucidtrading.com/en/articles/16226050-lucidflex-customization) and [official consistency calculation](https://support.lucidtrading.com/en/articles/12945805-lucidflex-consistency-percentage).

Operational eligibility remains blocked by the missing authoritative historical session/holiday calendar, verified brokerage costs and integration permissions, complete account-contract details, and sustained authorized forward paper review. The 50% consistency cushion and purchase fee are not guessed. OHLCV cannot establish intrabar sequence, true spread, order-book depth, queue priority or future capacity. See [CME hours and holidays](https://www.cmegroup.com/trading-hours.html), [LIMITATIONS.md](LIMITATIONS.md) and [FUNDED_ACCOUNT_RULES.md](FUNDED_ACCOUNT_RULES.md).

The reserved market test was not consumed because no candidate meets the research and operational eligibility gates. Real-money execution remains disabled. No paid download, account purchase or live broker action was made.

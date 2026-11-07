# Architecture

All new code lives in this isolated directory on the pre-existing `research/codex-eth-bnb` worktree. Existing tracked files and experiments are preserved. The custom futures ledger is necessary because the existing crypto engines use fractional USDT quantity, funding, perpetual liquidation proxies, and 365-day annualization. Wilder smoothing and pivot-confirmation conventions were adapted from `backtesting/indicators.py`; the five-minute assumptions were replaced. The existing session block-bootstrap approach informed the futures version, which uses 252 sessions and integer contracts.

```text
Authorized CSV/Parquet / completed-bar JSONL
       -> canonical schema + explicit raw-price provenance
       -> quality report + exchange schedule
       -> chronological holdout exclusion
       -> causal features / purged event targets
       -> conventional strategies / calibrated fitted models
       -> desired exposure / abstention
       -> independent risk guard
       -> sequential Simulator + PaperBroker + funded state machine
       -> trade ledger / equity / experiment registry / dashboard
```

`data.py`, `contracts.py`, and `providers.py` own data availability, sessions, explicit contracts, metadata and roll selection. `features.py` computes causal indicators, session features, and exact-time cross-market features. `labels.py` defines executable-entry future returns, cost-aware directions, ambiguous triple barriers and meta-labels.

`databento_import.py` verifies and streams the user ZIP into raw contract/year partitions. `dataset_catalog.py` selects contracts from prior-session volume. `splits.py` physically separates training, validation and final test with hashes and a fixed protocol. Development descriptors list only training and validation files; final evaluation reserves access before loading test prices. Feature caches require matching dataset/timeframe, verified file content and the same batch-feature function definitions.

`strategies.py` provides 16 conventional candidates, regime switching, and abstaining ensembles. `models.py` supplies logistic regression, return ridge regression, trees, optional LightGBM/XGBoost, chronologically separated calibration and training-only correlation pruning. `optimization.py` provides bounded inner chronological grid/Optuna search and ablation helpers; the default campaign uses predeclared parameters. `advanced.py` has small MLP/TCN/LSTM/GRU/transformer constructors and training, plus a Gymnasium environment and optional PPO/DQN integration.

`research.py` manages folds, budgets, hashes, trial logs, cost/latency/missed-fill stress, session attribution, Monte Carlo, freezing, and single-use holdout reservations. `metrics.py` and `statistics.py` provide session/trade metrics and uncertainty. `risk.py` and `funded.py` are independent of prediction models. `execution.py` defines paper order matching; `backtest.py` runs the sequential state machine. `paper.py` calls these same features, signal definitions and simulator for completed-bar streaming.

`stream_features.py` retains bounded rolling history and continuing EMA/Wilder/session state with tested batch parity. `durable_paper.py` adds write-ahead inputs, an append-only sequence ledger, rotating checksummed checkpoints, explicit resume and a no-arrival watchdog. Completed orders and historical curves leave working memory after archival. `portfolio.py` coordinates synchronized MES/MNQ sleeves against a single cash balance and shared risk budget.

Artifacts are local Parquet/JSON/joblib; this registry is the lightweight alternative to an MLflow server. Runs are single-process and seeded to avoid disturbing existing research workloads. The dashboard is read-only Streamlit. The Docker definition packages this dashboard and local research CLI; it was not built on the full drive.

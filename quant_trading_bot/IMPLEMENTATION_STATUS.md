# Milestone acceptance and remaining work

Status is implementation/functional acceptance, not evidence of profitable trading. The current passing test receipt and generated reports are the executable record; earlier failed tests and runs are preserved where relevant.

| Milestone | Implemented and tested | Remaining dependency / next step |
|---|---|---|
| 1 Foundation | Isolated directory, audit, provenance manifests, UTC/schema quality, nullable quotes, explicit calendar support, completed resampling, causal rolls, dependency pins, clean Windows install, verified Databento contract history, physical train/validation/test files and access guards | Authoritative historical session schedule |
| 2 Backtester | Integer MES/MNQ ledger, next-bar orders, fees/adverse ticks, partial fills, trade-through limits, stop-limit deferral, stop-first ambiguity, unresolved-roll rejection, hard risk gates | Quote/depth/latency validation and real broker specifications |
| 3 Baselines | 16 strategy families, causal features, session variants, chronological multi-year real-data comparison and nearby-parameter stress | No qualifying validation trading edge |
| 4 ML | Logistic, ridge returns, tree, LightGBM/XGBoost training, purged calibration, training-only pruning, tested inner grid/Optuna search, complete attempt logs | Multiple real-data objectives and inner searches |
| 5 Adaptive | Rule regime, K-means/GMM helpers, abstaining equal/training-weighted ensembles, meta-label utilities, calibration/regime attribution | Sparse meta-event sample; no real OOS adaptive improvement established |
| 6 Funded simulation | Official source audit, user-confirmed 50% consistency/DLL off, EOD/static/intraday floors, floor locks, daily soft locks, consistency, payout/economics helpers, block Monte Carlo scenarios, shared-account portfolio engine | General cushion formula, purchase fee, complete account agreement and platform permission |
| 7 Advanced | Small PyTorch MLP/TCN/LSTM/GRU/transformer training tests; Gymnasium checked; optional PPO/DQN; significance/ablation helpers | No real market neural/RL advantage; no advanced deployment candidate |
| 8 Paper | Batch/online feature parity, bounded state, checksummed checkpoints and explicit recovery, input ledger, no-arrival watchdog, JSONL feed, reconciliation, permanent kill, monitoring, local read-only dashboard | Authorized external feed and sustained forward paper review |

The user-provided Databento archive replaced earlier synthetic/sample futures data. Original one-minute ES/NQ 2010–2023 training, actual micro 2024–2025 validation, later rule studies, counts and graphs are documented in `MODEL_COMPARISON.md`. One frozen MNQ candidate consumed the 2026 test: $6.50 net, $536 closing-equity drawdown, 28 trades. The nominal historical target was met, but no dependable deployable edge was established. No second tuned candidate may claim the same 2026 period as untouched test data.

No live trading or paid service has been activated. Clean Windows and Ubuntu 24.04 WSL core installations/tests are verified with separate locks; Docker and advanced Linux training remain unverified. Operational completion still depends on authoritative calendars, exact account charges and permissions, account-contract terms and forward paper review. New independent confirmation needs new forward data; the consumed final period cannot be silently recycled.

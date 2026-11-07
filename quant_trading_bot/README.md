# MES / MNQ research and paper trading

Current measured results and counts are in [the research report](MODEL_COMPARISON.md) and [interactive charts](reports/research_charts.html). One frozen MNQ candidate has now consumed the 2026 final test: **$6.50 net profit, $536 closing-equity drawdown, 28 trades**. That thin positive result does not establish a dependable trading edge. Do not reuse 2026 for tuning and call it untouched test data. New confirmation requires a new forward period. Live execution remains disabled.

This isolated Python project implements contract-level futures research without changing the existing crypto experiments. It compares conventional signals and supervised ML using the same sequential execution engine, costs, integer-contract risk limits, chronological folds, and a single-use final-test boundary. Live execution is absent.

The newest [risk/exit improvement study](reports/RISK_EXPANSION_RESEARCH.md) increases the MNQ gap-continuation candidate to two contracts and extends the scheduled exit from 11:00 to 11:30 ET. On reused 2024–2025 selection data it made **$4,451 net**, versus the reproduced **$1,635.50** baseline, with **$1,638 closing-equity drawdown** and a **$1,649 adverse-intrabar bound**. At 2× costs it made $3,274 with a $1,843 intrabar drawdown bound and no permanent shutdown. The 3×-cost case triggered shutdown and failed. Long-history and confidence checks remain unresolved; 2026 was not reused. The live dashboard places this result and its original-baseline overlay at the top.

The preceding [additional strategy batch](reports/POST_FINAL_RESEARCH.md) covers 16 new session/calendar and opening-gap/price-structure rules: 128 ES/NQ configuration screens followed by 12 selected micro replays. Its MNQ gap-continuation candidate made $1,635.50 with $871 measured drawdown in reused 2024–2025 data, but failed long-history and confidence checks. These post-final-test studies exclude 2026 and require new forward data for independent confirmation. The inventory now records 68 distinct strategy/model definitions; parameters and reruns do not increase that definition count.

## Current data

The transfer studies fit on reference **ES/NQ history from 2010 through 2023**, with internal model selection in reference 2022–2023, then evaluate actual MES/MNQ on 2024–2025. The frozen MNQ 2026 test result is now recorded separately. Reference observations from 2024 onward are excluded from fitting. Earlier micro history supplies causal feature warmup only. Volume/VWAP features are excluded from the first transfer models, and actual micro multipliers/costs apply to validation P&L. Both original one-minute and resampled 15-minute reference studies use every eligible training row without the earlier 100,000-row cap.

The **original one-minute transfer experiment** uses contract-sized feature/label shards, batched logistic training and XGBoost external memory. It retains every eligible reference row without sampling. Base fitting/calibration/inner selection stay chronological inside 2010–2023; actual micro validation and final test retain the same boundaries. The 15-minute run is a separately labeled control, not the resolution of the source archive.

```powershell
.\.venv\Scripts\python.exe scripts/run_reference_transfer.py
.\.venv\Scripts\python.exe scripts/run_minute_reference_transfer.py
```

This is a tested research hypothesis, not an assumption that a successful mini strategy transfers automatically. The earlier micro-trained 5/15-minute campaigns remain comparison records.

Interactive comparisons and data coverage: [research charts](reports/research_charts.html). The local dashboard runs on [127.0.0.1:8511](http://127.0.0.1:8511). No real-money adapter is enabled.

The active dataset is the user-provided Databento export **GLBX-20261106-FX6FM5XWUX**. Its archive hashes were verified, and 22,409,292 outright bars were imported into contract/year Parquet partitions. The prior synthetic datasets, downloaded evaluation samples, and their research runs have been removed. The original ZIP in Downloads and the separate ETH/BNB research were preserved.

`data/catalog.json` resolves `MES`, `MNQ`, `ES`, and `NQ` to development descriptors containing only their physical training and validation files. Training uses available history before January 1, 2024 UTC; validation uses 2024–2025; the separate test files cover 2026 through November 5. There is no random shuffle. MES/MNQ start in May 2019; ES/NQ start in June 2010.

Default governed research fits models, preprocessing and calibration on training data only and compares candidates on validation. The test partition is excluded from feature generation and selection, and ordinary research loading rejects it. Final evaluation requires a frozen candidate and consumes a single-use reservation. See [reports/DATA_SPLIT_REPORT.md](reports/DATA_SPLIT_REPORT.md) for exact counts and hashes. Aliases such as `MES:train` resolve individual partitions; use `MES` for the controlled research campaign.

Front contracts are chosen using the preceding completed session's volume with an expiry guard. Raw contract prices are retained; prices and quotes are never forward-filled or invented. ES/NQ remain distinct mini contracts, not pre-2019 micro observations.

```powershell
.\.venv\Scripts\python.exe -m quant_futures datasets
.\.venv\Scripts\python.exe -m quant_futures baseline MES --config configs/mes_market.yaml --output runs/mes_baselines_real
.\.venv\Scripts\python.exe -m quant_futures research MNQ --config configs/mnq_market.yaml --output runs/mnq_research_real
```

These commands reproduce the earlier 15-minute comparison settings. Source one-minute history remains preserved. Data import does not establish profitability. Review [reports/DATA_IMPORT_REPORT.md](reports/DATA_IMPORT_REPORT.md), the fixed split protocol and [MODEL_COMPARISON.md](MODEL_COMPARISON.md) before research. The frozen MNQ final-test result is recorded separately, and that market period is consumed.

**No deployable candidate has been established.** Earlier synthetic runs demonstrated software behavior only and have been superseded by the Databento data. See [MODEL_COMPARISON.md](MODEL_COMPARISON.md), [DATA_SOURCES.md](DATA_SOURCES.md), and [LIMITATIONS.md](LIMITATIONS.md).

## Installation

Run these commands from `quant_trading_bot`. The lock and clean installation were verified with Windows Python 3.13.5; core/research tests were also verified in Ubuntu 24.04 WSL with Python 3.12.3. The Windows closure is in `requirements.lock` and the independently resolved Linux closure is in `requirements-wsl.lock`. Docker execution and neural/RL training under Linux remain unverified.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
```

In WSL/Linux replace `.\.venv\Scripts\python.exe` with `.venv/bin/python` and use `requirements-wsl.lock`. The initial development environment reused installed packages via `--system-site-packages` to conserve disk. A separate `.clean-check` environment was installed from the lock without global packages and passed acceptance tests and `pip check`. XGBoost, LightGBM, Optuna, DuckDB and Plotly are included in both tested core locks. `requirements-advanced.lock` pins the installed PyTorch/PPO/DQN closure; advanced training tests ran in the Windows development environment.

The original Windows catalog stores absolute Windows paths. `scripts/prepare_wsl_catalog.py`, run inside WSL, writes separate native-path descriptors under `data/manifests/wsl/` without modifying data or the Windows catalog. Use those explicit descriptor paths in Linux CLI work, or import data in a separate Linux checkout. Filesystem-path portability is separate from the verified model/accounting tests.

## Functional smoke run

Use new output names for each run; existing dataset and experiment versions are never overwritten.

```powershell
.\.venv\Scripts\python.exe -m quant_futures doctor --output reports/environment.json
.\.venv\Scripts\python.exe -m quant_futures selftest --receipt reports/test_receipt.json
.\.venv\Scripts\python.exe -m quant_futures fixture --instrument MES --output data/processed/demo_mes.parquet
.\.venv\Scripts\python.exe -m quant_futures research data/processed/demo_mes.parquet --output runs/demo_mes
.\.venv\Scripts\python.exe -m quant_futures paper-replay data/processed/demo_mes.parquet --artifact runs/demo_mes/candidate.joblib --output runs/demo_paper
.\.venv\Scripts\python.exe -m streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8511
```

The dashboard labels synthetic results. Model files are Python/joblib artifacts: load only files produced locally by this project. Passing current-source tests are required before paper execution. Historical paper replay is distinct from streaming paper operation.

## Data and research commands

Import canonical CSV or Parquet with `timestamp_utc,instrument,contract,open,high,low,close,volume`. Explicit quarterly contract examples are `MESZ26` and `MNQZ26`. Keep raw traded prices; do not relabel adjusted continuous prices with an inferred contract. Optional bid/ask fields stay null unless supplied.

```powershell
.\.venv\Scripts\python.exe -m quant_futures import vendor.csv data/processed/mes_v1.parquet --provider "licensed export" --license-note "private research; record actual entitlement" --price-basis raw
.\.venv\Scripts\python.exe -m quant_futures validate data/processed/mes_v1.parquet --output reports/mes_quality.json
.\.venv\Scripts\python.exe -m quant_futures features data/processed/mes_v1.parquet --output data/processed/mes_features_v1.parquet
.\.venv\Scripts\python.exe -m quant_futures baseline data/processed/mes_v1.parquet --output runs/mes_baselines
.\.venv\Scripts\python.exe -m quant_futures train data/processed/mes_v1.parquet --output runs/mes_models
.\.venv\Scripts\python.exe -m quant_futures walk-forward data/processed/mes_v1.parquet --output runs/mes_walk_forward
.\.venv\Scripts\python.exe -m quant_futures stress data/processed/mes_v1.parquet --output runs/mes_stress
```

`train`, `walk-forward`, and `stress` run the same integrated controlled pipeline, including the baseline comparison and cost stress; `baseline` excludes ML. Features exclude the reserved test partition for the active catalog, or the configured final fraction for standalone fixture imports. A naive vendor timestamp requires `--source-timezone America/New_York`; UTC offsets are otherwise mandatory. Schedule validation uses `--schedule official_sessions.csv`, containing `session_id,open_utc,close_utc`. Set `calendar_schedule` in research YAML to use the same verified schedule throughout research; operational eligibility remains false.

```powershell
.\.venv\Scripts\python.exe -m quant_futures resample data/processed/mes_v1.parquet --minutes 5 --output data/processed/mes_5m_v1.parquet
.\.venv\Scripts\python.exe -m quant_futures estimate-data-cost --symbols MESZ26 MNQZ26 --start 2026-10-01 --end 2026-11-01
```

Resampling supports 1, 2, 5, 15, 30, 60, and 1440 minutes. Daily bars require an explicit exchange schedule. Set matching `timeframe_minutes` in config. The cost endpoint requires `DATABENTO_API_KEY` and requests free metadata only; it never submits a paid download.

## Final test and paper streaming

After selection is frozen and the protocol is reviewed, the following command consumes the final test once. Its exclusive manifest is outside the run directory. Failed attempts also consume the reservation. Do not change the governance directory or delete reservations to repeat a final test.

```powershell
.\.venv\Scripts\python.exe -m quant_futures holdout data/processed/mes_v1.parquet --frozen runs/mes_models --governance data/manifests/final_tests
.\.venv\Scripts\python.exe -m quant_futures paper-stream - --artifact runs/mes_models/candidate.joblib --output runs/stream_paper
```

Streaming reads completed canonical bars as JSONL from stdin, or a named JSONL spool. An authorized external provider must supply the feed. EOF cancels outstanding paper orders and preserves any open simulated position; it does not fabricate a shutdown price. No credentialed live feed or real-money broker adapter is shipped.

See [ARCHITECTURE.md](ARCHITECTURE.md), [RESEARCH_METHODOLOGY.md](RESEARCH_METHODOLOGY.md), [BACKTEST_ASSUMPTIONS.md](BACKTEST_ASSUMPTIONS.md), [RISK_MANAGEMENT.md](RISK_MANAGEMENT.md), [FUNDED_ACCOUNT_RULES.md](FUNDED_ACCOUNT_RULES.md), [PAPER_TRADING.md](PAPER_TRADING.md), and [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for scope, assumptions, verification and remaining prerequisites.

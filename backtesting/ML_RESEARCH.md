# ETHUSD research branch

This branch adds an isolated five-minute ETHUSD training pipeline for the user's Breakout 90/10 account research. It does not place orders or change the stock database or stock predictor artifact.

The user's confirmed instrument is **ETHUSD on Breakout**. The reference screenshot uses five-minute Binance ETHUSDT perpetuals. The primary experiment trains **exclusively on Binance ETHUSDT perpetual futures candles**, from Binance's official public archive, with SHA-256 verification against the published checksums. A separate experiment uses the configured Massive API's `X:ETHUSD` consolidated crypto trades as an ETH/USD spot-proxy comparison. The sources are never mixed. No stock, MES, MET, or other coin rows enter either experiment. Neither feed reproduces Breakout execution prices; validating a funded strategy requires the actual execution/feed history.

## Run on Windows

Run these commands from the repository root. All data, artifacts and reports named below are now inside `backtesting/`.

```powershell
python -m venv .ethvenv
.ethvenv/Scripts/python.exe -m pip install -r backtesting/requirements-ml.txt
.ethvenv/Scripts/python.exe -m backtesting.eth_research.data --start 2024-11-03 --end 2026-11-02
.ethvenv/Scripts/python.exe -m backtesting.eth_research.perpetual_data --start 2024-11-03 --end 2026-11-02
.ethvenv/Scripts/python.exe -m unittest discover -s backtesting/tests -v
.ethvenv/Scripts/python.exe -m backtesting.eth_research.train
.ethvenv/Scripts/python.exe -m backtesting.eth_research.predict

# Independent comparison using your Massive key; not a futures dataset.
.ethvenv/Scripts/python.exe -m backtesting.eth_research.train --market massive_spot_proxy --bars backtesting/data/ethusd/bars.csv --output backtesting/artifacts/ethusd/massive_proxy --publish-report backtesting/reports/ethusd_massive_proxy_comparison.md
```

The configured `MASSIVE_API_KEY` is read from the existing `.env`; `POLYGON_API_KEY` is a fallback. No new secret is required. Downloads are read-only, paginate, throttle to five requests per minute, retry temporary errors, and resume cached 28-day chunks. Dates are UTC, end exclusive. Only finished five-minute bars are accepted. Cached raw data and model binaries are Git-ignored.

The Binance perpetual downloader uses public read-only ZIP archives without account credentials, preferring full monthly archives and falling back to daily archives. It verifies each archive's published checksum and reads CSVs in memory without extracting ZIP paths. `--market` enforces a single source/ticker and rejects attempts to mix the Massive and perpetual datasets.

Downloaders replace completed CSVs atomically. Training reads one byte snapshot, saves `dataset_snapshot.csv` in its output directory, and hashes those same bytes. The initial Massive experiment ran while a resumed downloader serialized its final CSV; `artifacts/ethusd/massive_proxy/dataset_replay_audit.json` records the original checksum and the completed file's checksum. Every held-out label and all selected-model probabilities were verified against the completed file (maximum probability difference below 1e-15). That historical run's original checksum is retained; the completed file is preserved as its verified replay snapshot.

This session's `.ethvenv` was created with `--system-site-packages` to reuse the installed PyTorch CPU runtime; XGBoost was installed in the local environment. `artifacts/ethusd/run_metadata.json` records actual library versions.

## What is compared

Majority baseline; two logistic regression regularizations; random forest; extra trees; two histogram boosting configurations; two XGBoost configurations; two dense neural networks; two LSTMs; and a one-dimensional convolutional network. This is 14 candidates including the baseline, with three expanding-window validation folds and one final 20% chronological holdout.

The target is whether the **next five-minute bar closes above its open**. Signals use only information available at the current bar close; hypothetical entry is the next bar open and exit is the next bar close. Flat candles count as non-UP. Two observations are purged at split boundaries. Scalers are fitted on training history, and neural early stopping uses a chronological inner tail, never the outer validation or final holdout. All candidates use identical eligible timestamps; rolling features and neural windows reset at gaps. The final unlabeled bar remains available for inference.

The learned candidate with the highest mean validation accuracy is frozen before evaluating the holdout. A separate confidence threshold is chosen using development out-of-fold returns, with a no-trade option. Final holdout scores for all candidates are reported as diagnostics; they do not change the selected model. A paired day-block bootstrap compares the selected candidate to the majority baseline while retaining intraday dependence. There is no guarantee that this bounded search finds the best possible model.

## Account assumptions

The 90/10 split means the trader keeps 90% of positive simulated net profits. It does **not** determine the training/test split. Costs default to 4 basis points per side, plus an assumed 2 basis points slippage per side. The simulation assumes Terminal financing of 3.3 basis points/day charged at four-hour snapshots, with conservative treatment of positions exiting exactly on a snapshot. Spread, latency, fills and actual funding rates are not observed.

Each isolated five-minute trade uses 10% of initial capital, capped to current equity, without leverage. Adjacent signals close and reopen, so both sides are charged on every trade. Returns and illustrative profit share are fractions of initial capital; account size has not been supplied. Reported intrabar drawdown uses each bar's adverse extreme. Without tick-level ordering this is an estimate; it does not certify compliance. An intrabar loss-limit breach is recorded and stops subsequent trading; the first bar's closing P&L is still an estimate, not a simulated forced-liquidation fill.

The specific plan and balance remain unknown, so daily/total rule checks default to unset. Once the actual limits are known they can be supplied explicitly:

```powershell
# Replace fractions with the limits in your actual agreement.
.ethvenv/Scripts/python.exe -m backtesting.eth_research.train --daily-loss-limit 0.03 --total-loss-limit 0.06
```

The simulation uses a 00:30 UTC daily reset and a static total-equity floor; it does not implement Spark trailing rules, payouts during the run, or other plan-specific terms. It cannot certify a funded account. If changing assumptions or models after viewing this report, obtain a new untouched test period before drawing conclusions.

## Outputs

- `reports/ethusd_model_comparison.md`: small, reviewable results report.
- `artifacts/ethusd/selected_model.joblib`: selected model, fitted scaler, feature schema, policy, and metadata. Trained on development data only so its holdout score remains reproducible. Load only trusted artifacts.
- `artifacts/ethusd/cv_results.json`, `holdout_results.json`, `selection.json`, `summary.json`: full metrics and frozen decisions.
- `artifacts/ethusd/dataset_snapshot.csv`: exact input snapshot for future runs; the initial Massive run has a verified replay snapshot as explained above.
- `artifacts/ethusd/holdout_predictions.csv`, `holdout_trades.csv`: audit data.
- `data/ethusd/bars.metadata.json`: source, range, bar count, gaps, and SHA-256.
- `data/ethusd/perpetual/bars.metadata.json`: equivalent provenance plus checksum-verified archive manifest for the futures experiment.
- `reports/ethusd_massive_proxy_comparison.md` and `artifacts/ethusd/massive_proxy/`: independent Massive comparison and its model/metrics.

`predict` uses completed cached bars and reports their timestamp. Data older than ten minutes returns `WAIT_STALE_DATA`; a no-trade selected policy returns `WAIT` on current data. There is no exchange connection, trading bot, or order submission. Inference on old development rows is not an out-of-sample backtest.

Published sources checked November 2, 2026: [Massive crypto aggregates](https://massive.com/docs/rest/crypto/aggregates/custom-bars), [Binance public futures data](https://github.com/binance/binance-public-data), [Breakout symbols](https://www.breakoutprop.com/symbols/), [funded fees](https://intercom.help/breakoutprop/en/articles/11647195-what-are-the-trading-fees-and-commissions-in-a-funded-account), and [funded agreement](https://www.breakoutprop.com/funded-trader-agreement/).

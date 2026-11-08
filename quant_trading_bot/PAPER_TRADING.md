# Paper operation

Run `python -m quant_futures selftest` with this project's interpreter before enabling paper operation. It creates a dated receipt with the tested source hash. Artifacts must match the current source hash and feature implementation. Source edits invalidate earlier receipts and artifacts. No real-money adapter is implemented, and no flag can enable live execution.

Historical paper replay and backtests use exactly the same feature builder, candidate signal code, configuration and `Simulator`. The integration test compares complete equity frames, not only total P&L. Replay may perform an explicitly labeled terminal accounting liquidation. Streaming receives completed-bar JSONL through a provider-neutral adapter; an authorized feed must produce timestamps, raw contract identifiers and OHLCV. It rejects unfinished, stale, duplicate, out-of-order and malformed bars.

```powershell
.\.venv\Scripts\python.exe -m quant_futures selftest
.\.venv\Scripts\python.exe -m quant_futures paper-replay data/processed/demo_mes.parquet --artifact runs/demo_mes/candidate.joblib --output runs/demo_paper
.\.venv\Scripts\python.exe -m quant_futures paper-stream - --artifact runs/demo_mes/candidate.joblib --output runs/live_feed_paper
.\.venv\Scripts\python.exe -m streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8511
```

The paper output includes `monitor.jsonl`, atomically replaced `state.json` snapshots, orders/fills, risk status, signal probability, inference/data age, position, equity, cash and unrealized P&L. `shutdown.json` records why a session ended and whether simulated positions remain. All fills, positions and P&L are simulated.

Disconnects cancel pending paper orders. `reconnect` reconciles expected broker positions and refuses a critical kill switch. Feed recovery is explicit; it is not an automatic live restart. There is no real provider-specific streaming client in this version, and EOF is a shutdown event. Online features retain 200 bars plus EMA/Wilder/session state; batch/online equality is tested across sessions, contract changes and the bounded window.

`paper-stream` uses `DurablePaperSession`: each completed input is written ahead, its accounting is appended to `ledger.jsonl`, and one of two rotating checkpoints is committed with a checksum. Closed orders, fills and equity history are archived in the ledger while working memory is compacted. Use `durable_paper.read_ledger()` to deduplicate recovered sequence IDs. Monitoring lines can repeat after a crash; they are not the accounting authority. Checkpoints use pickle/joblib and must be trusted local files. A no-arrival watchdog halts and cancels orders when a blocked feed exceeds one configured bar interval plus the allowed data age.

Explicitly resume the same paper session after a clean interruption with `paper-stream ... --output runs/live_feed_paper --resume`. The model identity, source version and current test receipt must match. A consumed write-ahead input is not traded twice; a not-yet-committed input is recovered. Checksum failures, critical kills and model changes require investigation and a new reviewed session. This protects local process recovery; it does not guarantee disk survival or replace broker-side protection and supervision.

The comparison helper reports equity and trade-count differences; feature drift reports standardized mean shifts against eligible training features. These are monitoring diagnostics, not automatic approval to retrain or increase leverage. Future paper review needs real authorized quotes, fills, disconnections, session closes, rolled contracts, broker fees and enough forward observations to assess drift and execution degradation.

Before any live implementation: confirm purchased account rules and API/platform permissions; supply licensed raw contract history and an authoritative calendar; complete untouched final-test and dependence-aware statistical review; review extended real-feed paper results; implement exchange-side protection and reconciliation; establish explicit user authorization for live activation. None of those prerequisites is implied by a passing functional test.

## Automatic ensemble paper testing (`quant_futures.ensemble_paper`)

`python -m quant_futures.ensemble_paper run --root runs/paper_ensembles` paper-tests the three frozen
ensemble candidates selected on 2026-11-06 without any order routing:

| key | version | sleeves (max contracts) | reproduced train / validation / 2026 test |
|---|---|---|---|
| `portfolio_e` | 1.0.0 | MES_MOM_3c + MNQ_BRK_E_2c (5 micros) | +19,095.50 (DD 1,395.25) / +3,142.25 (1,744.25) / +6,562.25 (964.75) |
| `ensemble_epsilon` | 1.0.0 | MES_MOM_1c + MNQ_VOL_1c + MNQ_E57_1c (3 micros) | +14,241.00 (2,186.00) / +4,052.75 (1,724.75) / +4,723.50 (483.50) |
| `ensemble_beta` | 1.0.0 | MES_MOM_2c + MNQ_BRK_E_1c + MNQ_HYB_C_1c (4 micros) | +12,817.25 (1,080.75) / +787.00 (1,343.62) / +3,182.25 (908.38) |

The sleeve parameters are those of `scripts/evaluate_multi_strategy_ensembles.py` (Epsilon uses the one-contract
MES sleeve that reproduces the user's selection screenshot, not the script's two-contract version). All three were
chosen after their 2026 test results were observed, so 2026 is consumed and this forward paper record is the only
fresh evidence about them.

How it works:

- Each run fetches public 1-minute `MES=F`/`MNQ=F` history (Yahoo, delayed continuous front month) and appends
  completed minutes to an append-only store (`<root>/bars/<SYM>_1m.csv`; the first observation of a minute wins and
  later differences are logged to `<SYM>_revisions.jsonl`). 15-minute bars are rebuilt from the store with the same
  all-15-minutes rule as the research DuckDB query. On 2026-11-02..05 this proxy matched the Databento series to
  within a tick on highs/lows and produced identical trade sets (prices within one tick) for all ten sleeve runs.
- The exact research engine (`scripts/mass_research.py`, `mass_execution.py`, `mass_features.py`,
  `training_5m_v2_policy.execution_cfg_5m_v2`: $0.50/side, 1 tick slippage, 1 tick spread, $150/contract risk,
  $400/contract daily loss, $2,000 hard drawdown, $50k start) is re-run from the paper start over the whole stored
  history on every run. Newly closed trades are appended to `<root>/<candidate>/ledger.jsonl` with sequence numbers;
  previously ledgered trades are re-derived and any difference is appended as a `divergence` record rather than
  rewritten. `status.json`, `equity.csv` and `<root>/dashboard.json` are rebuilt each run and the paper server shows
  them at `/futures`.
- Deployment: `deploy/futures-paper.service` + `deploy/futures-paper.timer` (every 15 minutes, Mon-Sat) on the paper
  droplet under `/opt/futures-paper`; the paper start date is pinned in `<root>/start.txt`.

Limitations: the bar source is a delayed public proxy, not licensed exchange data; roll handling of the continuous
symbol is undisclosed (the engine sees a single contract label); fills are simulated at the research cost model;
nothing here measures real broker fills, funded-account rule enforcement or platform latency.

### TradingView overlay (`pine/mass_sleeve_15m_v1_0_1.pine`)

A single Pine v5 strategy with a preset dropdown for the eight sleeve variants (MES_MOM_3c/2c/1c, MNQ_BRK_E_2c/1c,
MNQ_VOL_1c, MNQ_HYB_C_1c, MNQ_E57_1c). It mirrors the engine's bar semantics (15-minute completed-close signal, next-open
entry, ceil-to-tick ATR stop, target = stop x R, prior-close trail, hold-bar and 15:55 ET flat exits, $150-per-contract
sizing) but it is a **non-authoritative overlay**: EMAs are not reset at the 17:00-18:00 ET break, targets fill on touch,
slippage is TradingView's integer tick setting, and the daily-loss / five-loss locks are approximations. Its alert
messages carry a JSON payload (`strategy`, `ticker`, `action`, `contracts`, `stop_distance`, `target_r`) so a future
webhook bridge can consume them; no bridge or live routing exists in this version. Compare its Strategy Tester trades
with `runs/paper_ensembles/<candidate>/ledger.jsonl` before trusting any number it shows.

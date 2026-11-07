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

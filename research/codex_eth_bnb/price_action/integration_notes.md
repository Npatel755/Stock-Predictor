# Handoff: price-action and session-mechanics round

All work is under the dedicated `research/codex-eth-bnb` worktree. Devin's checkout and earlier frozen source files are not modified. This round imports the already-tested formation execution adapter and weekly activity calculator unchanged.

```powershell
& '../Stock Predictor/.ethvenv/Scripts/python.exe' -m pytest research/codex_eth_bnb/tests research/codex_eth_bnb/formations/tests research/codex_eth_bnb/price_action/tests -q -p no:cacheprovider
& '../Stock Predictor/.ethvenv/Scripts/python.exe' -m research.codex_eth_bnb.price_action.run
```

The runner first verifies the frozen source/dependency/plan/data identities. Existing replay keys load cached artifacts; new records append to the registry. The selected rules, costs and acceptance gates are frozen before validation. No failed validation rule is replaced.

Inputs: completed UTC OHLCV candles with causal ATR and UTC-day session VWAP, plus the pinned signed settlement history for execution. `signals.detect(frame)` returns the eight raw setup types, reference close, structural stop, origin and confirmation availability. `signals.signalize(frame,spec,events)` applies the fixed1.5R/3R target, next-open desired-position output and expiration. `setup_id` prevents repeated successful entries after a stop. No order or API call is emitted.

The correction in `protocol_correction.md` is important provenance. The initial implementation could re-arm an expired opening fade while price stayed outside its fixed session range. The corrected implementation requires a new crossing. Original54replays/18variants and manifest remain available; registry code hashes identify them, and combined calendar/weekly/cost exports mark `implementation_status=superseded`. They do not contribute to the current strategy scoreboard or shortlist. The cumulative280-slot plan was conservatively increased to298slots to count those preliminary variants. No validation was accessed by the old implementation.

Read `manifest.json`, `training_results.json`, `strategy_comparison.csv`, `validation_shortlist.json`, `validation_scoreboard.csv`, `robustness_report.md`, `accounting_audit.json`, and `diagnostic_configurations.json`. Per-trial outputs include trade/equity Parquet, daily return CSV, weekly activity including zeros, and monthly/quarterly/regime attribution. Artifacts under `outputs/` remain locally cached and git-ignored; their exact identity is recorded in the registry/manifests.

The final historical20% is contaminated and performance access remains blocked. The existing prospective windows are sealed; no prospective result, paper service, Pine port, production integration or live routing is added. Rejected or merely infrequent diagnostics are not deployable strategies. Fixed fee/depth/precision/mark-price limitations remain as described in the parent research documents.

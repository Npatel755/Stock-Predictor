# Formation research integration notes

This directory is a separate experiment under `research/codex-eth-bnb`. It does not change the prior frozen core, Devin's strategy files, TradingView alerts, paper services, account settings or live execution.

From the dedicated worktree:

```powershell
& '../Stock Predictor/.ethvenv/Scripts/python.exe' -m pytest research/codex_eth_bnb/tests research/codex_eth_bnb/formations/tests -q -p no:cacheprovider
& '../Stock Predictor/.ethvenv/Scripts/python.exe' -m research.codex_eth_bnb.formations.run
```

The second command checks `manifest.json` against the exact source, dependency, plan, data and split hashes before loading cached results or simulating. A changed implementation requires a new experiment identity. It never evaluates the contaminated nominal final period. All source clean/funding snapshots are inherited read-only from the isolated parent data directory; raw historical inputs remain identified by their pinned manifests.

Interfaces:

- `patterns.library()` declares the 36 primary specifications and six baselines per asset before outcomes.
- `patterns.detect(frame, sensitivity)` returns geometric breakout events and raw confirmed pivots. The frame needs completed OHLCV, causal ATR, UTC bar-open timestamps and `attrs['timeframe']`. Geometric pivot index and confirmation index are separate fields. Raw pivots are not trade signals.
- `patterns.signalize(frame, specification, events)` produces desired direction, immutable setup identifier and structural bracket prices at completed bar close.
- `formations.execution.simulate(frame, config)` consumes that information at the next open. It adds one-successful-entry-per-formation and previous-signal structural brackets to a local copy of the original vetted execution code. Without these fields, fill/ledger parity is tested against the parent engine. The parent engine file remains unchanged.
- `activity.weekly_activity(result)` counts distinct successful entry timestamps across the entire period and complete UTC Monday-Sunday weeks. Partial exit legs do not add entries; inactive weeks count as zero.

The frequency objective is a measured research gate, not an instruction to force trades: >=2/week on average and >=50% complete weeks with at least two entries in each development fold and validation. A genuine setup can still be skipped because the account holds another position, the price gaps past a bracket, volume caps bind or minimum order size is not met. Pattern-mix opposite-direction conflicts do not open a position.

Numeric shoulder/pivot/triangle/flag thresholds are exact test definitions rather than a subjective visual classification. Retrospective charts label the first validation H&S occurrence regardless of its later profit. Orange hollow markers show when pivots became available; trading at the earlier pivot would introduce lookahead.

Read `report.md`, `strategy_comparison.csv`, `validation_scoreboard.csv`, `robustness_report.md`, `accounting_audit.json` and `diagnostic_configurations.json` before considering any reuse. Rejected diagnostics are not approved paper/live configurations. No Pine port, webhook, account routing or production integration is performed by this experiment.

After the frozen runner, run python -m research.codex_eth_bnb.formations.tools.finish to regenerate the artifact-only chart margins, explicit cost attribution and verification manifest. It verifies unchanged frozen research code and does not alter signals, fills or selection.

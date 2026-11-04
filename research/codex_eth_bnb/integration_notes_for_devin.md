# Integration notes for Devin

Everything authored for this task is under research/codex_eth_bnb in branch research/codex-eth-bnb. Original checkout remains outside the write boundary. No production integration is performed.

Interfaces: data_pipeline.snapshot/funding/load/resample; strategies.library/build_features/build_signal; execution.simulate(frame,config)->metrics/trades/equity; analytics; runner.Lab; paper.emit_paper_signal. OHLCV timestamps denote UTC candle open. Signal information exists only at candle close; execution consumes previous signal.

Reproduction from the dedicated worktree:

```powershell
& '../Stock Predictor/.ethvenv/Scripts/python.exe' -m pytest research/codex_eth_bnb/tests -q -p no:cacheprovider
& '../Stock Predictor/.ethvenv/Scripts/python.exe' -m research.codex_eth_bnb.data_pipeline --funding
& '../Stock Predictor/.ethvenv/Scripts/python.exe' -m research.codex_eth_bnb.tools.reproduce
```

Read research_plan.md, candidate_manifest.json, split_manifest.json and code_freeze.json before reproducing. The registry append-only replay key includes config/code/data identity. Repeated identical trials load saved artifacts; frozen manifests reject changes. data/ and outputs/ are git-ignored local artifacts; persist them with checksum manifests when handing off. Source raw archive paths point to the original machine and must be supplied read-only on another machine.

Paper interface is local-file only: `python -m research.codex_eth_bnb.paper --config CONFIG.json --bars CANDLES.parquet --asof UTC_TIMESTAMP --output stdout`. It emits desired exposure, not orders. Context input can supply local BTC/peer files. A valid frozen candidate envelope and unchanged code/data manifests are required; no candidate exists if gates fail. Never promote an illustrative/rejected configuration.

No API keys, live execution, production imports, unattended jobs or deployment are added. Any future integration requires explicit review and authorization.

## Post-run accounting

Run `python -m research.codex_eth_bnb.tools.audit_outputs` and `python -m research.codex_eth_bnb.tools.finalize` after the frozen runner. These produce calendar-consistent volatility/Sortino, check every ledger, and export charts/rejected diagnostics. They do not revise signals, ranks, shortlist or acceptance gates. Their own source hashes are recorded separately.

The reproduction wrapper preserves the original execution revision from code_freeze.json after later commits add result artifacts. It first verifies byte-identical frozen core code and manifests; it does not revise or reselect any strategy. Use python -m research.codex_eth_bnb.tools.reproduce --verify-only for the read-only identity check. The original runner entrypoint is intended for the initial execution commit and deliberately refuses a changed freeze record.

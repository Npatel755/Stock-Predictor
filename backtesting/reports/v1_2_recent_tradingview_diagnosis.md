# v1.2 recent TradingView result diagnosis

The supplied TradingView screenshot shows **-$189.50** for October 11 through November 3, 2026. The latest screenshot's strategy properties and individual trades are not exported, so a matching total cannot certify parity.

The complete local comparison uses October 11 through October 27 inclusive (UTC). October 28 and November 2 candles remain missing locally. Results below do not claim coverage of those missing days or the entire screenshot range.

| Replay | Closed trades | Net P&L |
| --- | ---: | ---: |
| Original v1.1, original execution | 2 | +$370.79 |
| Saved v1.2, Python research costs | 2 | -$200.68 |
| Saved v1.2, Pine-style execution diagnostic | 2 | -$189.66 |
| Latest TradingView screenshot, longer displayed range | Trade count not visible | -$189.50 |

## What changed

Both local versions trade the same two short setups. Original v1.1 uses 2R targets and a 0.1 ATR stop buffer. Both trades reach its closer target. v1.2 uses 4.5R targets and a 0.4 ATR stop buffer. Both trades reverse into their stops before reaching its farther targets. v1.2 also sizes including estimated costs and requires at least 10bp ATR.

| v1.2 entry (UTC) | Initial stop | Target | Exit bar open (UTC) | Research net P&L | Pine-style diagnostic net P&L |
| --- | ---: | ---: | --- | ---: | ---: |
| 2026-10-15 13:00 | 2361.581801 | 2291.171897 | 2026-10-15 14:05 | -$100.04 | -$94.03 |
| 2026-10-18 16:20 | 2385.892720 | 2283.082759 | 2026-10-18 22:00 | -$100.64 | -$95.64 |

Intrabar exit timestamps are bar bounds, not exact trade timestamps. No positions remain open at the local comparison endpoint.

## Execution isolation

The diagnostic retains the saved v1.2 signals, next-open entries, 0.001-unit Python quantity truncation, and 2bp cost estimate for sizing. A temporary Broker subclass applies only two ticks of market/stop fill slippage. Financing is disabled and the intrabar policy is changed to the TradingView OHLC approximation. The subclass is injected only inside an isolated `unittest.mock.patch.object` context; the research engine, saved config and Pine export are unchanged.

Removing extra actual fill slippage and financing moves -$200.68 to -$189.66, close to the screenshot. The remaining $0.16 is unexplained without the actual TradingView trade export. Quantity precision, tick rounding, source prices and chart settings are candidates, not confirmed causes. A separate hypothetical 0.01-unit quantity truncation gives -$189.49; that exchange quantity step has not been established from the screenshot.

Both cold initialization on October 11 and indicators warmed from August 1 produce the same local v1.2 trades and net result. The original v1.1's local +$370.79 also approximately reproduces the earlier v1.1 screenshot's +$370.45.

The previously reported v1.2 +$4,344.93 covers January 2023 through October 27, 2026 under research execution assumptions. It is not an expected profit for every subperiod. No strategy parameters were changed to make this short window profitable. Full trade-by-trade and signal reconciliation remain unverified.

Local diagnostic ledgers: `backtesting/artifacts/dvs/tradingview_mismatch/`, with subdirectories `v12_research_warm`, `v12_research_cold`, `v11_original_warm`, and `v12_pine_execution`.

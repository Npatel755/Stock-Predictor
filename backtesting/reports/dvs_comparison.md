# DVS ETH initial backtest results

Run date: November 2, 2026 (New York). Source: supplied **DVS ETH v1**, not an independently supplied v1.1. TradingView parity remains **unverified**.

| Run | Available candle period (UTC, end exclusive) | Entries | Net return | Final equity | Modeled intrabar drawdown |
| --- | --- | ---: | ---: | ---: | ---: |
| Mode A: parity candidate | 2023-01-01 → 2026-10-28 | 198 | −5.90% | $47,051.95 | 6.69% |
| Mode B: research / Breakout cost scenario | 2023-01-01 → 2026-11-02 | 198 | −7.21% | $46,397.12 | 7.97% |

Both runs start at $50,000. These configurations and date ranges differ; this is not a controlled one-variable comparison. The Mode A run ends before the missing October 28 data. Mode B segments around the gap and includes the available tail. No trades occurred in that tail after the indicator reset. Neither run established profitability.

Mode A follows the source's 0.05% commission per side, two instrument ticks of slippage, process-on-close entries and OHLC-path ordering. Mode B uses the separately recorded research configuration: 0.04% per side, two ticks plus two basis points of assumed slippage, next-open entries, stop-first ambiguous bars, and assumed 3.3bp/day financing at four-hour snapshots. The personal Pine daily risk gate is not a Breakout funded-account compliance test.

The data importer requested 2023-01-01 through 2026-11-03 exclusive. It found **403,200** candles through the end of November 1 UTC. October 28 and November 2 UTC archives were unavailable, totaling **576** missing five-minute bars. No candles were fabricated. Full-range Mode A rejects those gaps. Mode B's synthetic segment-boundary closes are explicitly data-quality handling, not tradable signals.

- [Mode A report](../artifacts/dvs/parity_candidate/report.md) · [interactive equity chart](../artifacts/dvs/parity_candidate/equity.html)
- [Mode B report](../artifacts/dvs/research/report.md) · [interactive equity chart](../artifacts/dvs/research/equity.html)
- [Run and validation instructions](../README.md)

Each run includes CSV trade/event ledgers, full-resolution Parquet signals/equity/trades/events, source/data/implementation hashes, configuration, and library versions. Open positions remain marked at the final close. These particular runs ended flat. Cash reconciles with the closed-trade ledger to numerical precision.

Validation completed: 45 automated tests (plus three neural-family subtests); both complete strategy runs; reloaded ML artifact/snapshot checks; Streamlit initial load, full research run, trade inspection, and missing-data rejection path; localhost HTTP health check; static chart inspection. No TradingView export reconciliation has been performed.

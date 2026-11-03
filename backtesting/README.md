# DVS ETH futures backtesting

All ETH strategy research, trained-model artifacts, data, reports and tests live in this directory. The stock Flask API remains a separate project at the repository root.

This is a local research platform with an event-driven order simulator and a Streamlit dashboard. It has no live order routing, exchange credentials, exchange deployment, or real-money execution.

## Quick start — Windows / PowerShell

Run these commands **from the repository root**. Python 3.11+ and a CPU are sufficient.

```powershell
python -m venv backtesting/.venv
backtesting/.venv/Scripts/python.exe -m pip install -r backtesting/requirements.txt
backtesting/.venv/Scripts/python.exe -m backtesting download
backtesting/.venv/Scripts/python.exe -m pytest backtesting/tests -q
backtesting/.venv/Scripts/python.exe -m streamlit run backtesting/dashboard.py --server.address 127.0.0.1
```

Open the local URL printed by Streamlit. `backtesting/start_dashboard.ps1` also launches the dashboard from any working directory and can reuse the existing repository `.ethvenv`.

The current session uses the existing `.ethvenv` runtime; substitute `.ethvenv/Scripts/python.exe` in the commands above to reuse it. Optional classifier experiments need `backtesting/requirements-ml.txt`. The dashboard and DVS engine do not require PyTorch, XGBoost, a GPU, Docker, TradingView Premium, or a paid data subscription. ML-only tests are skipped when those optional dependencies are absent.

## Source of truth and modes

`reference/DVS_ETH_v1_1_fixed.pine` is the supplied **v1.1** source and is now the default. `reference/DVS_ETH_v1.pine` preserves the originally supplied v1. Both files retain their original content. No TradingView trade export has been supplied. The original request is preserved in `reference/build_brief.md`; it ends at section 9.

**Mode A — TradingView parity candidate** implements the selected supplied version, including its indexing and state behavior. It is **not a certified TradingView match**. Defaults are 50,000 initial capital, **0.04% commission per side for v1.1** (0.05% for v1), two instrument ticks of adverse market/stop slippage, 20% margin, no pyramiding, and orders processed on the signal close. Initial capital and the named `input.*` risk/strategy parameters are exposed; execution changes are rejected in parity mode. Tick size defaults to 0.01 and point value to 1, matching this ETH instrument. Select a version in the dashboard or pass `--strategy-version v1`/`v1.1` to the CLI. Commission defaults resolve by version; a supplied JSON with incompatible commission is rejected.

**Mode B — Research** permits explicitly recorded changes: next-open entries, extra basis-point slippage, alternative commission, financing, stop-first treatment of ambiguous bars, and gap segmentation. `configs/research_breakout.json` is an illustrative Breakout cost scenario, not a certified account-rules simulator. It keeps the DVS signals and changes execution. The 90/10 share is only an illustrative share of positive marked net profit; it is not an actual payable payout.

```powershell
# Parity candidate on the currently available gap-free prefix.
backtesting/.venv/Scripts/python.exe -m backtesting run --end 2026-10-28 --output backtesting/artifacts/dvs/parity_v1_1_full

# Entire available history, with explicit research changes and gap handling.
backtesting/.venv/Scripts/python.exe -m backtesting run --mode research --gap-policy segment --config backtesting/configs/research_breakout.json
```

The CLI's default full-history parity run intentionally rejects missing data. The dashboard instead starts Mode A on the longest contiguous range of complete UTC days. With the current data that is January 1, 2023 through October 27, 2026. The selected dates are visible; the dashboard does not silently shorten a user-selected range or switch modes. If a selected range contains gaps, the run button is disabled and **Use complete parity range** restores the valid selection. Research mode starts with the full available history and can explicitly segment gaps.

Data-quality metrics describe the selected backtest range. The archive audit separately retains all unavailable dates from the original download request, including unpublished days beyond the available data. No candles are invented or forward-filled. Date filters reseed the simulation and indicators from the selected dataset start; match the TradingView chart history and settings when comparing outputs.

## Strategy implementation

- Daily bias compares the previous two completed UTC daily closes.
- Four-hour close, EMA(50), and latest/previous confirmed swing levels use `[1]` in their own timeframe. EMA seeds from the first available source close. Pivots use two left/two right bars, emitted at their confirmation timestamp; equal extremes select the rightmost pivot candidate.
- Fifteen-minute resistance/support use confirmed-pivot `valuewhen(...)[2]`; breakout close uses `[1]`, earlier close `[2]`, and relative volume is `volume[1] / sma(volume,20)[2]`.
- Higher-timeframe expressions map to the **5m bar-open bucket**, then the strategy evaluates at that bar's close. No unfinished higher-timeframe values are used. Prefix-equivalence tests cover incomplete 15m/4h/daily boundaries.
- Five-minute ATR uses SMA-seeded Wilder smoothing. Five-minute RVOL excludes the current volume from its 20-bar denominator.
- Setups may be replaced by another breakout, expire only when age is **greater than** 24 bars, and invalidate on loss of bias or failure through the level. A retest cannot occur on the breakout-detection bar. **v1.1 forbids confirmation on a retest bar:** its persistent `lastRetestBar` advances whenever `nearLevel and retested` holds, including subsequent nearby bars. Confirmation requires a strictly later bar. v1 preserves same-bar retest/confirmation. The retest extreme updates only on qualifying retest bars, and the last retest index is not reset when the source leaves it stale.
- Stop/target and risk sizing are calculated from the signal close, even though fills include slippage. Quantity floors to 0.001 ETH, capped by both planned dollar risk and the input leverage limit. v1.1 includes `syminfo.pointvalue` in both sizing denominators; broker P&L/notional costs use the configured point value. Targets remain tied to the original signal price.
- The personal daily loss condition gates entries, uses marked equity at the first calculated bar of each UTC day, and does not flatten an existing position. **v1.1 latches a daily lock after a breach, even if equity recovers, and clears setups whenever entries are blocked.** v1's loss gate can recover intraday. Entry counters and the v1.1 lock reset at UTC midnight. These are separate from Breakout contractual limits.

## Execution assumptions and parity limits

The custom broker processes existing orders before the bar-close strategy calculation. New close-of-bar entries cannot retroactively consume an earlier high or low from their entry bar. Pending brackets use the documented historical OHLC path: open→nearer extreme→other extreme→close. Equal-distance ties use low first. Gap crossings fill at the next open, limits may improve at gaps, and adverse slippage applies to market/stop fills, not target limits.

Margin calls use the documented four-times truncated cover quantity and are recorded as partial liquidation legs. Exact TradingView ordering at margin/stop coincidences, pivot ties, fractional fills, and end-of-bar bracket activation require export reconciliation. No tick path or bar magnifier is available from five-minute candles. Intrabar exit timestamps are explicitly upper bounds, with `exit_bar_open`/`exit_phase` stored separately. Open positions remain marked at the final close.

Research gap segmentation closes at a synthetic last-known boundary, resets setup/indicator history, and resumes with carried cash. Those boundary closes are data-quality handling with advance knowledge of segment boundaries, **not tradable strategy signals**. They must not be counted as evidence of live execution performance or mixed into Mode A.

## Historical data

The importer requests **2023-01-01 through the current complete UTC day**, exclusively from Binance's official USD-M **ETHUSDT perpetual** archives. It reuses monthly/daily ZIP caches and verifies published SHA-256 checksums. It supports milliseconds and microseconds, preserves exchange open and close timestamps, stores the exclusive five-minute availability boundary separately, removes only identical duplicates, rejects conflicting duplicates, sorts while reporting out-of-order input, and reports missing periods. No candles are forward-filled.

Clean data is stored at `data/ethusd/perpetual/candles.parquet`. Its `.quality.json` records coverage, missing periods, duplicate counts, zero-volume candles, requested versus available dates, archive manifest and Parquet hash. The dashboard exposes this audit. Updates reuse immutable archives and retry unavailable recent daily archives on the next import. Missing historical days are also attempted from daily archives. Updates do not rewrite the earlier ML experiment's CSV snapshot.

At the initial import (November 2, 2026 in New York / November 3 UTC), 403,200 candles were available through the end of **November 1 UTC**. October 28 and November 2 UTC archives were unavailable, totaling 576 missing bars in the requested range. A gap-free Mode A prefix ends immediately before October 28. Missing archive dates remain visible; later imports may recover them.

## Outputs and reconciliation

Each run writes `results.json`, full-resolution `equity/signals/events/trades.parquet`, trade/event CSVs, a standalone interactive `equity.html`, `equity.png`, and `report.md` under `artifacts/dvs/`. Output directories include strategy versions, preserving old results. Results include source and implementation hashes, configuration, data hash, library versions, assumptions, and data quality. The chart's close drawdown is distinct from both intrabar metrics. `max_intrabar_drawdown` uses a running unrealized equity peak; `max_closed_equity_drawdown_usd/fraction` uses the prior closed-equity peak, corresponding to TradingView's published convention. Both remain export-unverified, especially for partial margin liquidations.

The dashboard displays data quality, mode/risk settings, equity/drawdown, trades, candle-level trade inspection, setup events, assumptions, and saved ML reports. It also compares an explicitly normalized TradingView CSV against local trade legs. Required columns:

```text
entry_bar_open,exit_bar_open,direction,quantity,entry_price,exit_price
```

Use timestamps with explicit UTC offsets and LONG/SHORT directions. Match exchange, standard candles, timeframe, tick size, inputs, chart start/history, commission, slippage, margin and order-processing properties. Convert TradingView's export into these columns explicitly; the tool does not guess localized column names or timezone. Matching one normalized export is evidence for that period only, not a global parity certificate. No comparison export has yet been supplied.

## Layout

```text
backtesting/
  config.py, indicators.py, engine.py  # DVS logic and custom broker
  market_data.py                      # public archives, UTC audit, Parquet
  reporting.py, reconcile.py          # artifacts and normalized TV comparison
  dashboard.py, __main__.py           # Streamlit and CLI
  configs/                            # separate parity/research examples
  reference/                          # supplied Pine and original brief
  tests/                              # DVS, data, broker and optional ML tests
  eth_research/                       # previous classifier experiment, separate from DVS
  data/, artifacts/                   # local Git-ignored caches and results
  reports/                            # small reviewable result summaries
```

Previous classifier results and reproduction commands are in [ML_RESEARCH.md](ML_RESEARCH.md). Their next-bar directional accuracy does not measure this DVS strategy's trade win rate. The relocated models still use the same saved weights and dataset snapshots.

The completed DVS runs and validation record are summarized in [reports/dvs_comparison.md](reports/dvs_comparison.md).
The original v1 results in that report are historical. See [reports/tradingview_discrepancy.md](reports/tradingview_discrepancy.md) for the v1.1 correction and current comparison.

Ongoing strategy-improvement experiments use the separate [research protocol](RESEARCH_PROTOCOL.md). The dashboard's **Strategy research** tab shows checkpoint progress, validation results and downloadable experimental configurations.

The saved **DVS ETH v1.2** derivative, reproduction command and validation limitations are in [V1_2.md](V1_2.md). Select it under **B · Research → Research preset** in the dashboard. It remains experimental because one validation half was negative.

References: [Binance public futures data](https://github.com/binance/binance-public-data), [TradingView strategy broker semantics](https://www.tradingview.com/pine-script-docs/concepts/strategies/), [TradingView higher-timeframe data](https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/), [Breakout fees](https://www.breakoutprop.com/symbols/).

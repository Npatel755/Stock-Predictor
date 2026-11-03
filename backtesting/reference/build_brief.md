# MASTER PROMPT — Build a Professional ETH Futures Backtesting System in Python

## 1. Your Role

You are a senior quantitative developer, algorithmic trading engineer, and Python software architect.

Your task is to build a complete, production-quality, locally executable cryptocurrency futures backtesting platform.

The system must faithfully reproduce my existing TradingView Pine Script v6 strategy named:

**DVS ETH v1.1 — Daily Bias + Market Structure + Volume**

The objective is to backtest Ethereum perpetual futures using years of historical market data without requiring TradingView Premium.

Do not simply create a generic trading bot. Recreate my actual strategy and build a reliable research environment around it.

Prioritize accuracy, reproducibility, realistic trade simulation, and clean software architecture.

**This is a backtesting and paper-trading research system. Do not implement live trading, real-money order execution, exchange API keys, or automated deployment to an exchange.**

---

# 2. Technology Stack

Use:

- Python 3.11+
- Pandas
- NumPy
- Matplotlib
- Plotly
- Streamlit
- PyArrow for Parquet storage
- Requests or HTTPX for historical data downloads
- Pytest for automated testing
- Python logging
- Dataclasses and type hints

Use a custom event-driven backtesting engine for accurate order simulation rather than relying entirely on vectorized backtesting.

You may use additional lightweight libraries when justified.

The system must run locally on Windows using VS Code, PowerShell, or WSL Ubuntu.

Do not require Docker, a paid service, or a GPU.

---

# 3. Original Pine Script — Mandatory Source of Truth

Use my existing DVS ETH v1.1 Pine Script as the authoritative specification.

First, search the current repository for the `.pine` strategy file.

If you find it, read the entire file before implementing anything.

If it isn't available, ask me to provide it or create an explicit reference specification from the logic below. Do not pretend that a reconstruction is a verified match.

Do not replace the original strategy with a simplified moving-average crossover, generic breakout system, or unrelated algorithm.

Maintain two distinct modes:

**Mode A: TradingView Parity**

Reproduce the original Pine Script exactly, including its unusual behaviors, even when a cleaner implementation is possible.

**Mode B: Research**

Permit experimental modifications to signals, execution, and risk rules.

Never mix Mode B modifications into Mode A without explicitly documenting them.

---

# 4. Market Data Requirements

Primary instrument:

**BINANCE:ETHUSDT.P — Binance ETHUSDT USDⓈ-M perpetual futures**

Use historical perpetual futures data, not spot ETHUSDT data.

Primary source:

https://data.binance.vision/

Download available historical 5-minute futures candlesticks for:

**January 1, 2023 through the latest available complete UTC day.**

Requirements:

1. Support monthly and daily ZIP archives.
2. Download archives efficiently.
3. Verify successful downloads.
4. Validate CSV column names and types.
5. Preserve original exchange timestamps in UTC.
6. Remove true duplicate records.
7. Detect missing and out-of-order candles.
8. Report missing periods instead of silently filling them.
9. Store cleaned data in Parquet format.
10. Cache downloaded archives.
11. Avoid redownloading unchanged data.
12. Support incremental updates.
13. Handle Binance's historical timestamp-unit conventions correctly.
14. Distinguish open timestamps from close timestamps.

Use exchange candle timestamps to define exact bar boundaries.

Do not silently shift candle timestamps.

If the dataset has gaps, the backtester must either reject the affected period or explicitly account for those gaps.

Historical data quality must be visible in the dashboard.

---

# 5. Multiple Timeframe Engine

The strategy uses four timeframes:

| Timeframe | Purpose |
|---|---|
| 1D | Daily directional bias |
| 4H | Higher-timeframe trend and market structure |
| 15M | Breakout detection |
| 5M | Entry and execution |

Build all higher-timeframe candles from the underlying 5-minute dataset, unless separately downloaded exchange candles are needed for parity testing.

Pay careful attention to candle boundaries.

Use only information that would have been available at the simulated decision timestamp.

### Prevent lookahead bias

The Pine Script uses `request.security()` with previous completed higher-timeframe bars and `lookahead=barmerge.lookahead_on`.

Reproduce the actual value availability and behavior of those expressions.

A completed daily or 4H candle may influence future lower-timeframe candles only when the corresponding data is legitimately available.

Do not accidentally use the final values of an unfinished higher-timeframe candle.

Do not calculate future swing pivots as if they were known at their pivot location.

Create dedicated automated tests to verify that no future information leaks into the signals.

---

# 6. Daily Directional Bias

Implement the original strategy's daily bias.

### Bullish daily condition

The previous completed daily candle must close above the preceding completed daily candle.

### Bearish daily condition

The previous completed daily candle must close below the preceding completed daily candle.

Use:

- Previous completed daily close.
- Daily close from two completed daily candles ago.

Neutral conditions should not generate entries.

---

# 7. Four-Hour Trend and Structure

Use the previous completed 4-hour candle.

Calculate:

- 50-period exponential moving average.
- Confirmed swing highs.
- Confirmed swing lows.

Swing pivots must follow TradingView's `ta.pivothigh(high, 2, 2)` and `ta.pivotlow(low, 2, 2)` semantics.

### Bullish structure

Require:

1. Latest confirmed swing high above previous confirmed swing high.
2. Latest confirmed swing low above previous confirmed swing low.
3. Previous completed 4H close above the 4H 50 EMA.
4. Bullish daily condition.

### Bearish structure

Require:

1. Latest confirmed swing high below previous confirmed swing high.
2. Latest confirmed swing low below previous confirmed swing low.
3. Previous completed 4H close below the 4H 50 EMA.
4. Bearish daily condition.

Otherwise, classify the directional bias as neutral.

Carefully reproduce the Pine Script's use of `ta.valuewhen()` to retrieve the latest and previous confirmed pivot values.

Also reproduce the original pivot confirmation delay.

---

# 8. Fifteen-Minute Market Structure

Detect bullish and bearish breakouts using the 15-minute chart.

Calculate:

- Latest confirmed 15M swing high.
- Latest confirmed 15M swing low.
- Previous completed 15M close.
- Earlier completed 15M close.
- 15M relative volume.

### Bullish breakout

Require:

- Bullish higher-timeframe bias.
- Previous 15M candle closes above the previously established swing resistance.
- Earlier 15M candle was at or below that resistance.
- Breakout relative volume at least 1.5.

### Bearish breakout

Require:

- Bearish higher-timeframe bias.
- Previous 15M candle closes below established swing support.
- Earlier 15M candle was at or above support.
- Breakout relative volume at least 1.5.

Relative volume:

`RVOL = completed breakout candle volume / average volume of the preceding 20 completed candles`

When reproducing the Pine Script, maintain its exact indexing and initialization behavior.

Activate new setups only when the relevant 15M candle becomes available to the 5M engine.

---

# 9. Retest Detection

Following a valid breakout, wait for price to retest the broken structure level.

Default settings:

- Retest window: 24 five-minute bars.
- Retest tolerance: 0.25 × ATR(14).
- ATR calculated on the 5M timeframe.

### Long retest

Price revisits the previous resistance level, now acting as potential support.

Record the retest swing low.

### Short retest

Price revisits the previous support level, now acting as potential resistance.

Record the retest swing high.

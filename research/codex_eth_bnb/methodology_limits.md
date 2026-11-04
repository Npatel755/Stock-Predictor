# Interpretation and execution limits

This is a bounded retrospective development study, not proof of future profitability. Training folds and validation have both been inspected in earlier repository research. The nominal final20% is withheld from performance calculations because earlier ETH/BNB searches contaminated it. There is no independent final-test result to report.

## Accounting conventions

All candles use UTC open timestamps. A bar ending at midnight belongs to the preceding calendar day. The runner ranks using calendar-correct daily Sharpe. The execution engine's original volatility/Sortino fields aggregate on close dates; `tools/audit_outputs.py` produces calendar-correct companion values and monthly/quarterly/yearly attribution without changing the frozen selection. Read `accounting_audit.csv` for the consistent calendar sampling values and `walkforward_results.csv` for original frozen-fold records. This small reporting correction does not change signals, trades, costs or rank choices.

Intrabar drawdown is a conservative OHLC equity bound, not observed tick-ordered drawdown. A same-bar adverse low and final close peak may not have occurred in that order. Close drawdown is separately reported. Funding rates are actual signed settlements, but notional uses candle-open last prices rather than unavailable historical mark prices. Settlement timestamp processing jitter is at most47ms after nominal8h boundaries; execution approximates payment eligibility at the nominal boundary before new entries. Features wait until the exact timestamp plus1hour, so that approximation cannot make settlement information available early.

Daily VWAP is `(high+low+close)/3 × volume` accumulated from00:00UTC. It is a conventional bar-based VWAP approximation, not a reconstruction from individual exchange trades. Higher-timeframe candles must contain every source candle before joining by close availability.

## Risk and capacity

The primary cap is1x at entry, with fractional stop-risk sizing0.25% and previous completed-bar volume participation0.1%. A stop can lose more than planned after a gap, extra fees, incomplete exit or financing. Participation caps are rough capacity scenarios; historical depth and queue order are unavailable. Exits can remain partial, exposing residual risk. A forced final accounting close may exceed capacity and is flagged, not represented as a demonstrated tradeable fill.

Buy-and-hold is capacity-constrained at its first eligible entry and does not pyramid later to fill unused allocation. It therefore can invest less than the full nominal account, especially at5m, and is labeled accordingly. It remains a perpetual long benchmark including funding, not a spot holding strategy.

At1x the strategy still has downside risk; short notional can drift as price changes. Any2x diagnostic uses an approximate maintenance threshold based on last prices, without historical mark-price tiers, liquidation fees or insurance-fund mechanics. No exchange-accurate liquidation safety claim is possible. Fixed tick/quantity steps and fees are explicit scenarios, not asserted historical filter schedules.

## Statistical and scope limits

Holm uses124 frozen slots:96 primary,24 baseline, and4 conditional model/ensemble slots. This does not account precisely for unknown prior adaptive testing; it is conservative for this run but cannot undo earlier848 ETH slots and crypto rounds. The seven-day circular block bootstrap assumes useful local dependence/stationarity and has finite Monte Carlo resolution. Parameter neighbors, long/short restrictions, transfer and null controls are sensitivity diagnostics; none replaces a failed validation rule.

The portfolio uses two separately funded half-capital sleeves with observed correlation; simultaneous ETH/BNB exposure is not assumed independent. The tested entry halt is a5% per-sleeve drawdown lock, not a fully synchronized tick-level portfolio risk engine. It prevents new entries after the first observed breach while retaining protective exits.

No open-interest model is fit because a complete point-in-time history is absent. Logistic models are skipped if the simple1h baseline fails the frozen evidence gate. Ensembles are inverse-volatility allocations of different mechanisms whose internal TRAIN evidence qualifies; their weights never use validation returns. If no candidate meets every frozen gate, the recommendation remains no strategy, with no live deployment or unattended paper collection.

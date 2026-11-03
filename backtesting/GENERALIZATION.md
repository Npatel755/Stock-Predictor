# Generalization protocol and current findings

**Future usability is unproven.** Repeatedly choosing better 2023–2026 results exposed that history to selection. Resplitting those observations now cannot create an untouched holdout. Current versions remain experimental.

The latest saved candidate, v1.11, is frozen. Its $12,814.03 development score is retained for provenance. Further whole-history profit campaigns and historical-profit-only version promotion are disabled. The campaign runner and all ten legacy optimization entry points, numbered saver, ML training data boundary and dashboard enforce these controls. Original research-driver source bytes are preserved under content-addressed revisions. The verifier permits the added lock only when all other source text still matches its pinned original.

## What was added

- A hash-locked strategy, Pine source and execution/indicator implementation.
- A retrospective nested chronological rule-selection diagnostic: three preceding six-month inner blocks choose the rule; a later six-month outer block evaluates it. A seven-day gap and trade-outcome availability mask purge overlapping labels. Open trades are excluded from inner selection scores. Weak inner evidence selects no-trade.
- A multiple-testing diagnostic using centered seven-day blocks and 100,000 bootstrap draws, adjusted for 848 logged search slots. The complete independent search history is unavailable, so this is a conditional retrospective diagnostic, not a certified global false-positive probability.
- Immediate parameter-neighborhood sensitivity checks.
- Newly fetched 2017 ETH spot and a separate BTC transfer test, with rules frozen before data retrieval, raw archive checksums, cost stress and no parameter optimization.
- A locked future ETH period, and an evaluation certificate that cannot be silently overwritten after inspection.

The historical candidate pool was itself selected on inspected data. The walk-forward table is therefore labelled retrospective. It tests the chronology of the selection procedure; it does not erase earlier exposure. Model-selection bias and the role of separate evaluation are discussed in [scikit-learn's nested-validation documentation](https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html), [time-series splitting documentation](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html) and the primary [backtest-overfitting research](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf).

## New data and actual results

| Frozen-rule diagnostic | Data | Main result | Important limitation |
| --- | --- | ---: | --- |
| ETH 2017 | 39,310 real five-minute ETHUSDT spot bars | −$77.32 summed across reset segments | Only 11 entries; insufficient evidence; spot is not futures |
| BTC transfer | 402,048 real five-minute BTCUSDT perpetual bars | +$2,546.75 | Hypothetical controlled execution assumptions; not future ETH validation |
| BTC at 4bp extra slippage | Same BTC bars and rules | +$1,504.56 | 5.24% intrabar drawdown |
| BTC at 8bp extra slippage | Same BTC bars and rules | **−$374.97** | 6.57% intrabar drawdown; transfer is cost-sensitive |

ETH spot intervals with malformed timestamps are excluded and reported; their timestamps are never shifted. Actual gaps split the test into independently reset accounts with fresh warm-up. Short segments are skipped. Multiple segment-account sums are not continuous returns. Raw ZIPs, checksums, omitted-row counts and ledgers are retained.

The older Massive ETHUSD request returned HTTP 403 for the configured entitlement. Native 2019 futures archive probes returned 404. Public 2017 spot data was available and was fetched into a separate data folder; it did not overwrite the ETH futures benchmark. A new venue or earlier regime adds a transfer check, not genuinely future observations.

An additional fixed-rule test selectively fetched ETH/USD five-minute candles from [Kraken's official OHLCVT archive](https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data), using about 23 MB of bounded range requests instead of downloading the full multi-part archive. The archive's ETags and range bounds were checked; the selected member's CRC and local SHA-256 were retained. The published SHA-256 of the entire multi-gigabyte archive was **not verified**.

The Kraken test reads 707,732 real spot candles from 2020 through September 2026. With unchanged rules, hypothetical costs and 54 independent reset accounts, the summed net is +$5,955.34 at main costs, +$5,374.00 at 4bp extra slippage and +$4,304.70 at 8bp. These are **not continuous returns**. There are 2,188 missing intervals; 346,187 rows in short segments were skipped. At most 28.2% of the source rows remain after each retained segment's minimum warm-up. This fragmented coverage materially limits the result. Venue prices are related, and this is spot under hypothetical leveraged costs, not actual Breakout fills. See [the venue-transfer report](reports/generalization_kraken_ethusd.md). The result is now consumed diagnostic evidence and does not select new parameters or alter the forward lock.

Both newly inspected datasets are now marked **consumed diagnostic data**. They cannot be repeatedly tuned on while being called untouched tests. BTC outcomes do not select new ETH parameters.

No statistical independence between ETH and BTC is assumed. A cross-asset transfer result is not a substitute for the fixed prospective ETH test.

## Historical warning signs

The one-sided historical block-bootstrap p-value is approximately 0.00020 before multiplicity adjustment. Using 848 logged slots gives approximately **0.170**, or **0.236** using the upper Monte Carlo bound. This does not establish an edge at a 0.05 threshold. It is not a probability of overfitting or of future success; bootstrap and trial-count assumptions remain material.

Three of four immediate parameter neighbors retain at least 90% of selected historical net. The worst retains about **77%**. This sensitivity and the small latest improvement remain warnings, not reasons to keep searching the same test until it looks better. The retrospective walk-forward also includes a losing outer fold and a no-trade fold.

See [chronological diagnostics](reports/generalization_diagnostics.md), [BTC](reports/generalization_btc.md), [BTC stress](reports/generalization_btc_stress.md), [ETH 2017](reports/generalization_eth2017.md), and [ETH stress](reports/generalization_eth2017_stress.md).

## Locked prospective evaluation

The fixed ETH v1.11 rules are locked for **2026-11-04 00:00 UTC through 2027-05-03 00:00 UTC exclusive**. The supported training, ordinary replay and optimization workflow excludes that window. The final evaluator reads no test prices before the scheduled end.

The predeclared minimum checks are:

- Complete real five-minute coverage and at least five EMA lengths of prior warm-up; no fabricated bars.
- At least 30 closed trades in the fixed 180-day window.
- Positive net at main costs and both 4bp/8bp extra-slippage scenarios.
- No margin calls and at most 5% intrabar drawdown in every scenario.
- A positive lower bound from the fixed seven-day-block confidence procedure.

Insufficient trades/data or failed checks remain insufficient/failed. The parameters and test end are not moved after seeing the result. A revealed certificate is immutable; a changed dataset or parameter set cannot silently replace it. A passing paper test would still not guarantee future profits or certify TradingView matching, actual Breakout fills or account-specific funded rules.

```powershell
.ethvenv/Scripts/python.exe -m backtesting.forward_validation --bars backtesting/data/generalization/forward_eth.parquet
```

Before May 3, 2027 this returns `awaiting_future_window` without reading test prices. No forward-validation certificate currently exists. New candidate parameters need a separately registered prospective protocol; they cannot inherit v1.11's test.

## Dashboard and files

Refresh the dashboard. **Generalization** shows the lock, chronological diagnostics, sensitivity and the additional ETH test. **BTC transfer test** is a separate tab with equity, drawdown, monthly P&L, trade inspection and cost-stress results. Its rules are fixed independently of sidebar selections.

The protocol is in `configs/generalization_policy.json`. Audit manifests, source hashes, actual data exposure, segment ledgers and results are in `artifacts/generalization/`. Earlier strategy configurations, metadata and Pine files remain unchanged. Original reproduction certificates are preserved when verifier code changes; rechecks receive separate files.

Exact copies of the two native ETH input datasets are retained under `artifacts/generalization/frozen_inputs/`. A later archive update cannot silently change an old replay: the verifier uses a matching original snapshot or refuses the run.

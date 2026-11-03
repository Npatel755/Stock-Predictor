Output truncated at line 134; continue reading from line 135.
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

## Direct Coinbase ETH/USD and BTC/USD tests

To test another venue without using Binance candles, the frozen rules were run on the public [Coinbase Exchange candle feed](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles). Both datasets cover January 1, 2023 through October 27, 2026 UTC. Coinbase prices and volumes are source-specific, but same-asset market prices across venues remain related. This is venue/asset transfer evidence, not fresh chronological validation.

| Coinbase product | Actual five-minute rows | Main-cost sum of reset-account net | At 4bp extra slippage | At 8bp extra slippage | Entries / reset segments |
| --- | ---: | ---: | ---: | ---: | --- |
| ETH/USD | 401,804 | +$7,951.24 | +$7,001.00 | +$5,260.77 | 284 / 10 |
| BTC/USD | 401,812 | −$20.60 | −$961.44 | −$2,652.20 | 284 / 8 |

These sums are **not continuous returns**, are not added to the Binance development score, and use hypothetical controlled execution costs rather than actual Coinbase spot fees or observed Breakout fills. The ETH candidate is unchanged: 72-hour channel, EMA250, signed 200bp gap, RVOL2.8, 1.5 ATR initial stop, 5.5R target and 3 ATR trail. Coinbase's quote tick is modeled at $0.01 for both assets; quantity rounding and the other research cost/risk assumptions remain fixed.

The 2,792 original daily API responses are retained with local SHA-256 hashes. Coinbase does not publish a separate checksum for these API responses, so no independent feed-integrity verification is claimed. API candle order is time, low, high, open, close, volume; inclusive end records are explicitly excluded. Gaps of 244 ETH candles and 236 BTC candles remain unfilled. After short-segment exclusion and minimum indicator warm-up, at most 92.5% of ETH rows and 94.0% of BTC rows remain eligible for execution.

Coinbase ETH stayed positive across these modeled cost scenarios, but Coinbase BTC did not. That is a generalization limitation, not a reason to retune the consumed BTC test until it passes. Every fixed main/stressed replay is freshly reproduced from the pinned responses before being described as computationally verified. The strategy stays experimental and the prospective lock is unchanged. See [full Coinbase results](reports/generalization_coinbase.md).

The dashboard places Coinbase ETH/USD under **Generalization**. **BTC transfer test** has separate **Coinbase BTC/USD** and **Earlier Binance BTC transfer** sub-tabs, each with equity, monthly P&L and candle-level trade inspection.

```powershell
.ethvenv/Scripts/python.exe -m backtesting.coinbase_validation
.ethvenv/Scripts/python.exe -m backtesting.coinbase_verification
```

The first command returns an existing consumed audit after checking its pinned sources; it does not fetch a revised feed or choose new parameters. The second rebuilds inputs and replays the recorded costs. These operations do not create a forward-validation certificate or promote a strategy version.

## v1.12 cost-reserve candidate

One new hypothesis is registered separately under `candidates/eth_v1_12/`: keep the frozen entry/exit rules, but size for a fixed 8bp slippage budget. This is an **unpromoted research candidate**, not a new historical-profit winner. Its Pine and pasteable text exports are explicitly labeled as candidates.

The new comparison separates the cost used for sizing from the cost used for market/stop fills. The baseline always sizes for 2bp; the candidate always sizes for 8bp. Actual fills are then stressed at 2, 4 and 8bp for both. Previous stress tests raised both assumptions together and remain diagnostics of known higher execution costs. They did not measure the same unexpected-cost question. Neither method observes actual order-book depth or guarantees a maximum realized loss.

Only the already-inspected native ETH development period is replayed, including each annual account reset. External ETH venue tests and BTC results do not choose new signal thresholds. No parameter grid is searched. The original v1.11 main result must reproduce exactly, and a second replay must reproduce the new metrics, ledgers and curves before the dashboard labels them computationally reproduced.

The candidate has its own hash-pinned 180-day future protocol. Its primary comparison requires lower intrabar drawdown at 8bp actual fills while retaining at least 90% of the positive fixed-2bp-budget baseline net, together with positive net at all costs, trade-count, drawdown, no-margin-call and positive lower block-interval checks. The original v1.11 lock is preserved; no candidate inherits its future evidence or automatically promotes itself. Historical profits cannot revise the new hypothesis or its protocol.

```powershell
.ethvenv/Scripts/python.exe -m backtesting.cost_reserve_study
.ethvenv/Scripts/python.exe -m backtesting.cost_reserve_study --verify
.ethvenv/Scripts/python.exe -m backtesting.cost_reserve_study --forward-bars PATH_TO_COMPLETE_FORWARD_PARQUET
```

The last command reads no prices before the candidate's registered end date. See [the cost-reserve report](reports/v1_12_cost_reserve.md). The Generalization tab includes the fixed-budget comparison, equity/drawdown overlays, monthly results, trade charts and candidate downloads.

## Structural robustness candidates (robust_structure_round1)

A pre-registered round of ten candidates (`backtesting/robust_structure_lab.py`, manifest frozen before any outcome) changed trade structure instead of entry thresholds, motivated by the consumed v1.11 ledger: trades stopped within two hours lose about $4.8k of the $9.4k total stop losses at a 5% win rate because the 1.5 ATR stop sits inside the median 2.8 ATR breakout candle, and no causal entry feature had Spearman |rho| above 0.14 with trade R. Groups: (a) initial stop 2.0/2.5/3.0 ATR with the 8.25 ATR target distance and 3 ATR trail unchanged; (b) a guard rejecting entries preceded by more than two same-direction raw channel breakouts in the prior 72 completed hours; (c) ensembles of neighbouring channel-length (48/72/96) and RVOL (2.4/2.8/3.2) settings traded as independent $100/n-risk sub-accounts. Same chronology as the other labs: 2020-2023 annual training at 8bp fills against a same-budget v1.11 replica, 2024 check, frozen selection, 2025-2026 diagnostics.

Outcome: **no candidate improved on v1.11, and nothing was promoted.** The 2.0 ATR stop scored 459.51 against the 410.06 v1.11 replica in training but closed $1,930.06 in 2024 against v1.11's $2,854.86; 2.5 and 3.0 ATR stops were ineligible. The fresh-breakout guard lowered the training score for every stop width (231.13 at 1.5 ATR). Ensembles had the best training scores (ensemble_grid_9: 769.52, 2024 closed $2,279.73) and were selected by the fixed gates, but on 2023-2026 the nine-member ensemble made $10,761.15 at 2bp fills versus $13,166.91 for v1.11 ($8,628.28 versus $10,858.31 at 8bp) with a slightly lower drawdown (2.83% versus 3.03%, upper-bound basis) and 2,806 small trades, so it failed the historical improvement gate (`higher_main` and `higher_stressed` false). Conclusion: v1.11's structure is not improved by wider stops, de-chasing or parameter averaging on the inspected history; its weakness is a cost of the breakout style rather than a fixable parameter, and more development rounds on this data only add selection exposure. v1.11 remains the frozen strategy awaiting its sealed prospective test.

Commands: `.ethvenv\Scripts\python.exe -m backtesting.robust_structure_lab` then `--verify`. Artifacts under `backtesting/artifacts/strategy_lab/robust_structure_round1/`, report at `backtesting/reports/robust_structure_round1.md`, dashboard section under the additional labs.

## v2 scale-in candidates (v2_scale_in_round1)

With discretion to pursue any direction under proper versioning, the second pre-registered round (`scale_in_lab.py`) tested the one structural idea the consumed ledger directly motivates: stops hit within two hours cost about $4.8k of the $9.4k total stop losses at a 5% win rate, while trades that progress are strongly positive. Six fixed candidates keep every frozen v1.11 entry, filter, target and 3 ATR trailing rule and change only how the $100 planned risk is deployed: a $50 core leg at the signal and a $50 add-on leg after price closes 0.5/1.0/1.5 initial-risk units in favour, either moving the core stop to breakeven with the add-on stopped at the core entry, or keeping the original stop for both. Both legs fill at the next open; two independent Broker sub-accounts are summed, so fees, financing, margin and stop-first handling are the shared frozen code and v1.11 is untouched.

Chronology was the same as the earlier labs: 2020-2023 annual training at 8bp fills against a same-budget v1.11 replica, the top eligible candidate per add-on-stop group checked on 2024 after a seven-day gap, selection frozen, then 2025, 2026 and 2023-2026 at 2/4/8bp fills. Moving the core stop to breakeven failed training at 0.5R and 1.0R (breakeven exits cut the trend winners the strategy depends on); keeping the original stop with a 0.5R add-on (`scalein_t0.5_original`) was eligible in training (score 517 against 410) and in 2024 ($2,079 closed, 1.25% drawdown, against v1.11's $2,855) and was selected before audit. On 2023-2026 it made $9,733 at 2bp and $7,924 at 8bp against v1.11's $13,167 and $10,858, with lower drawdown (2.11% and 2.30% upper bounds against 3.03% and 3.46%) and 501 legs against 312 trades. Deferring half the risk reduced losses on fast stop-outs but gave up more on the winners that run straight from entry, so the historical comparison failed and no v2.0 candidate was registered or promoted. `reports/v2_scale_in_round1.md` and the dashboard keep every candidate, including the failed ones.

Together with robust_structure_round1 and Codex's filter, exit, timeframe and funding labs, every reasonable structural change to the v1.11 breakout has now underperformed the frozen rules on the consumed history. The honest reading is that v1.11's fast stop-outs are the price of its trend capture rather than a removable defect, that further search on 2020-2026 mostly adds selection exposure (848 logged slots plus 62 lab candidates), and that the sealed 2026-11-04 to 2027-05-03 forward test remains the only admissible evidence of generalization. A future v2.0 should come from a genuinely different return source evaluated under its own pre-registered protocol, not from more variations of this breakout.

## v2 funding-crowding fade (v2_funding_fade_round1)

The third pre-registered round left the breakout alone and tested a different return source: positioning crowding measured from settled perpetual funding (`funding_fade_lab.py`). Six fixed candidates fade the crowd when the 24-hour mean of the last settled 8h rate ranks at or above the 90th/95th/98th percentile of its trailing 30 days, with or without a same-direction break of the prior 24-hour range, using fixed geometry (2 ATR stop, 3R target, 96-hour time stop, no trail). Signals use settlements published at least one hour earlier and completed hourly candles; execution is the shared next-open Broker. As a new source it only had to be positive standalone on 2020-2023, then positive on 2024, then beat v1.11 as an added $100-risk sleeve.

Every candidate failed training: penalized scores ranged from -1,133 to -2,653 (41 to 254 entries), the two per-group shortlist entries also lost on 2024 (-$761 and -$1,241), and so nothing reached the portfolio audit, was registered or promoted. Fading extreme funding into a price failure loses money in this execution model: win rates near 30% at 3R are insufficient once fees, slippage and financing are charged. `reports/v2_funding_fade_round1.md` and the dashboard retain every candidate.

After three rounds (robust_structure_round1, v2_scale_in_round1, v2_funding_fade_round1: 22 lab candidates) on top of Codex's labs and the 848 logged search slots, no change to the breakout and no second return source has beaten the frozen v1.11 on the consumed history. The research budget on 2020-2026 is spent; the sealed 2026-11-04 to 2027-05-03 forward test is the only remaining admissible evidence, and any future v2.0 must come from a new, pre-registered idea evaluated on data that has not been inspected.

## Historical selection diagnostics

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

## Blinded source collection and readiness

The Generalization tab includes **Collect completed ETH days without evaluating returns**. It retrieves only fully completed UTC daily ETHUSDT perpetual archives, verifies their published checksums and pins each first successfully captured source. Missing archives are retried on a later manual collection. Replacing a pinned ZIP, even together with its checksum, is rejected. First-seen source data is not revised based on strategy outcomes.

```powershell
.ethvenv/Scripts/python.exe -m backtesting.forward_collection
```

The collector computes data quality only; it does not run signals, trades, equity or performance selection. Content-addressed snapshots and source provenance are retained rather than overwritten as the period grows. A later unavailable source day can change the coverage report without altering the last complete price snapshot. An operating-system writer lock prevents concurrent collections from replacing each other's source pins and releases automatically if the process exits. The final evaluator can use the retained snapshot path shown by the dashboard. No collection is scheduled in the background; the button or command must be run explicitly.


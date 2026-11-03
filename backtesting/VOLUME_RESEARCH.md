# ETH volume-filter research candidate

This separate experimental candidate improves the saved v1.4's historical net profit and drawdown on identical data, capital, risk and cost assumptions. **v1.4 remains unchanged.** The only change to its entry rules is requiring the completed signal hour's volume to be at least twice the mean volume of the preceding 20 completed hours.

- [Text for Pine Editor](downloads/ETH_Volume_Research.txt)
- [Experimental Pine](reference/experimental/ETH_Volume_Research.pine)
- [Full rule, execution and filter profile](reference/experimental/ETH_Volume_Research.json)
- [Export metadata](reference/experimental/ETH_Volume_Research.metadata.json)
- [Frozen selection report](reports/v1_4_volume_followup.md)
- [Reproduction and stress checks](reports/volume_candidate_verification.md)
- [Preceding failed filter experiment](reports/v1_4_entry_filters.md)

## Same-period comparison

All rows use continuous accounts on January 1, 2023 through October 27, 2026 UTC, starting with $50,000 and $100 planned risk per trade.

| Scenario | Net P&L | Entries | Running-peak intrabar drawdown |
| --- | ---: | ---: | ---: |
| Saved v1.4 | +$6,034.44 | 465 | 4.92% |
| Volume-filter candidate | +$9,971.43 | 397 | 4.02% |
| Saved v1.4, 4bp extra slippage | +$4,721.92 | 465 | 5.16% |
| Volume-filter candidate, 4bp extra slippage | +$8,735.76 | 397 | 4.11% |
| Volume-filter candidate, 8bp extra slippage | +$6,468.48 | 397 | 4.28% |

Main-scenario historical improvement is **+$3,936.99**, about **65.24% more net profit** than v1.4. Fees, financing and open-position marks are included; this is before any 90/10 profit distribution. These values are modeled results, not observed funded-account fills.

Rules remain a 96-hour channel, hourly EMA 150, 1.5 hourly ATR initial stop, 4.5R target and 3 hourly ATR trailing stop. Entries use the next five-minute open after an hourly confirmation. Stops tighten only after completed candles. Both trade directions and UTC weekends remain allowed. Capital, maximum 5x leverage, planned $100 cost-aware risk, three-entry daily limit and $300 personal daily gate are unchanged.

Execution assumes 0.04% commission per side, two ticks plus 2bp adverse market/stop slippage, 3.3bp/day financing at six snapshots, and stop-first handling of ambiguous brackets. The 4bp and 8bp tests increase extra adverse slippage without reducing other costs. No live order execution or funded-account compliance certification has been added.

## What passed and what still failed

The fixed historical gate required higher net profit and no worse drawdown than v1.4, at least 100 entries, no margin calls, positive independently reset 2025 halves and 2026, positive 2020-2022 aggregate, and higher full-period profit than the parent under the same doubled-extra-slippage assumptions. The selected candidate passed:

| Independently reset historical check | Net P&L |
| --- | ---: |
| 2025 H1 | +$1,981.65 |
| 2025 H2 | +$2,278.30 |
| 2026 through October 27 | +$582.55 |
| Earlier 2020-2022 aggregate | +$3,760.53 |

Positive 2026 totals hide a losing half: **2026 H1 lost $240.43**, or **$374.10 at 4bp extra slippage**. H2 through October 27 made $822.98, or $713.25 at 4bp. These are independently reset account diagnostics, not a guarantee of consistent profits.

All inspected data, including 2026, participated in selection. This is repeated historical optimization. The search count is **638 configuration slots including repeats**, plus post-selection diagnostics. The preceding 48-filter round found +$7,793.34 at minimum RVOL 1.5 but failed its 2026 gate; that failure is retained. The follow-up froze 18 volume/weekend configurations across two previously inspected geometries and selected the highest net profit passing the unchanged gate.

A fresh replay reproduced the frozen winner and saved v1.4. Equity reconstructed from actual simulated fill/financing events matches both broker endpoints. Future-data mutation and partial-hour prefix tests verify causal signal/filter availability; a neutral filter reproduces the unmodified simulator's metrics, trades and events exactly.

The conditional paired seven-day-block interval for the historical net improvement was +$1,589.98 to +$6,024.38. It **does not correct for candidate-search bias** and is not a future-profit probability. Removing the three largest winners by diagnostic subtraction leaves +$8,687.46; that subtraction is not a deployable strategy replay. Nearby volume thresholds were profitable on development history, but did not select a new rule. No independent forward observations have been collected.

## Visual dashboard and TradingView

In **Strategy research**, choose **round8_volume_geometry**. Click **Backtest filtered research candidate on selected dates**. It uses the sidebar's UTC dates with fixed candidate risk/cost/filter settings. Results include equity, drawdown, monthly P&L and candlestick trade inspection. The numbered version selector continues to load the original saved v1.4. The filtered research replay has its own artifacts and session result.

To test the exported candidate, copy all of the text download into a new TradingView Pine Editor strategy on a standard **BINANCE:ETHUSDT.P, five-minute chart**. Allow at least 150 completed hours for warm-up. The Pine title is **ETH Volume Research | Experimental candidate**; it is not a replacement or rename of v1.4.

Pine compilation and trade-by-trade matching remain unverified. Pine exports the actual volume and optional UTC-weekend filters and only consumes the hourly signal at the hour's final confirmed five-minute close. It models fixed tick slippage; it omits Python's extra basis-point fill slippage, financing and stop-first ambiguity policy. Symbol quantity/tick precision and different initialization history can also change the result. Do not expect identical Python and TradingView headline totals. The generic independent exporter rejects filtered selections so that it cannot silently drop these entry filters.

## Reproduce

```powershell
.ethvenv/Scripts/python.exe -m backtesting.volume_refine
.ethvenv/Scripts/python.exe -m backtesting.volume_audit backtesting/artifacts/optimization/round8_volume_geometry
.ethvenv/Scripts/python.exe -m backtesting.export_volume_candidate backtesting/artifacts/optimization/round8_volume_geometry
```

The frozen universe, every negative result, source/data/profile hashes, ledgers and stress checks remain under `backtesting/artifacts/optimization/round8_volume_geometry/`. The preceding failed experiment is under `round7_v1_4_entry_filters/`. No saved v1.4 profile, Pine file or download is overwritten, and missing later candles are never fabricated.

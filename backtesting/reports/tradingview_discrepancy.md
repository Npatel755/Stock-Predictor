# TradingView comparison: supplied v1.1 correction

The supplied `DVS_ETH_v1_1_fixed.pine` confirms that the original Python implementation used a different strategy version. Both source files are preserved under `backtesting/reference/`; v1.1 is now the default, and v1 remains selectable for reproduction.

## Recent comparison

| Measure | TradingView screenshot | Python v1.1 |
| --- | ---: | ---: |
| Displayed / tested dates | Oct 11?Nov 2, 2026 | Oct 11?27, 2026 (UTC) |
| Closed trades | 2 | 2 |
| Winners | 2 | 2 |
| Net P&L | +$370.45 | **+$370.79** |
| Return on $50,000 | +0.74% | +0.7416% |
| Drawdown from prior closed-equity peak | $73.59 | **$73.69** |

The remaining total-P&L difference is $0.34, and the drawdown difference is $0.10. These are close totals, not a trade-by-trade parity certificate: no TradingView trade export has been provided, and the full displayed date range is unavailable locally. Do not silently adjust prices, fills or indicators to force the totals to match.

The prior Python recent-window result was +$82.61 with one winner and one loser. It was a v1 result, not v1.1.

## Changes established by the actual source

- Commission changes from 0.05% to 0.04% per side.
- v1.1 forbids confirmation on the same candle as a retest. Its persistent `lastRetestBar` advances on every `nearLevel and retested` bar, so confirmation must occur on a later bar that does not advance that index.
- A daily loss breach latches `dailyLocked` until the next UTC day, even if equity later recovers.
- Setups are cleared whenever trading is blocked, as well as on expiry or bias invalidation.
- v1.1 sizing includes `syminfo.pointvalue` in both risk and leverage calculations. ETH defaults to point value 1, so this alone does not alter this dataset's size.
- `timeframe.change` replaces the previous change-of-time expression; all previous-completed daily/4h/15m expressions and their indexing remain unchanged.

## The trade that changed the recent result

| Version | Short entry bar (UTC) | Simulated close-of-bar entry | Outcome | Net P&L |
| --- | --- | --- | --- | ---: |
| v1 | Oct 15, 2026 02:20 | 02:25 | Stop | ?$103.47 |
| v1.1 | Oct 15, 2026 12:55 | 13:00 | Target | +$181.95 |

The October 18 short remains a winner: +$188.84 in v1.1, versus +$186.08 in v1 with its higher commission. The changed retest-confirmation timing explains the large recent-window difference; commission explains part of the remainder.

Running the recent v1.1 window with an additional 90 days of indicator warm-up produces the same entries, sizing, exits, P&L and drawdown. That warm-up test did not explain the remaining cents-level difference.

## Drawdown convention correction

The earlier Python `max_intrabar_drawdown` metric tracked a peak that included unrealized gains inside trades. TradingView's published metric anchors to the highest closed-trade equity before the trade. Those measures differ even for identical trades. The dashboard now shows the closed-equity-peak dollar drawdown for comparison and labels the running-unrealized-peak measure separately. Both are retained in JSON reports.

For the recent v1.1 run, drawdown from running unrealized equity peaks is 0.4761%, while drawdown from closed-equity peaks is $73.69 / 0.1474%. The latter corresponds to the convention shown by TradingView, subject to export verification. Partial margin-call metric behavior is still unverified.

[TradingView's published intrabar drawdown definition](https://www.tradingview.com/support/solutions/43000681690-max-drawdown-intrabar/).

## Full-history comparison

| Scenario | Period (UTC, end exclusive) | Entries | Net P&L | Return |
| --- | --- | ---: | ---: | ---: |
| Original v1 parity candidate | Jan 1, 2023 ? Oct 28, 2026 | 198 | ?$2,948.05 | ?5.90% |
| **v1.1 parity candidate** | Jan 1, 2023 ? Oct 28, 2026 | 168 | **+$513.09** | **+1.03%** |
| v1.1 research execution scenario | Jan 1, 2023 ? Nov 2, 2026 | 168 | ?$652.09 | ?1.30% |

The research scenario additionally uses next-open fills, two basis points extra assumed slippage, financing, and stop-first ambiguous bars. It has a different date range and explicitly segments data gaps. Its result is not a TradingView-parity claim or funded-account rules certification.

October 28 and November 2 UTC archives remain unavailable. The recent parity run stops before the first gap; the longer research run resets at gaps. The screenshot does not provide exact trades, order properties or candle data with which to resolve the remaining $0.34. Exact entry/exit timestamps, quantities, commissions, prices and TradingView chart-history initialization must still be reconciled.

## Reproduce

From the repository root, using the existing CPU environment:

```powershell
.ethvenv/Scripts/python.exe -m backtesting run --strategy-version v1.1 --start 2026-10-11 --end 2026-10-28 --output backtesting/artifacts/dvs/recent_v1_1
.ethvenv/Scripts/python.exe -m backtesting run --strategy-version v1.1 --end 2026-10-28 --output backtesting/artifacts/dvs/parity_v1_1_full
.ethvenv/Scripts/python.exe -m backtesting run --strategy-version v1.1 --mode research --gap-policy segment --config backtesting/configs/research_breakout.json --output backtesting/artifacts/dvs/research_v1_1_full
```

Each run saves trade/event ledgers, equity/signals, exact Pine source hash, implementation/data hashes, configuration and library versions. Historical v1 outputs remain intact. The dashboard explicitly labels the selected and completed strategy version.

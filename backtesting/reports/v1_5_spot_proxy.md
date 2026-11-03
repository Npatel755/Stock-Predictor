# ETH v1.5 additional 2018-2019 spot-proxy test

Different market/feed: ETHUSDT spot. This tests transfer of frozen signals under an explicitly hypothetical leveraged execution-cost scenario, not observed spot/futures/Breakout fills. No tuning to the new data. 2018-2019 is an earlier-regime test, not prospective validation.

Fetched **208,855** checksum-verified five-minute ETHUSDT **spot** bars. Instrument labels remain `BINANCE:ETHUSDT`; none were relabeled as perpetual futures. 1385 missing intervals were not fabricated. Excluded off-grid source records: 241; original ZIPs remain intact and no timestamps were shifted.

Split at actual gaps into independent accounts; features and warm-up restart in each segment. Reject segments shorter than 2400 five-minute bars. No invented bars, no ticker substitution.

| Frozen strategy | Sum of independent segment-account net P&L | Entries | Eligible segments | Worst segment intrabar drawdown |
| --- | ---: | ---: | ---: | ---: |
| v1_4 | $6,833.37 | 220 | 12 | 1.98% |
| v1_5 | $5,541.70 | 170 | 12 | 1.60% |

**The segment sums are not a continuous account return.** Annual/gap boundaries start a new $50,000 account and reset indicator warm-up. Open positions stay marked at each endpoint. Hypothetical futures-style fees, leverage, slippage and financing are held fixed for comparison; they are not actual spot funding or Breakout execution.

| Year / segment | Strategy | Rows | Net P&L | Entries |
| --- | --- | ---: | ---: | ---: |
| 2018 / 2 | v1_4 | 10025 | $58.53 | 10 |
| 2018 / 2 | v1_5 | 10025 | $267.81 | 4 |
| 2018 / 4 | v1_4 | 38849 | $2,409.05 | 55 |
| 2018 / 4 | v1_5 | 38849 | $1,965.45 | 36 |
| 2018 / 7 | v1_4 | 30792 | $1,644.21 | 38 |
| 2018 / 7 | v1_5 | 30792 | $1,106.31 | 23 |
| 2018 / 8 | v1_4 | 7398 | $260.79 | 4 |
| 2018 / 8 | v1_5 | 7398 | $311.47 | 3 |
| 2018 / 9 | v1_4 | 13716 | $222.36 | 15 |
| 2018 / 9 | v1_5 | 13716 | $-58.51 | 16 |
| 2019 / 1 | v1_4 | 20184 | $948.91 | 18 |
| 2019 / 1 | v1_5 | 20184 | $739.42 | 15 |
| 2019 / 2 | v1_4 | 18372 | $152.23 | 17 |
| 2019 / 2 | v1_5 | 18372 | $-122.21 | 14 |
| 2019 / 3 | v1_4 | 6723 | $115.59 | 4 |
| 2019 / 3 | v1_5 | 6723 | $115.59 | 4 |
| 2019 / 4 | v1_4 | 19629 | $211.26 | 23 |
| 2019 / 4 | v1_5 | 19629 | $204.51 | 21 |
| 2019 / 5 | v1_4 | 25824 | $156.46 | 24 |
| 2019 / 5 | v1_5 | 25824 | $357.88 | 22 |
| 2019 / 6 | v1_4 | 3428 | $253.29 | 5 |
| 2019 / 6 | v1_5 | 3428 | $253.29 | 5 |
| 2019 / 7 | v1_4 | 10608 | $400.69 | 7 |
| 2019 / 7 | v1_5 | 10608 | $400.69 | 7 |

Skipped short segments: 4. All raw archive hashes, exact coverage, omitted segment sizes and ledgers are saved with the audit. These new rows are kept separate from the original Binance perpetual comparison. The $6,000 baseline is still judged only on the original 2023-2026 perpetual dates.

The candidate was frozen before fetching this data. Results cannot reselect its parameters in this audit. Cross-market transfer success or failure does not erase historical selection bias, certify funded-account compliance or establish future profitability. No orders or profile changes occurred.

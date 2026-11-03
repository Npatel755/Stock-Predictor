# ETH v1.10 additional diagnostics

Spot transfer with hypothetical leveraged costs. Segment sums are not continuous returns or Breakout fills. These diagnostics do not alter the frozen selection gate.

The fixed rules were recorded before running these diagnostics. The 2018-2019 spot dataset and all 24 monthly archives match their stored SHA-256 hashes. The ticker remains BINANCE:ETHUSDT spot; no spot candle is relabeled as a perpetual future. Annual/gap boundaries reset accounts and indicators; short segments are skipped equally for both versions.

| Rules | Sum of independent spot segment-account net P&L | Entries | Segments |
| --- | ---: | ---: | ---: |
| v1.9 | $5,455.36 | 138 | 12 |
| v1.10 | $5,622.07 | 118 | 12 |

Skipped short segments: 4. These sums are not a continuous return and are not added to the original perpetual baseline. Hypothetical fees, financing and leverage are held fixed. They do not represent actual spot funding, executable spot shorting or Breakout fills.

Older spot data is already inspected. This is a post-selection transfer diagnostic, not fresh validation. The earlier v1.4 spot sum was $6,833.37; see [the original audit](v1_5_spot_proxy.md). A higher original-period result does not imply a universal historical winner.

The additional reset 2026 H1 stress check at 8bp extra slippage makes **$331.16**. This post-selection diagnostic does not change the frozen gate.

A conditional paired seven-day moving-block bootstrap, 2000 draws with seed 1909, gives a 95% interval of **$-1,139.53 to $2,155.99** for the historical difference of $577.19.

The interval conditions on already-selected rules, does not correct for the repeated search, and is not a probability of future profit. All 2023-2026 data was used in historical selection. Pine compilation, TradingView matching and funded-account readiness remain unverified.

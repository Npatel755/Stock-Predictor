# ETH v1.8 additional verification and diagnostics

Fresh replay reproduces the parent and selected full-period main/4bp/8bp results, all four reset halves, the weak-half 4bp check and the 2020-2022 check. Event-reconstructed equity reconciles with the broker. Saved earlier profiles are unchanged. This verifies computation on reused historical data, not independent future performance.

## Additional weak-half stress

After selection, the independently reset 2026 H1 makes **$131.40** at 8bp extra slippage per market/stop side. This additional diagnostic was not used to change the frozen gate.

## Already-inspected 2018-2019 spot proxy

Rules and scenarios were frozen before this diagnostic. The dataset and all 24 raw monthly archives matched their stored SHA-256 hashes. The real ticker remains BINANCE:ETHUSDT spot; none of these bars are labeled as perpetual futures or Breakout execution. No missing bar is filled. Annual/gap boundaries reset accounts and indicators; segments shorter than 2400 bars are skipped equally for both versions.

| Rules | Sum of independent segment-account net P&L | Entries | Segments |
| --- | ---: | ---: | ---: |
| v1_7 | $4,391.33 | 146 | 12 |
| v1_8_candidate | $5,462.33 | 141 | 12 |

There are 4 short skipped segments. The sums above cover 12 independently reset $50,000 accounts; they are not a continuous return, actual leveraged spot fills or futures-account performance. Hypothetical financing/fees/leverage remain fixed for comparison. Different EMA warm-up periods can produce different trade counts in a shared segment. These sums are not added to the original perpetual-period baseline.

v1.8 improves on v1.7 in this inspected proxy, but still trails the earlier v1.4 proxy sum of $6,833.37 recorded in [the original audit](v1_5_spot_proxy.md). No universal historical winner or prospective validation is established.

## Conditional historical uncertainty

A paired seven-day moving-block bootstrap of daily equity differences, 2000 draws with seed 1813, gives a 95% interval of **$-1,723.99 to $3,377.66** around the historical difference. The observed difference is $741.57.

The interval includes zero. It conditions on already-selected rules, does not correct for 748 configuration slots including repeated controls, and is not a probability of future profit. Older spot data has already been inspected; this comparison is a post-selection transfer diagnostic. Pine compilation, TradingView matching and funded-account readiness remain unverified.

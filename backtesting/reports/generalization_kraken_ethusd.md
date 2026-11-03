# Kraken ETH/USD frozen venue-transfer test

ETH/USD spot venue transfer under hypothetical ETH-futures-like fees, leverage, shorting and financing. Not Breakout fills, not independent asset evidence, and not future ETH validation.

Frozen strategy: **v1.11**. Requested 2020-01-01 through 2026-10-01 exclusive. Read **707,732** real five-minute spot candles from `ETHUSD_5.csv`. No parameter search or version promotion occurred.

Split actual gaps into independent $50000 accounts and fresh indicator warm-up. Skip segments shorter than 3000 bars. No missing-candle fabrication or timestamp shifts.

TLS and pinned per-part ETags and exact Content-Range; selected ZIP member CRC and local SHA-256. Full multi-part published SHA-256 is not verified without downloading all ~9.5GB.

Downloaded 22,801,745 bytes using bounded ranges; member CRC verified and local SHA-256 retained. Full archive checksum verification: **not performed**. Archive part identities and all fetched byte ranges are retained.

| Extra slippage bp per side | Sum of independent segment-account net | Entries | Segments | Worst segment drawdown |
| --- | ---: | ---: | ---: | ---: |
| 2.0 | $5,955.34 | 177 | 54 | 1.94% |
| 4.0 | $5,374.00 | 177 | 54 | 1.97% |
| 8.0 | $4,304.70 | 177 | 54 | 2.01% |

Missing real intervals: 2188; off-grid rows excluded: 0; skipped short segments: 1153. These reset-account sums are **not continuous returns** and are not added to the Binance development score.

This dataset is now consumed diagnostic evidence. A failed result will not trigger tuning on this test until it passes. Venue and USDT/USD differences, volume construction, fragmentation and hypothetical costs limit comparability. The prospective ETH lock remains unchanged.

[Official archive description](https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data).

Coverage limitation: 361,545 of 707,732 rows were in sufficiently long segments; 346,187 rows were skipped entirely. After each retained segment's minimum warm-up, at most 199,545 rows (28.2%) remain eligible for execution; partial initial hours can reduce that further. This test is not equivalent to continuously trading the full requested period.

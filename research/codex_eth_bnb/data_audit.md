# Data audit

Market: Binance USD-M linear USDT perpetual futures. Spot economics are not mixed into this project.

| Asset | Five-minute bars | Missing | Zero-volume | Snapshot SHA256 |
| --- | ---: | ---: | ---: | --- |
| BNB | 612,288 | 0 | 47 | 0d12496c2f1ae4206694c4700b2c4e6eec53f614c08d83e47418bdfae60c836c |
| BTC | 612,288 | 0 | 66 | 0c0a308351986c4bef9e73e62f3d03b3b8a2a31fd015b956c371474c6e387187 |
| ETH | 612,288 | 0 | 47 | 487bf5623daeeda0fc42f2ad94f88b07234c1a712852b8036f8d497631b3eeb3 |

Exchange ZIP/checksum pairs validated:223. Original raw ZIPs are read-only external provenance, local clean snapshots remain in isolated data/. Funding raw ZIP/checksum copies are retained locally.

UTC candle alignment, unique/conflicting duplicates, OHLC ordering, finite/nonnegative volume, complete history and aggregation counts are checked. No prices are forward-filled. Local hashes show identity, not independent correctness of the exchange.

## Funding and missing sources

- BNB: 6378 signed settlement records, SHA256 5061d6b8f857564151d95b2a4937e63040db1dcb815a065af59231c62abd7a60.
- ETH: 6378 signed settlement records, SHA256 27ca20ec67354ae7f8300540e383395abe2b66143fee9181a8a9135e334ea6e8.

Observed settlement timestamps contain up to47ms processing jitter after nominal8h boundaries. Raw timestamps remain unchanged; settlement eligibility is approximated at the nominal boundary before new entries. Funding signals use the EXACT timestamp plus1hour delay. Payment notional uses candle-open trade prices, not unobserved mark prices. Complete coverage/interval checks run before use.
Open interest excluded: no complete point-in-time source. Historical maintenance/filter/fee schedules absent. Corporate stock splits do not apply to these linear perpetual contracts; contract/exchange convention changes remain a feed-specific limitation.

Primary source: https://github.com/binance/binance-public-data ; funding: https://www.binance.com/en/support/faq/detail/360033525031 .

# Coinbase ETH/USD and BTC/USD frozen-rule transfer

Direct Coinbase Exchange candles. Frozen **v1.11**, 2023-01-01 00:00:00+00:00 to 2026-10-28 00:00:00+00:00 exclusive. No Binance candles were used for either test. Rule and filter settings were fixed before full data retrieval; no transfer result selected parameters.

Controlled hypothetical execution: unchanged ETH research fees, shorting, leverage, financing and 0.001 quantity rounding; 0.01 USD tick for both products. These are not Coinbase spot execution costs or certified Breakout fills.

Split real gaps into independent accounts and fresh indicators; skip segments shorter than 3000 bars. Never fill, relabel or shift bars.

Retain each raw HTTPS response and local SHA-256. No provider-published response checksum or independent historical feed verification is claimed.

| Product | Extra slippage bp per side | Sum of reset-account net | Entries | Segments | Worst segment drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| ETH-USD | 2.0 | $7,951.24 | 284 | 10 | 2.27% |
| ETH-USD | 4.0 | $7,001.00 | 284 | 10 | 2.28% |
| ETH-USD | 8.0 | $5,260.77 | 284 | 10 | 2.30% |
| BTC-USD | 2.0 | $-20.60 | 284 | 8 | 5.15% |
| BTC-USD | 4.0 | $-961.44 | 284 | 8 | 5.52% |
| BTC-USD | 8.0 | $-2,652.20 | 284 | 8 | 6.18% |

Multiple reset-account sums are not continuous returns and are not added to the Binance development score. Same-asset prices across exchanges and BTC/ETH prices are related; neither test establishes statistical independence or future ETH profitability.

| Product | Actual rows | Missing requested intervals | Retained rows | Upper-bound rows after warm-up | Skipped short segments |
| --- | ---: | ---: | ---: | ---: | ---: |
| ETH-USD | 401,804 | 244 | 401,660 | 371,660 | 1 |
| BTC-USD | 401,812 | 236 | 401,664 | 377,664 | 2 |

API responses may include the candle at the requested exclusive end or preceding the start. Raw responses are retained; out-of-range records are explicitly excluded. Bucket order is time, low, high, open, close, volume. No missing candle is fabricated.

Both datasets are now consumed diagnostic evidence. Failed outcomes stay failed; they do not authorize retuning until the test passes. The frozen ETH forward-test protocol remains unchanged.

[Official candle schema and range limits](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles).

Interpretation: the frozen rule transferred more successfully to Coinbase ETH/USD than to Coinbase BTC/USD. BTC was slightly negative at main costs and lost more under both higher-slippage scenarios. The parameter set was not changed to improve this outcome. Coinbase-specific data did not supply unseen future ETH observations.

Fresh computational verification rebuilt all 2,792 source responses, reproduced the actual candle datasets and all 54 main/stressed segment replays, and reconciled the stored equity curves with the broker. Timestamp storage units are normalized for comparison; UTC instants and numeric prices/equity are compared exactly without rounding or tolerance. This establishes computational reproduction, not future profitability.

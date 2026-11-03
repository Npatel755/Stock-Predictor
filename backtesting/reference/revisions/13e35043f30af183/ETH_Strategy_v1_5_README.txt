ETH Strategy v1.5 - volume-filter research

Copy ETH_Strategy_v1_5.txt into a NEW TradingView Pine Editor strategy. Use standard BINANCE:ETHUSDT.P, 5-minute candles. Allow 150 completed hours for warm-up.

Requested baseline: $6,000 net on 2023-01-01 through 2026-10-27 UTC at $100 planned risk and $50,000 starting capital.
v1.5 main modeled net: $9,971.43; above baseline: $3,971.43; drawdown: 4.02%; entries: 397.
v1.4 actual reference: $6,034.44 net. Both remain separately selectable.

v1.5 requires hourly volume >=2x the mean of the preceding 20 completed hours. Geometry: 96-hour channel, EMA150, 1.5ATR initial stop, 4.5R target and 3ATR trail.

Added 208,855 older ETHUSDT spot bars from 2018-2019 for a separate frozen-rule test. v1.5 was profitable in the sum of independent segment accounts but trailed v1.4 there. Those spot-proxy sums are not a continuous-account return or futures execution result and are not added to the main baseline comparison.

All original 2023-2026 data was used in historical selection. Future performance and exact TradingView matching are unverified. Pine omits Python's extra basis-point fill slippage, financing and stop-first ambiguity handling. Compilation in TradingView remains unverified.

Dashboard: refresh, choose v1.5, click Run v1.5 backtest. Equity, drawdown, monthly P&L and candle trade inspection remain available.

Read V1_5.md and the additional-data reports for evidence, retained failures and limitations. No funded-account orders were submitted.

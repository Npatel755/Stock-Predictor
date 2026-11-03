ETH Strategy v1.3 - Independent channel breakout research

Open ETH_Strategy_v1_3.txt, copy all text, paste into a NEW TradingView Pine Editor strategy, save, then Add to chart.
Use standard BINANCE:ETHUSDT.P candles at 5 minutes. The strategy computes hourly signals. Allow 200 hours for warm-up.

This is an alternative to DVS v1.2. v1.2 is unchanged.
Rules: 80-hour channel, EMA 200 filter, 2 ATR initial stop, 3R target, 3 ATR trailing stop. $100 planned risk including estimated costs.

The historical selection gate passed on reused data, but 2026 lost $1,077.22 in Python. Continuous 2023-2026 net was $4,075.01, below v1.2's $4,344.93 on the same dates. Continuous 2020-2026 net was $8,529.48.

Compilation in TradingView and exact trade matching are unverified. Pine omits the Python scenario's extra basis-point fill slippage, financing, and stop-first ambiguity policy. Headline results can differ.

See V1_3.md and v1_3_robustness.md in this package for the full evidence and limitations. This is experimental research; no funded-account deployment has been performed.

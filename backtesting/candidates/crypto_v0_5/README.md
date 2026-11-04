# crypto_v0_5 (BNB, round 3, shelved candidate)

Unpromoted, not paper traded. Rule `macd_4h_patient` from `backtesting/crypto_research/round3.py`; artifacts in `backtesting/artifacts/crypto_research/crypto_round3_families/`.

MACD(12,26,9) histogram sign change on completed 4h candles with close above EMA200 (long) or below EMA200 (short); 4h volume >= mean of the prior 20 candles; entry at the next 5m open; 3 ATR stop, 5R target, 4 ATR trail. Same coin as crypto_v0_1 and also a trend rule, so it adds less diversification than a different coin would.

| Window | Closed net ($100 risk, 8bp) |
|---|---|
| 2021 train | $1,776 |
| 2022 train | $1,214 |
| 2023 train | $729 |
| 2024 validation | $341 |
| 2025 held-out | $629 |
| 2026 to Oct 28 held-out | $155 |

Worst drawdown under 2% in every window. The held-out window was opened once, after selection; it was not used to choose the rule. No Pine port exists yet, so Pine/Python parity is untested.

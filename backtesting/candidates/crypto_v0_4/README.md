# crypto_v0_4 (SOL, round 3, shelved candidate)

Unpromoted, not paper traded. Rule `keltner_4h_patient` from `backtesting/crypto_research/round3.py`; artifacts in `backtesting/artifacts/crypto_research/crypto_round3_families/`.

Keltner-channel breakout on completed 4h candles: close crosses above EMA20 + 2 ATR(14) with close > EMA200 (long) or below EMA20 - 2 ATR with close < EMA200 (short); 4h volume >= mean of the prior 20 candles; entry at the next 5m open; 3 ATR stop, 5R target, 4 ATR trail.

| Window | Closed net ($100 risk, 8bp) |
|---|---|
| 2021 train | $1,611 |
| 2022 train | $601 |
| 2023 train | $1,962 |
| 2024 validation | $53 |
| 2025 held-out | $865 |
| 2026 to Oct 28 held-out | $640 |

Worst drawdown under 2% in every window. The held-out window was opened once, after selection; it was not used to choose the rule. No Pine port exists yet, so Pine/Python parity is untested.

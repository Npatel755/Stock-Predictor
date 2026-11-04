# crypto_v0_1 — BNB 4h time-series momentum (research candidate, not promoted)

Found by the pre-registered multi-coin lab `backtesting/crypto_research/` (manifest, every candidate result,
selection and the single held-out look are under `backtesting/artifacts/crypto_research/crypto_round1/`).
ETH v1.11 is untouched; this is a separate instrument and a separate version line.

## Rules (fixed before any result was seen)
- Instrument: Breakout BNBUSD, researched on Binance BNBUSDT perpetual 5-minute data 2021-01-01 .. 2026-10-28.
- Bars: completed 4-hour bars. Signal when the 20-bar (80h) return crosses from negative to positive with close above
  the 200-bar EMA (long), or crosses from positive to negative with close below it (short). Completed-bar volume must
  be at or above the trailing 20-bar average. Enter at the next 5-minute open.
- Exits: initial stop 3 x ATR(14, 4h); target 5R; 4 x ATR trailing stop. One position at a time, both directions,
  24/7, no pyramiding.
- Sizing in research: $100 risk per trade, $50k account, 4bp commission, 8bp fill slippage budget.

## Evidence (closed net at $100 risk, 8bp fills)
| Window | Role | Net | Max drawdown | Legs |
|---|---|---|---|---|
| 2021 | train | $1,554 | 0.68% | 23 |
| 2022 | train | $856 | 1.11% | 25 |
| 2023 | train | $120 | 1.31% | 37 |
| 2024 | validation | $1,504 | 0.98% | 28 |
| 2025 | held-out, single look | $972 | 1.23% | 27 |
| 2026 to Oct 28 | held-out, single look | $300 | 1.64% | 24 |

Only 2 of 8 coins produced any candidate that passed both train and validation gates (BTC squeeze_breakout_4h_balanced
was the other, score 48 vs 612); 6 coins produced nothing. The ETH v1.11 rules transplanted to every coin failed training
on all eight.

## Breakout 50k sizing (replay of 2024-2026 trades, 79 legs)
| Risk/trade | Worst peak-to-trough | Worst day | 2025-26 profit (22 months) |
|---|---|---|---|
| $100 | $683 | $105 | $1,272 |
| $150 | $1,025 | $158 | $1,908 |
| $200 | $1,367 | $210 | $2,544 |
| $300 | $2,050 | $316 | $3,816 |

Static floor is $3,000 below start; daily loss limit ~$1,500. Recommended $200 (2.2x buffer to the floor on history);
$150 if the account must survive a drawdown twice as deep as anything seen.

## Neighbourhood check (crypto_round2_bnb, 2026-11-03)
A pre-registered 240-rule grid around this candidate (`backtesting/crypto_research/round2.py`, artifacts under
`artifacts/crypto_research/crypto_round2_bnb/`) ranked rules by the median training score of each rule and its one-step
neighbours. This candidate ranks 11 of 240 with 4 of 8 neighbours passing the training gate; 55 of 240 grid points
have a positive training score, concentrated on 4h bars, lookback 10-20, volume gate on, patient/wide exits.
The grid's top plateau rule (lookback 15, EMA100, 3 ATR / 8R / 4 ATR) lost $914 in 2024 validation, so nothing replaced
this candidate and no crypto_v0_2 exists. Read this as: the edge is narrow, and the 2024-26 numbers above could be a
favourable draw from that narrow region. Forward paper evidence decides, not further historical tuning.

## What this is not
- Not promoted. Selection used 2021-24 data; the 2025-26 numbers are one pre-registered look, not forward evidence.
- Modest: about $1.3k/yr per $100 risk, 40% win rate, longest losing streak 6. Expect flat quarters.
- No Pine script and no TradingView parity yet; nothing is deployed.

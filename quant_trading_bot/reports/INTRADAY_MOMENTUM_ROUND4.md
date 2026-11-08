# Round 4: market intraday momentum (last half hour) on MES/MNQ

Round 4 (pre-registered 2026-11-08): market intraday momentum (Gao, Han, Li, Zhou 2018, JFE 129(2)) on MES/MNQ.

Source: QuantConnect Strategy Library "Intraday ETF Momentum" -> Gao et al.: the first half-hour return (from the prior
close) predicts the last half-hour return of the S&P 500 ETF; the 12th half-hour (15:00-15:30) also predicts it; the
effect is stronger on volatile days. Adapted hypothesis, not the equity curve: take a position for the last half hour
of the CME day session in the direction of the predictor.
Mechanics: decision at the close of the 15:15-15:30 ET bar, fill at the 15:30 open through the standard engine (spread,
slippage, commissions, $150 risk, $400 daily loss, $2k DD), forced flat at the 16:00 bar open (engine flat_minute 955),
stop 1.5 ATR(16), 2 ATR trail. Predictors: first30_prevclose = close(10:00) - prior session 16:00 close;
first30_open = close(10:00) - open(09:30); h12 = close(15:30) - close(15:00). Filter |pred| >= k * ATR(16), k in {0, 1}.
target_r in {2.0, 6.0}. 3 x 2 x 2 = 12 variants per instrument, fixed before running.
Negative control ("placebo"): same predictor and sign, but the position is taken 12:30-13:00 (h12 placebo uses the
12:00-12:30 half hour). If the edge is specific to the last half hour, the placebo should not share it.
Train = ES 2010-2019 + MES 2020-2023 (NQ/MNQ for MNQ); gate: train total > 0, >= 60% train years positive, worst annual
DD < $1,000, per-trade net > placebo per-trade. Passers get one 2024-2025 validation look. 2026 never loaded.
Output: reports/INTRADAY_MOMENTUM_ROUND4.{json,md}; events.jsonl line.

| variant | predictor | k | target_r | train total | +years | worst DD | trades | $/trade | placebo $/trade | gate |
|---|---|---|---|---|---|---|---|---|---|---|
| MES/0 | first30_prevclose | 0.0 | 2.0 | -21,528 | 0/14 | 1,985 | 3296 | -6.5 | -5.4 | fail |
| MES/1 | first30_prevclose | 0.0 | 6.0 | -21,552 | 0/14 | 1,985 | 3296 | -6.5 | -5.4 | fail |
| MES/2 | first30_prevclose | 1.0 | 2.0 | -15,326 | 0/14 | 1,696 | 2468 | -6.2 | -5.4 | fail |
| MES/3 | first30_prevclose | 1.0 | 6.0 | -15,349 | 0/14 | 1,696 | 2468 | -6.2 | -5.4 | fail |
| MES/4 | first30_open | 0.0 | 2.0 | -19,094 | 0/14 | 1,846 | 3287 | -5.8 | -6.4 | fail |
| MES/5 | first30_open | 0.0 | 6.0 | -19,133 | 0/14 | 1,851 | 3287 | -5.8 | -6.4 | fail |
| MES/6 | first30_open | 1.0 | 2.0 | -11,274 | 0/14 | 1,534 | 1765 | -6.4 | -6.6 | fail |
| MES/7 | first30_open | 1.0 | 6.0 | -11,312 | 0/14 | 1,534 | 1765 | -6.4 | -6.6 | fail |
| MES/8 | h12 | 0.0 | 2.0 | -19,138 | 0/14 | 1,992 | 3213 | -6.0 | -6.3 | fail |
| MES/9 | h12 | 0.0 | 6.0 | -19,180 | 0/14 | 1,992 | 3213 | -6.0 | -6.3 | fail |
| MES/10 | h12 | 1.0 | 2.0 | -5,202 | 2/14 | 892 | 939 | -5.5 | -5.8 | fail |
| MES/11 | h12 | 1.0 | 6.0 | -5,215 | 2/14 | 892 | 939 | -5.5 | -5.8 | fail |
| MNQ/0 | first30_prevclose | 0.0 | 2.0 | -10,434 | 1/14 | 1,287 | 3190 | -3.3 | -3.2 | fail |
| MNQ/1 | first30_prevclose | 0.0 | 6.0 | -10,443 | 1/14 | 1,287 | 3190 | -3.3 | -3.2 | fail |
| MNQ/2 | first30_prevclose | 1.0 | 2.0 | -7,764 | 1/14 | 1,478 | 2394 | -3.2 | -3.1 | fail |
| MNQ/3 | first30_prevclose | 1.0 | 6.0 | -7,773 | 1/14 | 1,478 | 2394 | -3.2 | -3.1 | fail |
| MNQ/4 | first30_open | 0.0 | 2.0 | -8,300 | 1/14 | 1,068 | 3176 | -2.6 | -2.9 | fail |
| MNQ/5 | first30_open | 0.0 | 6.0 | -8,310 | 1/14 | 1,068 | 3176 | -2.6 | -2.9 | fail |
| MNQ/6 | first30_open | 1.0 | 2.0 | -5,336 | 1/14 | 1,060 | 1928 | -2.8 | -2.9 | fail |
| MNQ/7 | first30_open | 1.0 | 6.0 | -5,346 | 1/14 | 1,060 | 1928 | -2.8 | -2.9 | fail |
| MNQ/8 | h12 | 0.0 | 2.0 | -9,089 | 2/14 | 1,425 | 3157 | -2.9 | -2.9 | fail |
| MNQ/9 | h12 | 0.0 | 6.0 | -9,180 | 2/14 | 1,425 | 3157 | -2.9 | -2.9 | fail |
| MNQ/10 | h12 | 1.0 | 2.0 | -1,972 | 4/14 | 969 | 842 | -2.3 | -4.2 | fail |
| MNQ/11 | h12 | 1.0 | 6.0 | -2,052 | 4/14 | 969 | 842 | -2.4 | -4.2 | fail |

Passers sent to validation: none


# qc_1 — institutional-style mechanisms from the QuantConnect library, pre-registered (2026-11-08, before any data run)

Trigger: Nick — "try some institutional strategies that jane street and citadel use, research strategies on quant connect with the skill i gave you".
Honest framing: Jane Street / Citadel edges are market making, latency and ETF/index arbitrage (colocation, inventory, rebates,
sub-tick costs). None of that is accessible from a funded micro-futures account. What transfers is (a) the *execution style*
(earning the spread passively instead of paying it) and (b) the strategy *classes*. QuantConnect Strategy Library (85 entries,
GitHub QuantConnect/Tutorials "04 Strategy Library", listed 2026-11-08) triage for intraday MES/MNQ: already covered or closed —
04/05 breakout (mass_v2), 07 intraday pairs (pairs_1/leadlag_1), 1026 intraday momentum (anomaly_1), 16 overnight (prohibited),
35/83/102 calendar (calendar_1), 58 VIX level (extstate_1), 198 VIX term structure (extstate_1 proxy), 71/15/34 cross-sectional reversal
(equity universes). Untested and buildable on data on disk: **25 Volatility Risk Premium** as a point-in-time day state, and the
institutional execution transfer below. 1023 index-ETF arbitrage needs ETF prints (not on disk) — declared gap.

## T1 — exec_1: passive-limit execution of short-horizon fades (MNQ 2023, bbo-1s + trades)
Hypothesis: mass_1m fades lost ~one marketable round trip (5.4 ticks) per trade while beating random entries by $4-7; executed
passively (post at bid/ask, fill only when price trades through) the cost term flips from -5.4 ticks to ~0 and the fade may be positive.
Data: data/market/orderflow/MNQ_c0_bbo-1s_2023.parquet (quotes) + MNQ_c0_trades_2023-04_2023-12.sec.parquet (1-s buy/sell volume, hi/lo/last).
Window: Apr-Dec 2023 RTH 09:35-15:50 ET (190 sessions); single-year pilot, no validation split exists — result is a pilot verdict only.
Signals (from mass_1m families, fixed, no search beyond this grid): 1-min close stretch from session VWAP in ATR units z ∈ {1.5, 2.0, 2.5}
and 5-min return exhaustion (|5-min move| ≥ k·ATR14_1m, k ∈ {2, 3}); direction = fade. Entry on the 1-s quote after the signal minute closes.
Fill model (conservative): buy limit at the prevailing bid; filled only if a later 1-s `lo` prints strictly BELOW the limit (trade-through)
within W ∈ {30, 60, 120} s, else cancel (no trade). Sell symmetric at the ask. Exit: target = entry ± T ticks (T ∈ {8, 16}) also passive
(filled only on trade-through), stop = marketable at mid-adverse 12 ticks + 1 tick slippage, time-out marketable after H ∈ {5, 15} min,
flat 15:55 marketable. Commission $0.61/side; passive fills pay no spread/slippage. 3×3×2×2 + 2×3×2×2 = 60 configs.
Placebo (decisive here): identical passive fill model on 20 sets of random entry times/directions with the same count per session — a passive
limit on random signals also earns spread in a mean-reverting book, so the fade must beat the random-passive distribution at ≥95%.
Gate: net > 0, ≥ 7 of 9 months positive, ≥ 200 fills, ≥ 95% of random-passive placebos, and net ≥ +2 ticks/fill over the placebo mean.
Also reported: fill rate, marketable-version net of the same signals (the mass_1m baseline), and the sensitivity to requiring trade-through
by 2 ticks instead of 1 (queue-position stress).

## T2 — vrp_1: variance risk premium as day state (2010-2023 training, 14 years)
State = prior-close VIX² /252 − realized variance of ES 15-min RTH returns over the prior 21 sessions (point-in-time, both known at the open).
Terciles by rolling 2-year rank. Tests: (a) day-direction long/short MES/MNQ 09:45→15:54 by tercile (6 variants); (b) filter the fixed 15m MNQ
momentum rule (anomaly_1 rule) to top / bottom VRP tercile (2 variants). Placebo: 200 random same-size day sets (a), 20 random masks (b).
Gates as prior rounds: net > 0, ≥ 10/14 years, no year > 40% of net, ≥ 95% placebo, ≥ 100 trades. Validation 2024-25 only for frozen passers;
2026 never loaded. Prior: low (extstate_1 day-direction all lost).

Costs everywhere: 1.75-tick MNQ / 1-tick MES spread for marketable legs, 1 tick slippage, $0.61/side. No paper promotion from this round
without Nick's yes. Nothing is bought.

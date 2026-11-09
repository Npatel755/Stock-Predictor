# pairs_1 — intraday NQ/ES relative-value mean reversion (pre-registered 2026-11-08, before any data look)

Hypothesis: the 15-minute log-ratio of NQ to ES (beta-hedged) mean-reverts over hours; the one cross-contract horizon not yet tested (leadlag_1 covered 1-minute, extstate_1 daily states). Prior: low-moderate. Two-leg micro costs make this a high bar.

## Data / splits
- Training: ES/NQ 2010-2018, MES/MNQ 2019-2023, 15-minute RTH bars (09:30-16:00 ET) from the existing 1-minute data. Validation 2024-2025 only for frozen passers; 2026 never loaded.
- All features use completed bars only (lagged one bar). Hedge ratio beta = OLS slope of 15m log-returns NQ on ES over the prior 20 sessions, fixed for the day at 09:30.

## Spread and signal
- r_t = ln(NQ_t) − beta_d · ln(ES_t); residual z_t = (r_t − mean_N(r)) / std_N(r), N ∈ {26, 52, 130} bars (1, 2, 5 sessions), using bars up to t−1 for mean/std and r_t for the current value.
- Entry when |z| ≥ k, k ∈ {1.5, 2.0, 2.5}, at the bar close, entry window 09:45-15:00 ET (variant: 09:45-11:30). Short the rich leg, long the cheap leg (z > 0: short MNQ / long MES).
- Exit at bar close when z crosses 0, or |z| ≥ k + 1.5 (stop), or after H ∈ {8, 16} bars, or 15:55 flat. One position at a time.
- Legs: 1 MNQ vs n MES with n = round(beta · 2·NQ / (5·ES)) clipped to 1..3, set daily.
- Grid: 3 N × 3 k × 2 H × 2 windows = 36 configs. Single pass; no re-tuning.

## Costs
- Per side per contract: half spread (MNQ 1.75 ticks → 0.875; MES 1 tick → 0.5) + 1 tick slippage + $0.61. MNQ $0.50/tick, MES $1.25/tick. A 1 MNQ + 2 MES round trip ≈ $11.3.

## Tests
1. Predictive: training mean next-4/8/16-bar change of r (in MNQ-dollar units at hedged size) by z decile; need monotone sign and extreme-decile magnitude > round-trip cost with |t| > 4 to count as evidence.
2. Executable grid above with 20 placebos per config: same entries per year placed at random eligible bars, random direction, same exits.

## Gates (frozen, as anomaly_1 / extstate_1)
- Net > 0; ≥ 10/14 positive years; max single-year share ≤ 40%; beats ≥ 95% of placebos; ≥ 100 trades. Passers only → one 2024-25 validation run. No automatic paper promotion.

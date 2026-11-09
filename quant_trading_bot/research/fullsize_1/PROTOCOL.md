# fullsize_1 — re-score at full-size NQ/ES economics (Nick 2026-11-09: "you can also try nq and es"), pre-registered before any run

Cost model: NQ tick 0.25 = $5.00, ES tick 0.25 = $12.50; spread 1 tick, slippage 1 tick/side, commission $2.50/side (placeholder until Nick confirms);
funded lock $2,000 intrabar drawdown and $400/day loss applied per contract. Round trip ≈ 4 ticks (vs 5.4 on MNQ) — the saving is 1.4-2 ticks/trade,
and dollar risk is 10x. Candidates (all previously beat their placebo but failed on cost or DD; nothing new is searched):
 F1 CL-inverse channel, once per episode (first minute |z| >= 1.5 of the prior-15-min CL move, direction opposite to CL), hold 30 min or 2 ATR stop.
 F2 NQ/ES opening divergence, two-sided (|z| >= 1.25 at 10:00), stop 2 ATR, 4R, hold 12 bars.
 F3 composite_1 variants B and D (long-only union / two-agree) with the fixed exits.
 F4 AG morning EWMA trend lb16 th0.75 (30m) and the fixed 15m momentum lb24 — the trend sleeves, to size the lock breach at 1 NQ.
Training 2010-2023 only, by year, at NQ costs; same gates plus: no funded breach in any year (intrabar DD < $2,000, daily loss < $400 x 1).
Validation 2024-2025 only for passers; 2026 never loaded. Prediction written now: F1/F2 move from -$2.6/trade to roughly breakeven (the 3-3.5-tick edge
vs 4 ticks of cost); F3 becomes profitable per trade but 2021-dominated; F4 breaches the lock at 1 NQ. No spend.

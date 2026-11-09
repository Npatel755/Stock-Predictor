# Research memo — 2026-11-09 (research-prioritization checkpoint)

## Learned this batch
- composite_1 (day-selection union/intersection): hit rate up, move size unchanged; $7–12/trade, 2021-heavy. Family closed.
- fullsize_1 (NQ/ES economics): saves 1.4–2 ticks/trade; the $2k lock binds first at 1 NQ. Full size is not an unlock.
- overnight_1/2 (Globex hold, allowed under Topstep/Lucid): raw premium ≈ 7 ticks/night (t 1.6); reopen-dip nights monotone and placebo-robust
  (D4 +$16/night, 11/14 yrs, 199/200) but 2020–22-heavy, 2023 negative, frozen passer failed the one-shot 2024–25. 2024–25 spent for the family.
- Antigravity NQ-leader / Champion-2: one-bar look-ahead (10:15 close for a 10:00 fill). Correct pre-2020 +$62. Withdrawn.

## State of the registry
Every mechanism family testable on owned data is closed under micro costs and funded constraints: intraday trend/breakout (2020–25 regime only),
mean reversion, order flow, lead-lag (NQ/ES, ZN, 6E, CL), calendar/anomaly, external state (VIX, VRP, 200-SMA), passive execution, day selection,
overnight. 2024–25 has been consumed for: mass_v2 passers, 1m-CT, overnight. 2026 never loaded.

## Next three highest-information experiments (ranked)
1. **Forward paper, overnight dip sleeve** (MNQ, gap ≤ −0.5σ, 18:05 → 09:30, 16:05 safety flatten, 1c) — the only clean test left for the strongest
   after-cost family; zero cost; needs Nick's yes and a new paper candidate type.
2. **multimarket_1** (pre-registered; CL-as-MCL with the frozen trend sleeves) — tests the diversification mechanism, not a new rule; owned data; low prior.
3. **Stop active search; audit only.** Expected information gain of further owned-data rounds is now below the multiplicity cost they add.

## Do not repeat
Trend/breakout parameter variants trained on 2020–23; VIX/VRP/SMA day gates; any lead-lag at micro costs; anything scored on 2024–25 or 2026.

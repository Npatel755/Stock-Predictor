# multimarket_1 — frozen MNQ trend/breakout rules on crude as MCL (2010–2023 training) — REJECTED 0/3

Protocol research/multimarket_1/PROTOCOL.md (pre-registered). CL.c.0 1-min (Databento, already owned) resampled to 15m/30m; traded as MCL
(tick 0.01 = $1, spread 2 ticks, slippage 1 tick/side, $0.61/side, 1 contract), entries 09:30–13:30 ET on completed bars, flat 14:25 ET.
Rules exactly as frozen on MNQ. Placebo: 20 random-direction same-count signal sets. Script scripts/multimarket_1_pilot.py; JSON reports/MULTIMARKET_1_TRAINING.json.

| rule | net | trades | $/trade | +years | 2010–19 | beats placebo |
|---|---:|---:|---:|---:|---:|---:|
| M1 AG morning EWMA trend lb16 th0.75 (30m, 1.5 ATR / 3.5R / 8) | −2,663 | 1,121 | −2.4 | 5/14 | −815 | 20/20 (placebo mean −6,902) |
| M2 AG 30m Donchian breakout lb8 th1.5 (1.25 ATR / 5R / 8) | +79 | 318 | +0.3 | 8/14 | +21 | 16/20 |
| M3 fixed 15m momentum lb24 (2 ATR / 3R / 24) | −11,454 | 2,809 | −4.1 | 1/14 | −8,035 | 17/20 |

Verdict: none of the index rules transfers to crude. Trend-following direction is right more often than random (M1/M3 beat random-direction
placebos) but the captured move is below the MCL round trip (≈ 5 ticks); the breakout rule is flat. The "same rule across uncorrelated markets"
diversification route is closed on owned data. No validation run; 2024–25 untouched for this family.

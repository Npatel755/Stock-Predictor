# book_1 — intraday-trailing-floor check of overnight_dip_v2 + ag_all_weather_v2_1c, training 2010–23 (2026-11-09)

Protocol: research/book_1/PROTOCOL.md. Script: scripts/book_1_pilot.py. Both legs frozen; nothing chosen; 2024–26 not loaded.
Marks: overnight leg at every 1-min low from the 18:05 fill to the 09:45 exit; intraday leg assumed to touch its stop on every trade
(conservative upper bound). High-water mark and drawdown on the same marked path.

| | value |
|---|---|
| closed net (matches portfolio_4) | +28,317 |
| closed drawdown (portfolio_4) | 1,633 |
| **intraday-trailing drawdown** | **2,043** at 2020-03-17 18:05 (overnight fill into the 17 Mar night, after the 16 Mar co-loss) |
| breach episodes $2,000 / $2,500 / $3,000 | 1 / 0 / 0 |
| worst marked day | −857; days marked ≤ −$1,000: 0; ≤ −$500: 10 in 14 years |

## Reading
- Under an intraday-trailing floor the pair touches $2,043 once in 14 years (March 2020), $43 over a $2,000 floor and only because the intraday
  leg is charged its full stop on every trade; with a realistic intraday path it is inside the floor. Still: the margin is zero, so the pair should
  not start on a fresh $2,000-floor account — the staging rule applies in a weaker form: run one leg until ≈ $500 of profit is banked (or the floor
  is $2,500+), then both. The $1,000 daily-loss limit was never reached.
- Annotation added to reports/PORTFOLIO_4_TRAINING.md. No deployment change.

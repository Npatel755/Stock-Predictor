# calendar_1 — known calendar anomalies, intraday-only (pre-registered 2026-11-08, before any data look)

Hypothesis: published calendar effects in US index returns (turn-of-month, monthly options expiration, month/quarter-end flows, day-of-week, pre-holiday) leave a tradeable *intraday* RTH component on MNQ/MES at micro costs. Most of the equity premium is earned overnight, so the prior for an intraday-only version is low; this round is to close the question, not to tune.

## Data / splits
- Training 2010-2023 (ES/NQ to 2018, MES/MNQ from 2019), 1-minute RTH; validation 2024-2025 once for frozen passers; 2026 never loaded.
- Day sets are fixed from the calendar alone (no price data): turn-of-month (last trading day of month through the first 3), options expiration (3rd Friday), month-end last trading day, quarter-end last trading day, each weekday, day before a US market holiday, and the complements.

## Tests (all 1 contract, costs as anomaly_1: $0.61/side, MNQ 1.75-tick / MES 1-tick spread, 1 tick slippage)
1. Day-direction, long 09:45 -> 15:54 on: TOM days; OPEX days; day-before-holiday; each weekday (Mon..Fri); non-TOM days. Short versions of the same (20 variants x 2 products = 40).
2. Last hour, 15:00 -> 15:54, long and short, on: month-end; quarter-end; OPEX; TOM; all days (10 x 2 products = 20).
3. Day-set *filters* on the fixed 15m MNQ momentum rule (anomaly_1): trade only on TOM / only OPEX / only Mon / only Fri / excluding OPEX / excluding TOM (6 filters).

## Controls
- Each day-set test is compared with 200 random day sets of the same size per year (direction fixed), placebo pct = share beaten. Filters use 20 same-day-count random masks as before.

## Gates (frozen)
- Net > 0; >= 10/14 positive years; max single-year share <= 40%; beats >= 95% of placebos; >= 100 trades (day tests: >= 100 days). Passers only -> one 2024-25 validation run. No automatic paper promotion.

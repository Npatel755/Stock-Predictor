# allweather_1 — backwardation-day filter for ag_all_weather (training 2010–2023; 2024–26 sealed)

Protocol: research/allweather_1/PROTOCOL.md. Script: scripts/allweather_1_pilot.py. Raw: reports/ALLWEATHER_1_TRAINING.json. Engine default costs; sleeves run via the paper runner's run_sleeve.

| | net | trades | $/trade | +yrs | 2010–19 | max yr | closed DD | breakout / 60m trend | removed days | removed net | random 5th pct |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| champion (ag_all_weather) | 13,069 | 1,644 | 7.95 | 9 | 2,284 | 37 % | **2,061** | 7,096 / 5,973 | – | – | – |
| V1 stand aside after VIX > VIX3M close | **14,073** | 1,551 | 9.07 | 8 | 2,874 | 35 % | **1,455** | 8,021 / 6,053 | 59 | **−1,005** | −302 |

- Gates: net ↑, DD ↓ (−29 %), removed days genuinely bad (below the 5th percentile of random same-count day sets) — but positive years 8 vs 9, so the strict
  pre-registered gate fails by one year. Judgement (Devin's discretion per Nick 2026-11-09): deployed as `ag_all_weather_v2` beside v1 — the champion's own
  training DD breaches the $2k floor and the filter removes exactly that kind of day.
- Nothing scored on 2024–26.

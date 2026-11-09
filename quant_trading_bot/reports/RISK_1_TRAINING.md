# risk_1 — pause rules for Book A's overnight leg (training 2010–23 only)

Protocol research/risk_1/PROTOCOL.md; script scripts/risk_1_pilot.py; raw reports/RISK_1_TRAINING.json. Marked (intraday-trailing) DD by the book_1 method. 2024–26 not loaded.

| rule | closed net | retained | marked DD (when) | $2k touches | nights skipped |
|---|---|---|---|---|---|
| Book A as is | +28,317 | – | 2,043 (2020-03-17 18:05) | 1 | 0 |
| R1 skip rest of week after book week P&L ≤ −750 | +28,071 | 99.1 % | 2,043 | 1 | 1 |
| R2 … ≤ −1,000 | +28,071 | 99.1 % | 2,043 | 1 | 1 |
| R3 skip next night after 3 losing nights | +27,963 | 98.7 % | **2,207** | 1 | 19 |

## Verdict: 0 of 3 — no pause rule adopted
- The $2,043 is one night's intraday excursion inside a week that was not yet down $750 when the night was entered; weekly-loss pauses therefore cannot reach it.
- Streak pauses remove above-average nights (nights after three losses are the deep-dip nights the rule exists for) and raise the DD.
- Together with overnight_9 (stops) this closes risk-overlay work on the overnight leg: the floor overshoot is handled by cushion staging (portfolio_4/book_1), not by rules.

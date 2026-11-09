# sizing_3 — SKEW-state sizing (pre-registered 2026-11-09, after extstate_2)

Hypothesis (from extstate_2, chosen before any sizing was computed): both legs of book_a earn 3–4× more per contract when the prior CBOE close has
SKEW below its 20-day mean (state "below"). Test: 2 contracts in state "below", 1 otherwise. Costs scale per contract. Training 2010–23 only.

Legs: L1 overnight_dip_v2 nights (MNQ 18:05→09:45, MNQ+MES co-dip); L2 ag_all_weather_v2_1c days (training run, budget off); L3 book = L1 + L2 (no overlaps on training).
Also as a *control*: the same 2c sizing on the complementary state ("above"), which the hypothesis says must be worse.
Gates vs the 1c baseline of each leg: closed DD < 2,000 (book: also marked estimate = closed DD + the book_1 marked excess 410), positive years ≥ baseline,
max-year share ≤ 40 %, net per unit of DD higher than baseline, 1-year funded-breach probability (sizing_1 block-bootstrap) not above 2× baseline.
One variant only (SKEW < 20d mean); no threshold search. 2024–26 not loaded. Deploy only if book passes and Devin judges it worthwhile.

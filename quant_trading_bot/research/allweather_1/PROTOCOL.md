# allweather_1 — backwardation-day filter for ag_all_weather (pre-registered 2026-11-09; training 2010-2023; 2024-26 sealed)

From crabel_1: the All-Weather 30m breakout sleeve lost -925 on 41 backwardation days (prior CBOE close VIX > VIX3M); the 60m trend sleeve -80 on 52.
Hypothesis (one variant): ag_all_weather (1 MNQ 30m breakout lb8 th1.5 + 1 MNQ 60m EWMA trend lb12 th0.75, independent sleeves) stands aside on days after a
backwardation close. Engine default costs; sleeves run exactly as in the paper runner (ep.run_sleeve), signals masked on filtered days.
Gates: net > champion, closed DD (summed daily curve) <= champion DD, >= champion positive years, and the removed days' net must be below the 5th percentile of
20 same-count random-day sets drawn from the champion's trade days. One trial. If it passes, deploy as `ag_all_weather_v2` beside v1 (Devin's discretion). 2024-26 never scored.

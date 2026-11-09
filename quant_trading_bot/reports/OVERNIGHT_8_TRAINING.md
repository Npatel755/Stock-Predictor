# overnight_8 — Asia-session move as the signal for a 03:00 -> US-open hold (training 2010–23 only)

Protocol: research/overnight_8/PROTOCOL.md (pre-registered). Script: scripts/overnight_8_pilot.py. Raw: reports/OVERNIGHT_8_TRAINING.json.
MNQ/MES 1-min train split only; 2024–26 not loaded. Entry 03:00 ET open, exits 08:30 / 09:30 / 09:45, 1 contract, micro costs, 200 same-count placebos.

## Result: 0 of 24 long cells pass — closed
| best cells | net | nights | $/night | +years | 2010–19 | DD | placebos beaten (median placebo) |
|---|---|---|---|---|---|---|---|
| MNQ Asia ≤ −0.5σ, exit 09:45 | +2,946 | 733 | 4.0 | 10/14 | +839 | 2,605 | 189/200 (−1,719) |
| MES Asia ≤ −0.5σ, exit 09:45 | −47 | 823 | −0.1 | 9/14 | −741 | 2,170 | 195/200 (−3,408) |
| MES Asia ≤ −1σ, exit 09:45 | +543 | 400 | 1.4 | 7/14 | −9 | 1,568 | 187/200 (−1,849) |

- The 03:00 -> US-open window has a *negative* unconditional drift on both contracts (placebo medians −$1.7k to −$4.5k per 14 years), so
  "beating placebos" here only means an Asia sell-off avoids part of that drag; the selected nights themselves earn $0–4 — under one tick.
- Asia continuation (A3, Asia ≥ +0.5σ) is strongly negative on both contracts (−$3.8k to −$5.2k, 1–5 positive years): the European/premarket
  window fades the Asian move rather than continuing it, but not enough to pay micro costs.
- Excluding reopen-dip nights (A4) leaves nothing: the small MNQ A1 result is the dip nights already on paper.
- Short mirrors (sign-flipped longs, informational only) are all strongly negative; they were computed without the second cost deduction, so they are if anything flattered.

## Lesson
The overnight premium on dip nights accrues 20:00 -> 08:30 and is only accessible by being long from the reopen (overnight_3 attribution);
there is no separate European-session effect to trade at 03:00. Overnight entry-timing work is closed (18:05 / 18:30 / 20:00 / 03:00 all tested).
Not deployed; nothing scored on 2024–26.

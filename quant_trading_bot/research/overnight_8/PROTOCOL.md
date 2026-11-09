# overnight_8 — Asia-session move as the signal for a 03:05 -> US-open hold (pre-registered 2026-11-09)

## Motivation
overnight_3 showed the reopen-dip premium accrues 20:00->08:30 ET and that entering at 03:00 *on the reopen-gap signal* loses most of it.
Untested: a signal formed during the Asian session itself (18:05 -> 03:00 ET return), traded over the European/US-premarket window only.
Shorter hold (6.5 h, no weekend/Asia exposure) = bounded excursion; it is independent of the reopen gap by construction (A4 excludes dip nights).

## Data and separation
MNQ/MES 1-min, train 2010-01-01 … 2023-12-31 only (scripts/overnight_3_pilot.nights frame). 2024–26 not loaded.

## Variants (long; short mirrors are negative controls). Entry 03:00 ET open (+half spread, 1 tick slip), exit at 08:30 / 09:30 / 09:45 open.
A1 Asia return <= -0.5 sd20 (prior 20 nights)   A2 <= -1.0 sd20   A3 >= +0.5 sd20 (continuation)   A4 A1 and NOT reopen dip (gap > -0.5 sd20)
2 instruments x 4 signals x 3 exits = 24 long cells.  1 contract.  200 same-count-per-year random-night placebos per cell.

## Gate
net > 0, >= 100 nights, positive years >= 11/14, max-year share <= 40%, DD < $2,000, 2010–19 net > 0, beats >= 190/200 placebos,
coherent across exits (>= 2 of 3 exits pass for the same signal). Deployment at Devin's discretion beside existing ledgers. No 2024–26 scoring.

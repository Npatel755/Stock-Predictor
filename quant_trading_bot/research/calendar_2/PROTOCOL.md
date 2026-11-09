# calendar_2 — overnight calendar windows (pre-registered 2026-11-09)

## Motivation
calendar_1 found no *intraday* calendar edge (TOM / OPEX / month-end / weekday / pre-holiday, 0 of 62). The published turn-of-month and pre-holiday
premia in equity indices are, in the literature, mostly earned overnight (close-to-open), which calendar_1 did not test; overnight_1/5/6 tested
weekday, after-up/down day, VIX state, releases and FOMC nights but not TOM / pre-holiday / OPEX. This round asks whether an unconditional overnight
hold (no stop, 1 micro contract) earns more than random nights inside those windows. Base rate (overnight_1): the unconditional MNQ 18:05→09:30 hold
makes +$0.40/night, so a window must beat same-count random nights, not zero.

## Data and separation
MNQ/MES 1-min, train split 2010-01-01 … 2023-12-31 only (nights() from overnight_3_pilot.py, Friday-row fix included). 2024–26 not loaded.

## Day sets (taken verbatim from scripts/calendar_1_pilot.py daysets(): tom = last trading day of month + first 3; month_end; opex = 3rd-Friday;
pre_holiday = session before a CME holiday closure). A night belongs to a window if its *exit morning* (the next RTH session) is in the set,
except W4 where the entry evening's session is the pre-holiday day (the hold runs into the holiday-shortened/closed period, exit = next RTH open).

## Variants (hold long, entry 18:05 open, exit 09:30 open; 09:45 exit reported as secondary for comparison with overnight_dip_v2, not a decision input)
W1 nights into TOM days (MNQ, MES)         W2 nights into month-end day only       W3 nights into OPEX Friday
W4 nights out of the pre-holiday session   W5 W1 ∩ reopen dip (gap ≤ −0.5σ) — reported for overlap with the deployed rule, no gate
Short-side mirror of W1–W4 is reported (negative control: should not pass).

## Metrics / controls: evaluate() of overnight_3 — net, nights, $/night, positive years, 2010–19 net, max-year share, DD, worst night, by-year; 200
same-count-per-year random-night placebos.
## Pre-registered gate (same as overnight rounds): net > 0, ≥ 100 nights, positive years ≥ 11 of 14, max-year share ≤ 40 %, DD < $2,000, beats ≥ 190/200 placebos.
Passers go to paper as a new candidate only at Devin's discretion (Nick's standing rule). No 2024–26 look. Nothing is tuned: windows and exits are fixed above.

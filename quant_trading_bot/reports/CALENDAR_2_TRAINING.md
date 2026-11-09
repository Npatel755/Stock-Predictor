# calendar_2 — overnight calendar windows, training 2010–23 (2026-11-09): REJECTED, 0 of 4 windows

Protocol: research/calendar_2/PROTOCOL.md. Scripts: scripts/calendar_2_pilot.py, scripts/calendar_2_followup.py. Data: MNQ/MES 1-min train split only;
2024–26 not loaded. Hold = long 1 micro, 18:05 open → 09:30 open (09:45 reported), no stop, micro costs ($0.61/side, 1.75/1.0-tick spread, 1 tick slip).
Day sets verbatim from calendar_1 (tom = last session + first 3; month_end; opex 3rd Friday; pre_holiday = session before a CME closure).
Placebo = 200 same-count-per-year random nights. Gate: net > 0, ≥ 100 nights, ≥ 11/14 positive years, max-year share ≤ 40 %, DD < $2,000, ≥ 190/200.

| window (exit 09:30) | MNQ net / nights / $·night / +yrs / DD / beats | MES net / nights / $·night / +yrs / DD / beats | short mirror (MNQ, MES) |
|---|---|---|---|
| W1 nights into TOM days | +65 / 651 / 0.1 / 5 / 2,583 / 100 | −1,094 / 645 / −1.7 / 5 / 1,937 / 101 | −4,094, −5,317 |
| W2 nights into month-end day | −555 / 159 / −3.5 / 6 / 1,425 / 72 | −1,610 / 159 / −10.1 / 6 / 2,120 / 19 | −430, +30 |
| W3 nights into OPEX Friday | +824 / 143 / 5.8 / 8 / 900 / 136 | −40 / 157 / −0.3 / 7 / 1,002 / 108 | −1,709, −1,520 |
| W4 nights out of the pre-holiday session | +431 / 126 / 3.4 / 6 / 360 / 146 | −100 / 38 / −2.6 / 4 / 379 / 89 | −1,211, −278 |
| W5 TOM ∩ reopen dip (reported, no gate) | +2,536 / 134 / 18.9 / 11 / 938 / 196 | +948 / 140 / 6.8 / 8 / 583 / 173 | — |

Exit 09:45 changes nothing material (W1 MNQ −250, W2 −954, W3 −1,051, W4 +546; MES all ≤ +109 except W5).

## Reading
- There is no overnight turn-of-month, month-end, OPEX-eve or pre-holiday premium on MNQ/MES at micro costs in 2010–23: every window is inside
  its random-night band (19–146 of 200), both exits, both contracts. Short mirrors are negative as they should be. The published TOM/pre-holiday
  overnight effects do not survive 2010–23 index-futures costs at one-micro scale (or were never there in this period).
- W5 looks good (MNQ 11/14 years, 196/200 vs *all* nights) but the fair control is random same-count subsets of the *dip* nights it is drawn from:
  there it beats only 150/200 (09:30) and 130/200 (09:45) on MNQ, 92 and 72 on MES — i.e. it is the reopen-dip effect already on paper, with no
  calendar increment ($18.9 vs $15.0 per dip night on MNQ; MES $6.8 vs $6.7). Not a filter worth adding to `overnight_dip` / `_v2`.
- Nothing deployed. Calendar effects are now closed for both the intraday (calendar_1) and the overnight (this round) hold.

## Erratum on the first pass (same day, before any result was recorded)
The nights frame drops Friday sessions (no 18:00 reopen that evening), so a trading-day calendar built from it had no Fridays: OPEX came out empty,
Thursday→Friday nights were mapped to Monday, and every Thursday looked "pre-holiday". Fixed by recovering Friday sessions from Thursday nights that
exited at Friday 09:30 (scripts/calendar_2_pilot.py); only the corrected numbers are reported above. No decision was taken on the faulty pass.

# overnight_3 — reopen-dip hold improvement round (training 2010–2023 only; 2024–26 sealed)

Protocol: research/overnight_3/PROTOCOL.md (pre-registered before any run). Script: scripts/overnight_3_pilot.py. Raw: reports/OVERNIGHT_3_TRAINING.json.
Champion = `overnight_dip` v1.0.0 on paper: long 1 MNQ 18:05 → next 09:30 ET open when the 18:00 reopen gap ≤ −0.5 × sd of the previous 20 gaps.
Costs: spread 1.75 (MNQ) / 1.0 (MES) ticks, 1 tick slippage per side, $0.61/side. 200 same-per-year-count random-night placebos per variant.

## Erratum first: overnight_1 / overnight_2 measured Sunday gaps against Thursday's close
Rebuilding the night table for this round and diffing it against `overnight_1_pilot.nights()` showed 3,115 of 3,224 common nights with a different gap.
Cause: the old frame dropped rows without an 18:00 reopen (every Friday) *before* forward-filling the RTH close, so Sunday nights were compared with
Thursday's close (e.g. Sunday 2010-07-18: old gap −3.09 %, true gap vs Friday −0.10 %). Weekday nights differ only where the 15:59 bar is missing.
The paper runner uses the correct reference (Friday for Sunday), as does this round. Consequences:
- overnight_1 V9 / overnight_2 D0–D5, X, S, Q numbers are mis-measured for ~1/5 of nights (the Sunday ones) and are superseded by the table below.
- The one-shot 2024–25 validation of D5 was spent on the mis-measured rule; it stays spent — 2024–25 is not re-opened for this family.
- Correct champion (D4) on training: **+$9,327 / 620 nights / $15.0 per night / 12 of 14 years / max year 31 % / closed DD $1,963 / 200 of 200 placebos / 2010–19 +$3,549**
  (previously reported +$7,228 / 446 / DD $1,303). It passes every gate but the DD is $37 under the $2,000 floor.
Also: MNQ 1-min training data has no bars Jan–May 2019 (MNQ launch; NQ is used before 2019), so 2019 has 169 nights.

## Results (one change each vs D4; pass = beats the champion on net, DD ≤ 1.15× and per-night, plus the standard gates)
| variant | MNQ net | nights | $/night | +yrs | DD | placebo | 2010–19 | pass | MES net | nights | $/night | +yrs | DD | placebo | pass |
|---|---:|---:|---:|---:|---:|---:|---:|:-:|---:|---:|---:|---:|---:|---:|:-:|
| D4 champion (exit 09:30 open) | 9,327 | 620 | 15.0 | 12 | 1,963 | 200 | 3,549 | – | 4,888 | 725 | 6.7 | 13 | 1,953 | 200 | – |
| E1 exit 09:35 close | 11,770 | 619 | 19.0 | 12 | 1,907 | 200 | 4,646 | **yes** | 6,482 | 724 | 9.0 | 11 | 1,543 | 200 | **yes** |
| E2 exit 09:45 open | 11,507 | 619 | 18.6 | 13 | 1,770 | 199 | 4,595 | **yes** | 5,303 | 724 | 7.3 | 12 | 1,746 | 200 | **yes** |
| E3 exit 10:00 open | 12,537 | 619 | 20.3 | 12 | 2,053 | 200 | 4,965 | no (DD) | 5,163 | 725 | 7.1 | 12 | 2,443 | 199 | no (DD) |
| E4 exit 08:30 open | 8,972 | 617 | 14.5 | 12 | 1,815 | 200 | 3,591 | no | 5,178 | 721 | 7.2 | 12 | 1,422 | 200 | **yes** |
| E5 exit at gap fill | 3,140 | 620 | 5.1 | 8 | 2,382 | 200 | 1,614 | no | 1,262 | 725 | 1.7 | 5 | 2,084 | 200 | no |
| N1 entry 18:30 | 9,052 | 577 | 15.7 | 12 | 1,883 | 199 | 3,801 | no | 4,710 | 713 | 6.6 | 11 | 2,128 | 198 | no |
| N2 entry 20:00 | 8,676 | 611 | 14.2 | 11 | 1,759 | 200 | 2,609 | no | 4,345 | 724 | 6.0 | 8 | 1,929 | 200 | no |
| N3 entry 03:00 | 4,131 | 615 | 6.7 | 9 | 1,758 | 200 | −36 | no | 228 | 725 | 0.3 | 5 | 2,246 | 196 | no |
| G1 post-close drift ≤ −0.5 sd | 7,412 | 401 | 18.5 | 10 | 1,603 | 200 | 1,841 | no | 3,944 | 561 | 7.0 | 11 | 1,144 | 199 | no |
| G2 reopen jump ≤ −0.5 sd | 1,213 | 489 | 2.5 | 9 | 2,323 | 121 | 1,644 | no | 387 | 618 | 0.6 | 8 | 1,781 | 149 | no |
| Z1 gap ≤ −0.5 sd(daily c-c) | 2,773 | 102 | 27.2 | 9 | 1,134 | 197 | 1,311 | no | 2,161 | 122 | 17.7 | 9 | 1,556 | 199 | no |
| Z2 D4 & reopen < day low | 3,520 | 96 | 36.7 | 10 | 972 | 199 | 1,161 | no | 1,077 | 113 | 9.5 | 8 | 907 | 183 | no |
| Z3 D4 & RTH day down | 6,341 | 212 | 29.9 | 13 | 1,306 | 200 | 1,794 | no (net) | 1,793 | 236 | 7.6 | 10 | 810 | 192 | no |
| C1 D4 & MNQ gap < MES gap | 6,608 | 410 | 16.1 | 10 | 1,565 | 199 | 2,068 | no | – | | | | | | |
| C2 D4 & MES gap ≤ −0.5 sd | 9,632 | 491 | 19.6 | 11 | 1,804 | 200 | 3,904 | **yes** | – | | | | | | |
| K1 2 contracts when gap ≤ −1 sd | 13,763 | 620 | 22.2 | 11 | 3,103 | 200 | 5,493 | no (DD) | 7,973 | 725 | 11.0 | 10 | 3,761 | 199 | no (DD) |
| P1 MNQ D4 + MES D4 (1c each) | 14,215 | 854 | – | 12 | 3,776 | – | – | no (DD) | | | | | | | |

Pre-declared combination (all passing MNQ changes at once; E1 and E2 are alternative exits, the later-listed E2 applied):
**COMBO = D4 & MES dip, exit 09:45 open: +$11,797 / 490 nights / $24.1 per night / 12 of 14 years / max year 29 % / closed DD $1,646 / 200 of 200 placebos / 2010–19 +$4,969 — passes.**
Per year: 2010 −101 · 2011 −51 · 2012 +406 · 2013 +470 · 2014 +531 · 2015 +455 · 2016 +838 · 2017 +806 · 2018 +1,146 · 2019 +470 · 2020 +3,454 · 2021 +1,471 · 2022 +1,664 · 2023 +240 (see JSON).

## Attribution on D4 nights (ticks, mean / t)
MNQ: 18:05→20:00 +3.8 (0.9) · 20:00→03:00 +17.1 (2.6) · 03:00→08:30 +15.1 (2.0) · 08:30→09:30 +2.1 (0.5) · 09:30→09:35 +4.1 (1.0) · 09:35→10:00 +3.1.
MES: 20:00→03:00 +4.3 (2.5) · 03:00→08:30 +4.1 (2.2) · 09:30→09:35 +1.8 (2.5). The reversion accrues during the Asian and European sessions and
continues a few minutes into the US open; entering later (N1–N3) loses the first leg without a DD benefit.

## Reading
- Three single changes pass on MNQ (exit 09:35, exit 09:45, require an MES dip too); exits later than 09:45 add net but push DD past $2k.
- The gain is honest in kind: same nights, better exit; or fewer nights (broad dip), higher per-night. Nothing was selected on 2024–26.
- Multiplicity: 34 trials this round, 86 in the family; the 200/200 placebo and 12 positive years are well above what ~1.7 expected false passers
  would produce, but 2020 is still the largest year (29 %) and 2010–11 are flat.
- Verdict: **challenger accepted for paper only** → deploy as `overnight_dip_v2` (MNQ 1c, D4 & MES dip, 18:05 → 09:45 open, 16:05 safety flatten)
  beside v1.0.0; it must beat v1 forward on paper. Not validated; no live routing.

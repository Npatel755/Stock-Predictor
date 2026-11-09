# overnight_3 — improving the reopen-dip overnight hold (pre-registered 2026-11-09, before any run)

Champion (on paper as `overnight_dip` v1.0.0): long 1 MNQ 18:05 ET bar open -> next RTH 09:30 open on nights where the 18:00 reopen gap
(18:00 bar open / last 15:55-16:00 close - 1, Sunday vs Friday) is <= -0.5 x std of the previous 20 gaps. Training 2010-23: +7,228 / 446 nights /
11 of 14 years / DD 1,303 / 199 of 200 placebos / 2023 -417. Its sibling (<= -1.0 sd) failed the one-shot 2024-25 validation, so **2024-2025 and 2026
are sealed for this whole family**: nothing below is ever scored on them. Survivors go to paper as a new version (champion-challenger), not to validation.

Mechanism being probed: a down reopen into the thin 18:00 book mean-reverts into the US open, where the overnight premium also accrues. The
observed 09:35-vs-09:30 exit gain in overnight_2 (S2 > D0 by +3.5k on all dip nights) suggests the reversion continues into the first RTH minutes.

Fixed: products MNQ and MES (each evaluated separately), costs as overnight_1/2 (spread 1.75 / 1.0 ticks, 1 tick slippage per side, $0.61/side),
training 2010-2023 only, 200 same-per-year-count random-night placebos per variant, 1 contract unless stated. Baseline mask D4 = gap <= -0.5 sd20.
Variants (one change each vs D4; all reported, no post-hoc additions):
 Exit (entry 18:05, mask D4):   E1 exit 09:35 close   E2 exit 09:45 open   E3 exit 10:00 open   E4 exit 08:30 open   E5 exit at gap fill (first bar after
   entry whose high >= prior RTH close -> fill at that close level; else 09:30 open)
 Entry (exit 09:30, mask D4):   N1 entry 18:30 open   N2 entry 20:00 open   N3 entry 03:00 ET open (signal still the 18:00 gap)
 Gap decomposition (if 16:00-17:00 bars exist):  G1 post-close drift (16:59 close / 15:59 close - 1) <= -0.5 sd20   G2 reopen jump (18:00 open / 16:59 close - 1) <= -0.5 sd20
 Normalisation / shape:  Z1 gap <= -0.5 x std20 of daily close-to-close returns   Z2 D4 & reopen below the RTH day's low   Z3 D4 & RTH day down (= S3 on D4)
 Cross-market (MNQ only):  C1 D4 & MNQ gap < MES gap (tech-specific dip)   C2 D4 & MES gap <= -0.5 sd20 too (broad dip)
 Sizing / portfolio:  K1 1c on D4 nights, 2c when gap <= -1.0 sd20   P1 MNQ D4 + MES D4 simultaneously (1c each, summed curve)
Attribution (informational, not a variant): mean move in ticks on D4 nights over 18:05->20:00, 20:00->03:00, 03:00->08:30, 08:30->09:30, 09:30->09:35, 09:35->10:00.

Gates (training, to be called a challenger that beats the champion): net > champion net on the same product, >= 11 of 14 years, largest year <= 40% of
net, >= 100 nights, closed-equity max DD <= 1.15 x champion DD and < $2,000, >= 190 of 200 placebos, per-night net >= champion per-night (so the gain is
not from adding mediocre nights). Multiplicity: 16 variants x 2 products + 2 = 34 trials in this round (86 in the overnight family); expected false
"passers" at the 95% placebo gate ~1.7, so any single passer is reported as suggestive. Combination step (pre-declared): if >= 2 single-change variants
pass on MNQ, their combination is evaluated once as a final trial; no further search.
Promotion rule: a passing MNQ challenger is deployed as a second paper ledger (`overnight_dip_v2`) beside v1.0.0 — never replaces it — and must beat
v1 forward on paper before anything else is done with it. No live routing.

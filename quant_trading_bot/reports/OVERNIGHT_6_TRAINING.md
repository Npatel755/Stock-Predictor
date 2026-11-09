# overnight_6 — Sunday split and pre-FOMC drift (training 2010–2023; 2024–26 sealed) — no replacement for v2

Protocol: research/overnight_6/PROTOCOL.md. Script: scripts/overnight_6_pilot.py. Raw: reports/OVERNIGHT_6_TRAINING.json. Champion v2: +$11,797 / 490 nights / $24.1 per night / 12 of 14 years / DD $1,646.

| variant | net | nights | $/night | +yrs | DD | 2010–19 | t | placebo | gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| S1 v2 Sunday nights only | 3,335 | 137 | 24.3 | 10 | 925 | 805 | 1.8 | – | informational |
| S2 v2 weekday nights only | 8,462 | 353 | 24.0 | 12 | 1,781 | 4,164 | 3.0 | – | informational |
| F3 unconditional long, night before FOMC | 3,217 | 105 | 30.6 | 11 | 1,160 | 283 | 1.89 | 196/200 | fails t ≥ 2 (narrowly) |
| F4 v2 ∪ pre-FOMC nights | 12,364 | 578 | 21.4 | 12 | 1,510 | 5,025 | 3.43 | – | fails per-night ≥ champion |

## Reading
- Sunday and weekday dip nights earn the same per night ($24), so the edge is a general reopen-dip effect, not a weekend-gap effect; Sundays are just
  28 % of the nights with a smaller drawdown.
- The pre-FOMC overnight drift (Lucca–Moench) is visible — 105 nights, 11 of 14 years positive, beats 196 of 200 random same-count night sets — but
  2010–19 contributed only +$283 and t is 1.89; it is a real but small sleeve on a micro contract.
- Adding those nights to v2 raises net (+$566) and lowers DD ($1,510) but dilutes per-night, so by the pre-registered rule v2 stays as is. Judgement call:
  not deployed to paper either — the gain is 8 nights a year of a sub-$1k/decade effect; revisit only if the paper v2 holds up.

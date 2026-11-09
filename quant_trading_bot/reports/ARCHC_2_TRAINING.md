# archc_2 — stress-day exclusion for Architecture C and the combined book (training 2010–2023; 2024–26 sealed)

Protocol: research/archc_2/PROTOCOL.md. Script: scripts/archc_2_pilot.py. Raw: reports/ARCHC_2_TRAINING.json. Engine default costs (as portfolio_1). Champion: +$16,070 / 1,980 trades / 11 of 14 / DD $1,596.

| variant (prior-close state) | net | trades | $/trade | +yrs | 2010–19 | max yr | DD | days removed | removed net | random 5th pct | removed bad? | + overnight v2: DD / P(≥$2k, 1 yr) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:-:|---|
| champion | 16,070 | 1,980 | 8.1 | 11 | 5,050 | 42 % | 1,596 | – | – | – | – | 2,315 / 5.7 % |
| V1 skip VIX ≥ 25 | 14,776 | 1,824 | 8.1 | 12 | 5,954 | 39 % | 1,596 | 106 | +1,294 | −1,362 | no | 2,053 / 3.5 % |
| V2 skip VIX ≥ 30 | 16,803 | 1,922 | 8.7 | 12 | 5,512 | 40 % | 1,596 | 41 | −734 | −616 | yes | 2,053 / 4.1 % |
| **V3 skip backwardation (VIX > VIX3M)** | **17,291** | 1,886 | 9.2 | 12 | 6,102 | 39 % | 1,596 | 64 | **−1,221** | −274 | **yes** | 2,053 / 3.7 % |
| V4 skip VIX ≥ 25 or backwardation | 15,071 | 1,772 | 8.5 | 12 | 6,251 | 39 % | 1,596 | 140 | +999 | −509 | no | 2,053 / 3.0 % |

## Reading
- Pre-registered gates: 0 of 4 pass — every variant leaves the max drawdown untouched (the worst stretch is not a stress period), so DD ≤ 0.8 × champion fails.
- V3 is nevertheless a real improvement: the 64 backwardation days it removes lost −$1,221, below the 5th percentile of random same-count day sets; net, positive
  years, pre-2020 and the largest-year share all improve; the per-trade edge rises from $8.1 to $9.2. VIX-level gates remove mostly good days (V1, V4).
- Combined with overnight_dip_v2 the book's DD drops to $2,053 and one-year breach odds to ≈3.5–4 %; still $53 over a $2k floor — the staging rule in
  reports/PORTFOLIO_1_TRAINING.md stands.
- Decision (Devin's discretion per Nick 2026-11-09): deploy V3 as `ag_arch_c_v2` beside `ag_arch_c` — same sleeves, signals masked on days whose prior CBOE close had VIX > VIX3M. Paper only; 2024–26 never scored.

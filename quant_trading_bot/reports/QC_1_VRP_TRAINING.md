# qc_1 VRP Result: QuantConnect Strategy 25 (Variance Risk Premium) Pilot

Pre-registered in `research/qc_1/PROTOCOL.md`. Evaluated on training 2010-2023 (14 years).
Costs: $0.61/side, MNQ spread 1.75 ticks, MES spread 1.0 tick, slippage 1.0 tick/side.

## A. VRP Day Direction 09:45 -> 15:54 ET

| product | tercile | side | net | trades | +yrs/14 | placebo pct | placebo mean | passes |
|---|---|---|---:|---:|---:|---:|---:|:---:|
| MNQ | low | long | -4,712.67 | 1207 | 5 | 0.19 | -445.58 | FAIL |
| MNQ | low | short | -2,758.67 | 1207 | 5 | 0.79 | -6,414.63 | FAIL |
| MNQ | mid | long | -1,216.16 | 1149 | 4 | 0.44 | -450.14 | FAIL |
| MNQ | mid | short | -5,896.16 | 1149 | 1 | 0.51 | -6,108.76 | FAIL |
| MNQ | high | long | +3,423.79 | 939 | 7 | 0.79 | -844.41 | FAIL |
| MNQ | high | short | -9,236.21 | 939 | 1 | 0.16 | -4,804.53 | FAIL |
| MES | low | long | -5,658.79 | 1207 | 2 | 0.21 | -3,164.08 | FAIL |
| MES | low | short | -6,338.79 | 1207 | 3 | 0.80 | -8,865.89 | FAIL |
| MES | mid | long | -2,804.28 | 1149 | 5 | 0.48 | -2,542.74 | FAIL |
| MES | mid | short | -8,616.78 | 1149 | 1 | 0.41 | -8,115.23 | FAIL |
| MES | high | long | -231.83 | 939 | 8 | 0.84 | -2,490.09 | FAIL |
| MES | high | short | -9,101.83 | 939 | 1 | 0.26 | -7,311.00 | FAIL |

## B. VRP Filter on 15m Momentum Rule

| filter | net | trades | +yrs/14 | placebo pct | placebo mean | passes |
|---|---:|---:|---:|---:|---:|:---:|
| unfiltered | -18,672.80 | 5746 | 2 | - | - | FAIL |
| high_vrp_only | -9,180.07 | 1600 | 7 | 0.40 | -9,027.11 | FAIL |
| low_vrp_only | -3,297.35 | 2121 | 5 | 0.95 | -9,749.34 | FAIL |
| mid_vrp_only | -4,116.87 | 1958 | 2 | 0.90 | -9,822.06 | FAIL |

## Conclusion
QuantConnect Strategy 25 (Variance Risk Premium) empirical verdict recorded. Validation untouched.
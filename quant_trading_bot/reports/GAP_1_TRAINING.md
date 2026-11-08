# gap_1 training result (2026-11-08): overnight gap fade / gap-and-go / Globex-range break — 0 of 152 configs pass

Protocol research/gap_1/PROTOCOL.md (registered before the run). 15-min bars incl. Globex, ES/NQ 2010-18 + MES/MNQ 2019-23 at micro economics, $0.61/side, MNQ spread 1.75 ticks, annual $50k accounts, $2k funded rules. Gate: total>0, >=10/14 years positive, no year >40%, >=150 trades, beats 95% of 50 placebos. **Passers: none; validation 2024-25 not run; 2026 never loaded.**

## Family summary (A = gap fade, B = gap-and-go, C = Globex-range break)

| instrument | family | configs | net>0 | median 14y net | best net | best +years/14 | median trades |
|---|---|---:|---:|---:|---:|---:|---:|
| MES | A | 24 | 0 | -2,228 | -336 | 4 | 200 |
| MES | B | 36 | 21 | 141 | 1,932 | 9 | 139 |
| MES | C | 16 | 0 | -6,260 | -2,273 | 4 | 1,800 |
| MNQ | A | 24 | 0 | -1,898 | -802 | 3 | 160 |
| MNQ | B | 36 | 20 | 283 | 1,788 | 11 | 108 |
| MNQ | C | 16 | 0 | -2,993 | -912 | 4 | 2,121 |

## Best config per family

| instrument | family | th | stop | tgt | hold | 14y net | 2010-19 | 2020-23 | +years | trades | worst DD |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| MES | A | 1.5 | 1.0 | 2 | 4 | -336 | -332 | -4 | 3 | 48 | 385 |
| MES | B | 0.5 | 1.5 | 2 | 12 | 1,932 | -192 | 2,124 | 8 | 439 | 472 |
| MES | C | 0.25 | 1.5 | 3 | 12 | -2,273 | -4,414 | 2,141 | 4 | 1449 | 1,247 |
| MNQ | A | 1.5 | 1.0 | 1 | 4 | -802 | -232 | -570 | 3 | 37 | 497 |
| MNQ | B | 0.5 | 1.5 | 2 | 8 | 1,788 | -68 | 1,856 | 7 | 826 | 1,515 |
| MNQ | C | 0.25 | 1.5 | 3 | 12 | -912 | -2,499 | 1,587 | 3 | 1800 | 1,365 |

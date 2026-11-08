# mass_v2 training results (ES/NQ 2010-2023 as MES/MNQ, 1 contract, today's costs)

Configurations scored: 1,200,000 of 1,200,000 planned. G1-G3 passers: 74. G4 (beat placebo p95): 74. G5 (DSR > 0.95, N = 1,200,000): 0. Frozen for validation: 13.

| instrument | family | configs | G1-G3 | mean net | mean +years/14 | best net |
|---|---|---:|---:|---:|---:|---:|
| MES | breakout | 60,000 | 0 | -7,947 | 1.3 | 1,412 |
| MES | hybrid | 60,000 | 0 | -6,645 | 1.1 | 2,482 |
| MES | mean_reversion | 60,000 | 0 | -16,814 | 0.2 | 214 |
| MES | momentum | 60,000 | 0 | -9,429 | 1.5 | 2,516 |
| MES | opening_range | 60,000 | 0 | -14,442 | 0.7 | 0 |
| MES | regime | 60,000 | 0 | -12,607 | 1.0 | 2,820 |
| MES | trend | 60,000 | 0 | -12,023 | 1.1 | 3,274 |
| MES | volatility | 60,000 | 0 | -9,182 | 0.3 | 77 |
| MES | volume | 60,000 | 0 | -16,487 | 0.4 | 0 |
| MES | vwap | 60,000 | 0 | -15,374 | 0.3 | 0 |
| MNQ | breakout | 60,000 | 0 | -1,697 | 3.1 | 8,628 |
| MNQ | hybrid | 60,000 | 6 | -960 | 2.8 | 12,265 |
| MNQ | mean_reversion | 60,000 | 0 | -10,035 | 1.2 | 377 |
| MNQ | momentum | 60,000 | 2 | -1,877 | 3.8 | 15,988 |
| MNQ | opening_range | 60,000 | 0 | -4,749 | 3.0 | 9,063 |
| MNQ | regime | 60,000 | 8 | -3,467 | 3.2 | 12,094 |
| MNQ | trend | 60,000 | 58 | -3,005 | 3.7 | 17,754 |
| MNQ | volatility | 60,000 | 0 | -3,592 | 1.4 | 9,856 |
| MNQ | volume | 60,000 | 0 | -6,105 | 2.3 | 10,787 |
| MNQ | vwap | 60,000 | 0 | -9,029 | 1.2 | 0 |

| id | rule | net 14y | +yrs | worst DD | trades | placebo p95/trade | per trade | gross net | restated net | DSR |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v2_059ba4b78c402017 | MNQ trend lb8 th1.0 600-720 stop3.0 tgt1.5 hold12 trail2.0 | 2,098 | 11 | 593 | 351 | -0.2 | 6.0 | 3,289 | 2,754 | 0.00 |
| v2_7f233cc729959bec | MNQ trend lb8 th1.0 600-720 stop2.0 tgt2.0 hold12 trail0.0 | 3,947 | 10 | 607 | 436 | 0.5 | 9.1 | 5,044 | 4,449 | 0.00 |
| v2_0ae0b032ed010c57 | MNQ trend lb8 th1.0 600-720 stop2.0 tgt4.0 hold12 trail0.0 | 3,810 | 10 | 607 | 411 | 1.1 | 9.3 | 5,092 | 4,328 | 0.00 |
| v2_003a44cf40dd39e3 | MNQ trend lb8 th1.0 600-720 stop3.0 tgt2.0 hold16 trail0.0 | 1,750 | 11 | 625 | 343 | 0.6 | 5.1 | 3,208 | 2,473 | 0.00 |
| v2_247125c067b9e7e8 | MNQ regime lb32 th1.5 585-945 stop1.5 tgt2.0 hold8 trail2.0 | 1,956 | 10 | 693 | 552 | 0.3 | 3.5 | 4,048 | 3,045 | 0.00 |
| v2_00a0e6bbb52491a1 | MNQ regime lb24 th1.5 585-945 stop1.5 tgt3.0 hold16 trail2.0 | 4,637 | 10 | 933 | 987 | -0.1 | 4.7 | 7,990 | 5,871 | 0.00 |
| v2_0de3c8ecfd54a49f | MNQ hybrid lb8 th1.5 585-690 stop1.5 tgt3.0 hold16 trail2.0 | 4,358 | 10 | 850 | 657 | 1.0 | 6.6 | 6,138 | 5,264 | 0.00 |
| v2_a0d6c5a4585881f5 | MNQ regime lb24 th1.5 585-945 stop1.5 tgt1.5 hold16 trail2.0 | 4,742 | 10 | 919 | 1154 | -0.2 | 4.1 | 8,441 | 6,224 | 0.00 |
| v2_e27a54ff69f8be54 | MNQ regime lb24 th1.5 585-945 stop1.5 tgt4.0 hold16 trail2.0 | 4,618 | 10 | 933 | 956 | 0.6 | 4.8 | 7,988 | 5,844 | 0.00 |
| v2_a773e4e38ff9e3a5 | MNQ trend lb8 th1.0 585-945 stop3.0 tgt3.0 hold8 trail0.0 | 2,350 | 10 | 639 | 404 | -0.2 | 5.8 | 4,050 | 3,359 | 0.00 |
| v2_5b72691fb4182819 | MNQ regime lb24 th1.5 585-945 stop2.0 tgt1.5 hold16 trail0.0 | 4,856 | 10 | 944 | 934 | -0.7 | 5.2 | 7,460 | 5,845 | 0.00 |
| v2_ba974563ac9af3f9 | MNQ regime lb24 th1.5 585-945 stop1.5 tgt1.5 hold16 trail0.0 | 4,854 | 10 | 873 | 1147 | -0.4 | 4.2 | 8,648 | 6,291 | 0.00 |
| v2_25749881dc5389f1 | MNQ regime lb24 th1.5 585-945 stop2.0 tgt1.5 hold16 trail2.0 | 5,166 | 10 | 749 | 945 | 0.1 | 5.5 | 7,732 | 6,186 | 0.00 |

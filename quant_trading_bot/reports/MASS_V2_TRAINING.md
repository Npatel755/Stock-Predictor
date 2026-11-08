# mass_v2 training results (ES/NQ 2010-2023 as MES/MNQ, 1 contract, today's costs)

Configurations scored: 1,200,000 of 1,200,000 planned. G1-G3 passers: 74. G4 (beat placebo p95): 74. G5 (DSR > 0.95, N = 1,200,000): 0. Frozen for validation: 12.

| instrument | family | configs | G1-G3 | mean net | mean +years/14 | best net |
|---|---|---:|---:|---:|---:|---:|
| MES | breakout | 60,000 | 0 | -6,746 | 1.5 | 2,168 |
| MES | hybrid | 60,000 | 0 | -5,442 | 1.2 | 2,467 |
| MES | mean_reversion | 60,000 | 0 | -14,329 | 0.4 | 214 |
| MES | momentum | 60,000 | 0 | -7,353 | 1.7 | 2,517 |
| MES | opening_range | 60,000 | 0 | -10,600 | 1.0 | 0 |
| MES | regime | 60,000 | 0 | -9,587 | 1.3 | 2,212 |
| MES | trend | 60,000 | 0 | -9,487 | 1.3 | 3,330 |
| MES | volatility | 60,000 | 0 | -7,735 | 0.4 | 140 |
| MES | volume | 60,000 | 0 | -14,598 | 0.4 | 0 |
| MES | vwap | 60,000 | 0 | -12,697 | 0.5 | 0 |
| MNQ | breakout | 60,000 | 0 | -1,488 | 3.2 | 9,430 |
| MNQ | hybrid | 60,000 | 6 | -841 | 2.8 | 9,732 |
| MNQ | mean_reversion | 60,000 | 0 | -8,756 | 1.4 | 1,000 |
| MNQ | momentum | 60,000 | 5 | -1,644 | 3.8 | 10,815 |
| MNQ | opening_range | 60,000 | 0 | -4,211 | 3.1 | 5,498 |
| MNQ | regime | 60,000 | 5 | -2,918 | 3.3 | 9,125 |
| MNQ | trend | 60,000 | 58 | -2,510 | 3.8 | 9,759 |
| MNQ | volatility | 60,000 | 0 | -3,099 | 1.5 | 5,169 |
| MNQ | volume | 60,000 | 0 | -5,569 | 2.4 | 7,000 |
| MNQ | vwap | 60,000 | 0 | -7,844 | 1.4 | 294 |

| id | rule | net 14y | +yrs | worst DD | trades | placebo p95/trade | per trade | gross net | restated net | DSR |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v2_059ba4b78c402017 | MNQ trend lb8 th1.0 600-720 stop3.0 tgt1.5 hold12 trail2.0 | 2,098 | 11 | 593 | 351 | -0.2 | 6.0 | 3,289 | 2,754 | 0.00 |
| v2_7f233cc729959bec | MNQ trend lb8 th1.0 600-720 stop2.0 tgt2.0 hold12 trail0.0 | 3,947 | 10 | 607 | 436 | 0.5 | 9.1 | 5,044 | 4,449 | 0.00 |
| v2_0ae0b032ed010c57 | MNQ trend lb8 th1.0 600-720 stop2.0 tgt4.0 hold12 trail0.0 | 3,810 | 10 | 607 | 411 | 1.1 | 9.3 | 5,092 | 4,328 | 0.00 |
| v2_003a44cf40dd39e3 | MNQ trend lb8 th1.0 600-720 stop3.0 tgt2.0 hold16 trail0.0 | 1,750 | 11 | 625 | 343 | 0.6 | 5.1 | 3,208 | 2,473 | 0.00 |
| v2_89e8cbeecf2b6d87 | MNQ trend lb8 th1.0 585-945 stop3.0 tgt1.0 hold8 trail0.0 | 2,710 | 11 | 489 | 413 | -1.6 | 6.6 | 4,108 | 3,478 | 0.00 |
| v2_082adc9cd78f572a | MNQ hybrid lb8 th1.5 585-690 stop1.5 tgt3.0 hold8 trail0.0 | 4,002 | 10 | 860 | 656 | 0.3 | 6.1 | 5,774 | 4,916 | 0.00 |
| v2_0de3c8ecfd54a49f | MNQ hybrid lb8 th1.5 585-690 stop1.5 tgt3.0 hold16 trail2.0 | 4,358 | 10 | 850 | 657 | -0.8 | 6.6 | 6,138 | 5,264 | 0.00 |
| v2_5b72691fb4182819 | MNQ regime lb24 th1.5 585-945 stop2.0 tgt1.5 hold16 trail0.0 | 4,482 | 10 | 944 | 813 | -1.0 | 5.5 | 6,774 | 5,316 | 0.00 |
| v2_7fc3a039165ff2f6 | MNQ regime lb24 th1.5 585-945 stop2.0 tgt3.0 hold16 trail0.0 | 4,864 | 10 | 944 | 744 | -1.0 | 6.5 | 7,074 | 5,689 | 0.00 |
| v2_8320c24d0bd42a4e | MNQ regime lb24 th1.5 585-945 stop2.0 tgt4.0 hold16 trail0.0 | 4,831 | 10 | 944 | 741 | 0.4 | 6.5 | 7,139 | 5,740 | 0.00 |
| v2_25749881dc5389f1 | MNQ regime lb24 th1.5 585-945 stop2.0 tgt1.5 hold16 trail2.0 | 4,448 | 10 | 664 | 833 | 0.2 | 5.3 | 6,708 | 5,314 | 0.00 |
| v2_84592d1c4df1061e | MNQ regime lb24 th1.5 585-945 stop2.0 tgt2.0 hold16 trail0.0 | 4,911 | 10 | 944 | 773 | 0.4 | 6.4 | 7,153 | 5,758 | 0.00 |

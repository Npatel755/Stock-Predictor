# mass_v2 training analysis (1,200,000 configurations, ES/NQ 2010-2023 as MES/MNQ, 1 contract, today's costs)

| gate | configs passing | share |
|---|---:|---:|
| G1_net_pos | 108,242 | 9.02% |
| G1_years10 | 1,157 | 0.10% |
| G2_dd1k | 431,473 | 35.96% |
| G3_trades140 | 953,655 | 79.47% |
| G3_topyear40 | 4,245 | 0.35% |
| all G1-G3 | 74 | 0.006% |

## Years positive (of 14) across all configurations

| +years | configs |
|---|---:|
| 13 | 3 |
| 12 | 21 |
| 11 | 124 |
| 10 | 1,009 |
| 9 | 3,520 |
| 8 | 9,709 |
| 7 | 21,488 |
| 6 | 40,169 |
| 5 | 66,553 |
| 4 | 103,645 |
| 3 | 138,639 |
| 2 | 161,792 |
| 1 | 193,012 |
| 0 | 460,316 |

## Positive-net configurations by instrument and family

| instrument | family | configs | net>0 | +years>=10 | best net | best +years |
|---|---|---:|---:|---:|---:|---:|
| MES | breakout | 60,000 | 138 | 0 | 2,168 | 8 |
| MES | hybrid | 60,000 | 3,053 | 128 | 2,467 | 11 |
| MES | mean_reversion | 60,000 | 29 | 0 | 214 | 7 |
| MES | momentum | 60,000 | 5,399 | 23 | 2,517 | 11 |
| MES | opening_range | 60,000 | 0 | 0 | 0 | 5 |
| MES | regime | 60,000 | 1,472 | 0 | 2,212 | 8 |
| MES | trend | 60,000 | 1,104 | 2 | 3,330 | 10 |
| MES | volatility | 60,000 | 30 | 0 | 140 | 7 |
| MES | volume | 60,000 | 0 | 0 | 0 | 6 |
| MES | vwap | 60,000 | 0 | 0 | 0 | 6 |
| MNQ | breakout | 60,000 | 15,599 | 0 | 9,430 | 9 |
| MNQ | hybrid | 60,000 | 17,475 | 63 | 9,732 | 10 |
| MNQ | mean_reversion | 60,000 | 125 | 0 | 1,000 | 7 |
| MNQ | momentum | 60,000 | 22,994 | 343 | 10,815 | 11 |
| MNQ | opening_range | 60,000 | 2,310 | 0 | 5,498 | 7 |
| MNQ | regime | 60,000 | 15,193 | 93 | 9,125 | 11 |
| MNQ | trend | 60,000 | 18,181 | 501 | 9,759 | 13 |
| MNQ | volatility | 60,000 | 1,651 | 2 | 5,169 | 10 |
| MNQ | volume | 60,000 | 3,421 | 2 | 7,000 | 10 |
| MNQ | vwap | 60,000 | 68 | 0 | 294 | 8 |

## MES: nearest misses (unique trade fingerprints; research-only, none passed the gate)

| rule | net 14y | +yrs | worst DD | trades | $/trade | top-year share | best year | failed |
|---|---:|---:|---:|---:|---:|---:|---|---|
| momentum lb16 th1.5 600-720 stop2.0 tgt1.0 hold8 trail1.0 | 700 | 11 | 214 | 142 | 4.9 | 0.68 | 2022 (478) | G3_topyear40 |
| hybrid lb32 th1.5 585-945 stop3.0 tgt2.0 hold8 trail0.0 | 375 | 11 | 523 | 135 | 2.8 | 1.48 | 2022 (556) | G3_trades140, G3_topyear40 |
| hybrid lb32 th1.5 585-945 stop3.0 tgt1.0 hold8 trail0.0 | 317 | 11 | 493 | 137 | 2.3 | 1.34 | 2022 (424) | G3_trades140, G3_topyear40 |
| hybrid lb32 th1.5 585-945 stop3.0 tgt1.5 hold8 trail0.0 | 305 | 11 | 523 | 135 | 2.3 | 1.59 | 2022 (486) | G3_trades140, G3_topyear40 |
| trend lb16 th1.0 585-945 stop3.0 tgt4.0 hold16 trail2.0 | 1,222 | 10 | 826 | 662 | 1.8 | 0.74 | 2022 (909) | G3_topyear40 |
| trend lb16 th1.0 585-945 stop3.0 tgt3.0 hold16 trail2.0 | 1,189 | 10 | 826 | 662 | 1.8 | 0.82 | 2022 (972) | G3_topyear40 |
| momentum lb16 th1.5 600-720 stop2.0 tgt1.5 hold8 trail0.0 | 1,008 | 10 | 263 | 129 | 7.8 | 0.75 | 2022 (759) | G3_trades140, G3_topyear40 |
| momentum lb16 th1.5 600-720 stop3.0 tgt1.5 hold8 trail1.0 | 797 | 10 | 205 | 119 | 6.7 | 0.65 | 2022 (517) | G3_trades140, G3_topyear40 |
| hybrid lb16 th1.5 585-690 stop2.0 tgt1.0 hold8 trail1.0 | 788 | 10 | 169 | 129 | 6.1 | 0.64 | 2022 (504) | G3_trades140, G3_topyear40 |
| hybrid lb16 th1.5 585-690 stop2.0 tgt1.0 hold4 trail0.0 | 703 | 10 | 262 | 127 | 5.5 | 0.54 | 2022 (382) | G3_trades140, G3_topyear40 |
| hybrid lb16 th1.5 585-690 stop2.0 tgt1.0 hold4 trail1.0 | 682 | 10 | 169 | 130 | 5.2 | 0.71 | 2022 (486) | G3_trades140, G3_topyear40 |
| hybrid lb32 th1.0 600-720 stop1.5 tgt3.0 hold8 trail0.0 | 677 | 10 | 710 | 188 | 3.6 | 0.78 | 2020 (525) | G3_topyear40 |

## MNQ: nearest misses (unique trade fingerprints; research-only, none passed the gate)

| rule | net 14y | +yrs | worst DD | trades | $/trade | top-year share | best year | failed |
|---|---:|---:|---:|---:|---:|---:|---|---|
| trend lb16 th1.0 600-720 stop1.5 tgt4.0 hold8 trail2.0 | 3,634 | 13 | 795 | 493 | 7.4 | 0.47 | 2021 (1,708) | G3_topyear40 |
| trend lb16 th1.0 600-720 stop1.5 tgt4.0 hold8 trail1.0 | 3,375 | 12 | 728 | 575 | 5.9 | 0.40 | 2022 (1,337) |  |
| trend lb16 th1.0 600-720 stop1.5 tgt3.0 hold8 trail2.0 | 3,280 | 12 | 795 | 501 | 6.5 | 0.52 | 2021 (1,696) | G3_topyear40 |
| trend lb16 th1.0 600-720 stop1.5 tgt4.0 hold4 trail0.0 | 2,898 | 12 | 737 | 593 | 4.9 | 0.47 | 2021 (1,360) | G3_topyear40 |
| trend lb16 th1.0 600-720 stop1.5 tgt2.0 hold8 trail2.0 | 2,891 | 12 | 796 | 546 | 5.3 | 0.53 | 2021 (1,516) | G3_topyear40 |
| trend lb16 th1.0 600-720 stop1.5 tgt3.0 hold4 trail0.0 | 2,886 | 12 | 737 | 593 | 4.9 | 0.49 | 2021 (1,408) | G3_topyear40 |
| trend lb16 th1.0 600-720 stop1.5 tgt4.0 hold4 trail2.0 | 2,852 | 12 | 760 | 596 | 4.8 | 0.48 | 2021 (1,360) | G3_topyear40 |
| trend lb16 th1.0 600-720 stop1.5 tgt2.0 hold8 trail0.0 | 2,780 | 12 | 796 | 542 | 5.1 | 0.51 | 2021 (1,417) | G3_topyear40 |
| trend lb16 th1.0 600-720 stop2.0 tgt1.5 hold8 trail0.0 | 2,215 | 12 | 1,038 | 478 | 4.6 | 0.44 | 2022 (978) | G2_dd1k, G3_topyear40 |
| trend lb16 th1.0 600-720 stop2.0 tgt1.5 hold8 trail2.0 | 2,146 | 12 | 1,016 | 481 | 4.5 | 0.45 | 2021 (958) | G2_dd1k, G3_topyear40 |
| trend lb16 th0.75 600-720 stop2.0 tgt4.0 hold8 trail0.0 | 5,751 | 11 | 1,046 | 943 | 6.1 | 0.38 | 2021 (2,202) | G2_dd1k |
| trend lb16 th0.75 600-720 stop2.0 tgt3.0 hold8 trail0.0 | 5,611 | 11 | 959 | 954 | 5.9 | 0.39 | 2021 (2,173) |  |

Among the 108,242 net-positive configurations, the 2020 year supplies a median 15% of total 14-year profit (2020 is the year the earlier 2020-2023 searches weighted most).

# mass_v2 training analysis (1,200,000 configurations, ES/NQ 2010-2023 as MES/MNQ, 1 contract, today's costs; bar rule: lenient)

| gate | configs passing | share |
|---|---:|---:|
| G1_net_pos | 71,711 | 5.98% |
| G1_years10 | 2,649 | 0.22% |
| G2_dd1k | 423,620 | 35.30% |
| G3_trades140 | 963,752 | 80.31% |
| G3_topyear40 | 1,708 | 0.14% |
| all G1-G3 | 447 | 0.037% |

## Years positive (of 14) across all configurations

| +years | configs |
|---|---:|
| 12 | 68 |
| 11 | 503 |
| 10 | 2,078 |
| 9 | 5,284 |
| 8 | 10,608 |
| 7 | 18,155 |
| 6 | 32,529 |
| 5 | 55,493 |
| 4 | 95,787 |
| 3 | 133,393 |
| 2 | 163,105 |
| 1 | 194,132 |
| 0 | 488,865 |

## Positive-net configurations by instrument and family

| instrument | family | configs | net>0 | +years>=10 | best net | best +years |
|---|---|---:|---:|---:|---:|---:|
| MES | breakout | 60,000 | 0 | 0 | 0 | 7 |
| MES | hybrid | 60,000 | 1,556 | 22 | 2,494 | 10 |
| MES | mean_reversion | 60,000 | 29 | 0 | 214 | 7 |
| MES | momentum | 60,000 | 2,906 | 22 | 2,456 | 10 |
| MES | opening_range | 60,000 | 0 | 0 | 0 | 5 |
| MES | regime | 60,000 | 383 | 0 | 1,982 | 9 |
| MES | trend | 60,000 | 868 | 0 | 3,178 | 9 |
| MES | volatility | 60,000 | 30 | 0 | 290 | 7 |
| MES | volume | 60,000 | 0 | 0 | 0 | 6 |
| MES | vwap | 60,000 | 0 | 0 | 0 | 6 |
| MNQ | breakout | 60,000 | 10,156 | 2 | 6,716 | 11 |
| MNQ | hybrid | 60,000 | 11,418 | 612 | 8,963 | 12 |
| MNQ | mean_reversion | 60,000 | 149 | 0 | 377 | 9 |
| MNQ | momentum | 60,000 | 17,773 | 963 | 10,812 | 12 |
| MNQ | opening_range | 60,000 | 3,544 | 0 | 6,360 | 8 |
| MNQ | regime | 60,000 | 9,933 | 479 | 8,492 | 11 |
| MNQ | trend | 60,000 | 12,152 | 549 | 9,700 | 12 |
| MNQ | volatility | 60,000 | 236 | 0 | 3,745 | 8 |
| MNQ | volume | 60,000 | 578 | 0 | 5,936 | 9 |
| MNQ | vwap | 60,000 | 0 | 0 | 0 | 7 |

## MES: nearest misses (unique trade fingerprints; research-only, none passed the gate)

| rule | net 14y | +yrs | worst DD | trades | $/trade | top-year share | best year | failed |
|---|---:|---:|---:|---:|---:|---:|---|---|
| hybrid lb16 th1.5 600-720 stop2.0 tgt1.5 hold8 trail0.0 | 974 | 10 | 317 | 137 | 7.1 | 0.78 | 2022 (759) | G3_trades140, G3_topyear40 |
| momentum lb16 th1.5 600-720 stop2.0 tgt1.5 hold8 trail0.0 | 972 | 10 | 317 | 138 | 7.0 | 0.78 | 2022 (759) | G3_trades140, G3_topyear40 |
| hybrid lb16 th1.5 600-720 stop3.0 tgt1.5 hold8 trail0.0 | 772 | 10 | 424 | 123 | 6.3 | 0.65 | 2022 (498) | G3_trades140, G3_topyear40 |
| momentum lb16 th1.5 600-720 stop3.0 tgt1.5 hold8 trail0.0 | 770 | 10 | 424 | 124 | 6.2 | 0.65 | 2022 (498) | G3_trades140, G3_topyear40 |
| hybrid lb16 th1.5 600-720 stop3.0 tgt3.0 hold8 trail0.0 | 689 | 10 | 470 | 115 | 6.0 | 0.72 | 2022 (496) | G3_trades140, G3_topyear40 |
| momentum lb16 th1.5 600-720 stop3.0 tgt3.0 hold8 trail0.0 | 686 | 10 | 470 | 116 | 5.9 | 0.72 | 2022 (496) | G3_trades140, G3_topyear40 |
| hybrid lb16 th1.5 600-720 stop3.0 tgt2.0 hold8 trail0.0 | 686 | 10 | 470 | 116 | 5.9 | 0.81 | 2022 (554) | G3_trades140, G3_topyear40 |
| momentum lb16 th1.5 600-720 stop3.0 tgt2.0 hold8 trail0.0 | 684 | 10 | 470 | 117 | 5.8 | 0.81 | 2022 (554) | G3_trades140, G3_topyear40 |
| hybrid lb16 th1.5 600-720 stop2.0 tgt1.0 hold8 trail1.0 | 656 | 10 | 268 | 151 | 4.3 | 0.73 | 2022 (478) | G3_topyear40 |
| momentum lb16 th1.5 600-720 stop2.0 tgt1.0 hold8 trail1.0 | 652 | 10 | 268 | 152 | 4.3 | 0.73 | 2022 (478) | G3_topyear40 |
| hybrid lb16 th1.5 600-720 stop2.0 tgt1.0 hold4 trail1.0 | 521 | 10 | 236 | 159 | 3.3 | 0.69 | 2021 (362) | G3_topyear40 |
| momentum lb16 th1.5 600-720 stop2.0 tgt1.0 hold4 trail1.0 | 516 | 10 | 236 | 160 | 3.2 | 0.70 | 2021 (362) | G3_topyear40 |

## MNQ: nearest misses (unique trade fingerprints; research-only, none passed the gate)

| rule | net 14y | +yrs | worst DD | trades | $/trade | top-year share | best year | failed |
|---|---:|---:|---:|---:|---:|---:|---|---|
| trend lb8 th0.75 585-945 stop3.0 tgt2.0 hold8 trail2.0 | 4,137 | 12 | 714 | 1102 | 3.8 | 0.52 | 2021 (2,164) | G3_topyear40 |
| momentum lb64 th0.75 600-720 stop1.5 tgt4.0 hold8 trail0.0 | 3,612 | 12 | 901 | 556 | 6.5 | 0.49 | 2021 (1,756) | G3_topyear40 |
| momentum lb64 th0.75 600-720 stop1.5 tgt3.0 hold8 trail0.0 | 3,480 | 12 | 901 | 573 | 6.1 | 0.53 | 2021 (1,834) | G3_topyear40 |
| momentum lb16 th1.5 600-720 stop1.0 tgt4.0 hold8 trail0.0 | 3,125 | 12 | 462 | 267 | 11.7 | 0.46 | 2022 (1,426) | G3_topyear40 |
| momentum lb48 th1.0 585-690 stop1.5 tgt3.0 hold8 trail2.0 | 2,895 | 12 | 648 | 356 | 8.1 | 0.58 | 2022 (1,683) | G3_topyear40 |
| momentum lb48 th1.0 585-690 stop1.5 tgt3.0 hold8 trail0.0 | 2,838 | 12 | 598 | 352 | 8.1 | 0.55 | 2022 (1,574) | G3_topyear40 |
| momentum lb48 th1.0 585-690 stop1.5 tgt4.0 hold8 trail2.0 | 2,738 | 12 | 648 | 333 | 8.2 | 0.54 | 2022 (1,472) | G3_topyear40 |
| momentum lb48 th1.0 585-690 stop1.5 tgt4.0 hold8 trail0.0 | 2,700 | 12 | 598 | 329 | 8.2 | 0.52 | 2022 (1,408) | G3_topyear40 |
| hybrid lb32 th1.0 585-690 stop1.5 tgt1.5 hold4 trail2.0 | 2,424 | 12 | 424 | 467 | 5.2 | 0.37 | 2021 (890) |  |
| momentum lb48 th1.0 585-690 stop2.0 tgt4.0 hold8 trail2.0 | 2,125 | 12 | 855 | 298 | 7.1 | 0.39 | 2020 (828) |  |
| momentum lb48 th1.0 585-690 stop2.0 tgt3.0 hold8 trail2.0 | 2,044 | 12 | 855 | 306 | 6.7 | 0.42 | 2021 (856) | G3_topyear40 |
| momentum lb48 th1.0 585-690 stop2.0 tgt4.0 hold8 trail0.0 | 1,996 | 12 | 765 | 292 | 6.8 | 0.40 | 2021 (806) | G3_topyear40 |

Among the 71,711 net-positive configurations, the 2020 year supplies a median 13% of total 14-year profit (2020 is the year the earlier 2020-2023 searches weighted most).

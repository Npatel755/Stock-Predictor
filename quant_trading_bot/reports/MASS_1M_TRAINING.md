# mass_1m training result (1-minute counter-trend search, research/mass_1m/PROTOCOL.md) - 2026-11-08

**198,720 configurations (6 fade families x 1/3/5-min bars x MES/MNQ, ES/NQ 2010-18 + MES/MNQ 2019-23 at micro costs, 1 contract, early-close fix): 0 pass G1-G3.**
No candidate was frozen; validation (MES/MNQ 2024-25) was NOT run and remains unexposed for this family.
Net-positive after costs: 4,225 (2.1%); >=10 of 14 years positive: 27; none meets all of >=10 +yrs, >=140 trades, worst-yr DD<$1k, top-year share<=40%.

## Per family / resolution
| inst | family | res | configs | net>0 | median net 14y | best net | max +yrs | median trades |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| MES | keltner_fade | 1 | 5,760 | 0 | -27,794 | -1,246 | 4 | 4,284 |
| MES | keltner_fade | 3 | 5,760 | 4 | -25,954 | 95 | 5 | 3,718 |
| MES | keltner_fade | 5 | 5,760 | 48 | -19,947 | 98 | 3 | 3,015 |
| MES | orb_fade | 1 | 4,320 | 3 | -5,133 | 173 | 9 | 825 |
| MES | orb_fade | 3 | 4,320 | 217 | -1,799 | 531 | 9 | 294 |
| MES | orb_fade | 5 | 4,320 | 227 | -928 | 612 | 9 | 176 |
| MES | rsi_extreme | 1 | 5,760 | 328 | -24,092 | 594 | 8 | 4,031 |
| MES | rsi_extreme | 3 | 5,760 | 202 | -16,353 | 337 | 8 | 2,588 |
| MES | rsi_extreme | 5 | 5,760 | 76 | -14,855 | 192 | 9 | 2,134 |
| MES | stretch_fade | 1 | 5,760 | 0 | -27,848 | -20,542 | 1 | 4,421 |
| MES | stretch_fade | 3 | 5,760 | 0 | -27,540 | -8,142 | 1 | 4,058 |
| MES | stretch_fade | 5 | 5,760 | 0 | -26,980 | -5,097 | 1 | 3,914 |
| MES | volume_exhaustion | 1 | 5,760 | 0 | -27,859 | -9,290 | 2 | 4,442 |
| MES | volume_exhaustion | 3 | 5,760 | 0 | -25,664 | -1,316 | 5 | 4,010 |
| MES | volume_exhaustion | 5 | 5,760 | 0 | -23,044 | -594 | 8 | 3,498 |
| MES | vwap_snapback | 1 | 5,760 | 0 | -27,891 | -24,722 | 0 | 4,399 |
| MES | vwap_snapback | 3 | 5,760 | 0 | -27,620 | -9,160 | 0 | 3,928 |
| MES | vwap_snapback | 5 | 5,760 | 0 | -26,543 | -2,916 | 1 | 3,602 |
| MNQ | keltner_fade | 1 | 5,760 | 0 | -26,110 | -602 | 4 | 7,950 |
| MNQ | keltner_fade | 3 | 5,760 | 2 | -16,315 | 356 | 8 | 4,556 |
| MNQ | keltner_fade | 5 | 5,760 | 53 | -10,899 | 638 | 5 | 2,931 |
| MNQ | orb_fade | 1 | 4,320 | 202 | -1,892 | 798 | 10 | 618 |
| MNQ | orb_fade | 3 | 4,320 | 780 | -526 | 1,936 | 10 | 255 |
| MNQ | orb_fade | 5 | 4,320 | 1309 | -198 | 2,943 | 10 | 164 |
| MNQ | rsi_extreme | 1 | 5,760 | 292 | -17,537 | 397 | 10 | 5,226 |
| MNQ | rsi_extreme | 3 | 5,760 | 315 | -13,584 | 621 | 9 | 2,935 |
| MNQ | rsi_extreme | 5 | 5,760 | 167 | -11,571 | 200 | 8 | 2,470 |
| MNQ | stretch_fade | 1 | 5,760 | 0 | -27,050 | -12,546 | 2 | 8,576 |
| MNQ | stretch_fade | 3 | 5,760 | 0 | -25,415 | -5,238 | 2 | 6,713 |
| MNQ | stretch_fade | 5 | 5,760 | 0 | -22,102 | -2,742 | 4 | 5,700 |
| MNQ | volume_exhaustion | 1 | 5,760 | 0 | -25,659 | -2,916 | 4 | 8,136 |
| MNQ | volume_exhaustion | 3 | 5,760 | 0 | -16,208 | -246 | 5 | 4,478 |
| MNQ | volume_exhaustion | 5 | 5,760 | 0 | -12,810 | -76 | 6 | 3,322 |
| MNQ | vwap_snapback | 1 | 5,760 | 0 | -27,332 | -16,741 | 2 | 8,303 |
| MNQ | vwap_snapback | 3 | 5,760 | 0 | -25,595 | -7,770 | 2 | 6,422 |
| MNQ | vwap_snapback | 5 | 5,760 | 0 | -19,820 | -2,012 | 3 | 4,864 |

## Read
- VWAP snap-back, stretch fade, volume exhaustion and Keltner fade fire 3,000-8,500 times in 14 years and lose about one micro round-trip of costs per trade at every resolution: the snap-back exists but is smaller than spread+slippage+commission on MES/MNQ.
- The only family with positive nets is the MNQ opening-range fade (~120-900 trades). Best config (orb_fade_r5 lb15 th1.0 585-690 stop1.0 tgt2.0 hold6): net 2,943, 5/14 +yrs, annual [17.0, -106.5, -31.0, -103.0, -20.5, -93.5, -306.0, -105.0, -5.5, -52.0, 972.5, 334.5, 1492.0, 950.0] - every 2010-19 year flat/negative, all profit 2020-23 (same regime signature as the 15-min trend rules).
- Most consistent config (orb_fade_r3 lb15 th1.5 585-690 stop3.0 tgt2.0 hold40): net 1,936, 10/14 +yrs, 358 trades, $5.41/trade, top-year share 0.52 (fails the 40% rule).
- Conclusion: with 1-min OHLCV + volume and today's micro costs there is no 1-5 minute counter-trend leg for the orthogonal pair; the next evidence class is order-flow (trade imbalance / book) data or the forward paper ledger.

## Pipeline report (auto-generated)
# mass_v2 training results (ES/NQ 2010-2023 as MES/MNQ, 1 contract, today's costs)

Configurations scored: 198,720 of 198,720 planned. G1-G3 passers: 0. G4 (beat placebo p95): 0. G5 (DSR > 0.95, N = 198,720): 0. Frozen for validation: 0.

| instrument | family | configs | G1-G3 | mean net | mean +years/14 | best net |
|---|---|---:|---:|---:|---:|---:|
| MES | keltner_fade_r1 | 5,760 | 0 | -25,450 | 0.0 | -1,246 |
| MES | keltner_fade_r3 | 5,760 | 0 | -21,397 | 0.2 | 95 |
| MES | keltner_fade_r5 | 5,760 | 0 | -17,973 | 0.2 | 98 |
| MES | orb_fade_r1 | 4,320 | 0 | -8,115 | 0.5 | 173 |
| MES | orb_fade_r3 | 4,320 | 0 | -3,572 | 1.5 | 531 |
| MES | orb_fade_r5 | 4,320 | 0 | -2,130 | 1.9 | 612 |
| MES | rsi_extreme_r1 | 5,760 | 0 | -17,278 | 0.6 | 594 |
| MES | rsi_extreme_r3 | 5,760 | 0 | -15,189 | 0.7 | 337 |
| MES | rsi_extreme_r5 | 5,760 | 0 | -14,404 | 0.8 | 192 |
| MES | stretch_fade_r1 | 5,760 | 0 | -27,584 | 0.0 | -20,542 |
| MES | stretch_fade_r3 | 5,760 | 0 | -26,368 | 0.0 | -8,142 |
| MES | stretch_fade_r5 | 5,760 | 0 | -25,043 | 0.0 | -5,097 |
| MES | volume_exhaustion_r1 | 5,760 | 0 | -26,224 | 0.0 | -9,290 |
| MES | volume_exhaustion_r3 | 5,760 | 0 | -21,088 | 0.1 | -1,316 |
| MES | volume_exhaustion_r5 | 5,760 | 0 | -19,110 | 0.1 | -594 |
| MES | vwap_snapback_r1 | 5,760 | 0 | -27,775 | 0.0 | -24,722 |
| MES | vwap_snapback_r3 | 5,760 | 0 | -25,695 | 0.0 | -9,160 |
| MES | vwap_snapback_r5 | 5,760 | 0 | -22,551 | 0.0 | -2,916 |
| MNQ | keltner_fade_r1 | 5,760 | 0 | -23,215 | 0.1 | -602 |
| MNQ | keltner_fade_r3 | 5,760 | 0 | -16,019 | 0.5 | 356 |
| MNQ | keltner_fade_r5 | 5,760 | 0 | -12,089 | 0.6 | 638 |
| MNQ | orb_fade_r1 | 4,320 | 0 | -3,251 | 1.8 | 798 |
| MNQ | orb_fade_r3 | 4,320 | 0 | -1,361 | 3.3 | 1,936 |
| MNQ | orb_fade_r5 | 4,320 | 0 | -632 | 3.9 | 2,943 |
| MNQ | rsi_extreme_r1 | 5,760 | 0 | -15,608 | 0.8 | 397 |
| MNQ | rsi_extreme_r3 | 5,760 | 0 | -13,366 | 1.0 | 621 |
| MNQ | rsi_extreme_r5 | 5,760 | 0 | -11,986 | 1.1 | 200 |
| MNQ | stretch_fade_r1 | 5,760 | 0 | -26,326 | 0.0 | -12,546 |
| MNQ | stretch_fade_r3 | 5,760 | 0 | -23,798 | 0.0 | -5,238 |
| MNQ | stretch_fade_r5 | 5,760 | 0 | -20,961 | 0.1 | -2,742 |
| MNQ | volume_exhaustion_r1 | 5,760 | 0 | -22,222 | 0.1 | -2,916 |
| MNQ | volume_exhaustion_r3 | 5,760 | 0 | -15,363 | 0.5 | -246 |
| MNQ | volume_exhaustion_r5 | 5,760 | 0 | -12,899 | 0.8 | -76 |
| MNQ | vwap_snapback_r1 | 5,760 | 0 | -26,779 | 0.0 | -16,741 |
| MNQ | vwap_snapback_r3 | 5,760 | 0 | -23,324 | 0.0 | -7,770 |
| MNQ | vwap_snapback_r5 | 5,760 | 0 | -19,005 | 0.1 | -2,012 |

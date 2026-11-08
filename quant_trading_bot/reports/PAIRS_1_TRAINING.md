# pairs_1 result: intraday NQ/ES beta-hedged relative-value mean reversion, 15m bars, training 2010-2023 (protocol research/pairs_1/PROTOCOL.md)

**Verdict: REJECTED (0 of 36 configs pass; every config loses and 36 of 36 are worse than 90% of random-direction placebos).** Validation untouched.

## Predictive test (hedged $ change over the next h bars when fading |z|, top |z| decile; cost of a 1 MNQ + n MES round trip is $8-18)

| N | h=4 | h=8 | h=16 |
|---|---:|---:|---:|
| 26 | -1.76 (t -4.4) | -2.86 (t -5.0) | -2.54 (t -2.5) |
| 52 | -1.56 (t -4.1) | -2.31 (t -4.1) | -3.27 (t -3.0) |
| 130 | -0.66 (t -1.8) | -1.71 (t -3.1) | -1.34 (t -1.3) |

## Executable grid (36 configs, 20 placebos each)

| N | k | H | window | net | trades | +yrs/14 | placebo pct | placebo mean |
|---|---|---|---|---:|---:|---:|---:|---:|
| 26 | 1.5 | 8 | 585-900 | -76,802 | 7,902 | 0 | 0.00 | -49,053 |
| 26 | 1.5 | 8 | 585-690 | -54,662 | 5,405 | 0 | 0.00 | -30,784 |
| 26 | 1.5 | 16 | 585-900 | -65,307 | 6,753 | 0 | 0.00 | -36,706 |
| 26 | 1.5 | 16 | 585-690 | -53,688 | 5,405 | 0 | 0.00 | -31,429 |
| 26 | 2.0 | 8 | 585-900 | -50,102 | 4,833 | 0 | 0.00 | -34,596 |
| 26 | 2.0 | 8 | 585-690 | -40,583 | 3,716 | 0 | 0.00 | -23,451 |
| 26 | 2.0 | 16 | 585-900 | -44,306 | 4,431 | 0 | 0.00 | -28,073 |
| 26 | 2.0 | 16 | 585-690 | -38,851 | 3,716 | 0 | 0.00 | -24,755 |
| 26 | 2.5 | 8 | 585-900 | -33,647 | 3,049 | 0 | 0.00 | -23,447 |
| 26 | 2.5 | 8 | 585-690 | -29,279 | 2,595 | 0 | 0.00 | -18,091 |
| 26 | 2.5 | 16 | 585-900 | -31,148 | 2,970 | 0 | 0.00 | -20,383 |
| 26 | 2.5 | 16 | 585-690 | -27,245 | 2,595 | 0 | 0.00 | -18,285 |
| 52 | 1.5 | 8 | 585-900 | -63,296 | 6,880 | 0 | 0.00 | -42,761 |
| 52 | 1.5 | 8 | 585-690 | -41,374 | 4,190 | 0 | 0.00 | -26,240 |
| 52 | 1.5 | 16 | 585-900 | -51,628 | 5,463 | 0 | 0.00 | -30,582 |
| 52 | 1.5 | 16 | 585-690 | -41,074 | 4,190 | 0 | 0.00 | -25,970 |
| 52 | 2.0 | 8 | 585-900 | -37,083 | 3,718 | 0 | 0.00 | -27,410 |
| 52 | 2.0 | 8 | 585-690 | -26,958 | 2,578 | 0 | 0.00 | -18,496 |
| 52 | 2.0 | 16 | 585-900 | -30,740 | 3,079 | 0 | 0.00 | -21,163 |
| 52 | 2.0 | 16 | 585-690 | -26,387 | 2,578 | 0 | 0.00 | -17,753 |
| 52 | 2.5 | 8 | 585-900 | -21,792 | 1,916 | 0 | 0.00 | -15,412 |
| 52 | 2.5 | 8 | 585-690 | -18,158 | 1,543 | 0 | 0.00 | -11,523 |
| 52 | 2.5 | 16 | 585-900 | -18,456 | 1,746 | 0 | 0.00 | -13,116 |
| 52 | 2.5 | 16 | 585-690 | -16,282 | 1,543 | 1 | 0.00 | -11,889 |
| 130 | 1.5 | 8 | 585-900 | -52,534 | 5,835 | 0 | 0.00 | -36,982 |
| 130 | 1.5 | 8 | 585-690 | -27,988 | 2,909 | 0 | 0.00 | -19,651 |
| 130 | 1.5 | 16 | 585-900 | -41,055 | 4,483 | 0 | 0.00 | -26,586 |
| 130 | 1.5 | 16 | 585-690 | -26,727 | 2,909 | 0 | 0.00 | -19,520 |
| 130 | 2.0 | 8 | 585-900 | -28,005 | 2,920 | 0 | 0.00 | -21,774 |
| 130 | 2.0 | 8 | 585-690 | -17,102 | 1,578 | 0 | 0.00 | -11,798 |
| 130 | 2.0 | 16 | 585-900 | -20,361 | 2,211 | 1 | 0.05 | -16,212 |
| 130 | 2.0 | 16 | 585-690 | -14,594 | 1,578 | 1 | 0.10 | -11,435 |
| 130 | 2.5 | 8 | 585-900 | -13,548 | 1,305 | 1 | 0.00 | -10,881 |
| 130 | 2.5 | 8 | 585-690 | -9,869 | 818 | 1 | 0.00 | -6,618 |
| 130 | 2.5 | 16 | 585-900 | -10,168 | 1,024 | 1 | 0.05 | -8,252 |
| 130 | 2.5 | 16 | 585-690 | -8,569 | 818 | 1 | 0.00 | -6,673 |

Best config 130/2.5/16: -8,569 on 818 trades; worst -76,802. Placebo means are themselves deeply negative (two-leg costs on 800-2,200 trades), and the real rule sits below them in almost every cell.

## Reading
Fading the intraday NQ/ES ratio loses *more* than random-direction trades with identical costs and exits, i.e. the beta-hedged ratio continues rather than reverts over 1-4 hours on 15m bars (the predictive table has the same sign). That is a relative-strength continuation effect, not a mean-reversion one. Trading it the other way would be a sign-flip fitted on training, so it is not claimed here; if tested it must be a fresh pre-registration (pairs_2) with its own gates, and the magnitude in the predictive table (a few dollars per hedged unit) is already in the range of the two-leg round trip, so the prior is low.

No cross-contract horizon remains untested: 1-minute lead-lag (leadlag_1), hours-scale ratio reversion (pairs_1) and daily state (extstate_1) are all closed at micro costs.

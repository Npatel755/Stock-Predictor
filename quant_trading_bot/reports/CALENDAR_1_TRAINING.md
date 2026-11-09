# calendar_1 result: intraday-only calendar anomalies on MNQ/MES, training 2010-2023 (protocol research/calendar_1/PROTOCOL.md)

**Verdict: REJECTED (0 of 62 variants pass).** Validation untouched. Day sets from dates only; 200 same-size random day sets per test (20 random masks for the filters).

## T1 day direction 09:45 -> 15:54 (L = long, S = short)

| product | day set | side | days | net | +yrs/14 | placebo pct | placebo mean |
|---|---|---|---:|---:|---:|---:|---:|
| MNQ | tom | L | 636 | +897 | 4 | 0.65 | -319 |
| MNQ | tom | S | 636 | -4,834 | 5 | 0.36 | -3,471 |
| MNQ | non_tom | L | 2659 | -3,402 | 5 | 0.32 | -1,817 |
| MNQ | non_tom | S | 2659 | -13,057 | 2 | 0.69 | -14,727 |
| MNQ | opex | L | 157 | -3,863 | 2 | 0.06 | -196 |
| MNQ | opex | S | 157 | +2,892 | 9 | 0.96 | -791 |
| MNQ | pre_holiday | L | 124 | +1,145 | 8 | 0.73 | -113 |
| MNQ | pre_holiday | S | 124 | -1,912 | 4 | 0.21 | -542 |
| MNQ | mon | L | 618 | +2,736 | 6 | 0.81 | -483 |
| MNQ | mon | S | 618 | -6,562 | 7 | 0.24 | -3,811 |
| MNQ | tue | L | 679 | -1,469 | 4 | 0.37 | -470 |
| MNQ | tue | S | 679 | -2,734 | 4 | 0.61 | -4,031 |
| MNQ | wed | L | 678 | -2,728 | 8 | 0.28 | -385 |
| MNQ | wed | S | 678 | -1,469 | 3 | 0.73 | -3,840 |
| MNQ | thu | L | 666 | -40 | 7 | 0.54 | -483 |
| MNQ | thu | S | 666 | -4,082 | 1 | 0.40 | -2,826 |
| MNQ | fri | L | 654 | -1,004 | 5 | 0.48 | -882 |
| MNQ | fri | S | 654 | -3,044 | 7 | 0.56 | -3,651 |
| MES | tom | L | 636 | -237 | 5 | 0.75 | -1,852 |
| MES | tom | S | 636 | -6,085 | 3 | 0.32 | -4,878 |
| MES | non_tom | L | 2659 | -8,458 | 2 | 0.27 | -7,060 |
| MES | non_tom | S | 2659 | -17,973 | 2 | 0.73 | -19,476 |
| MES | opex | L | 157 | -2,332 | 3 | 0.04 | -316 |
| MES | opex | S | 157 | +771 | 8 | 0.95 | -1,250 |
| MES | pre_holiday | L | 124 | +382 | 7 | 0.68 | -174 |
| MES | pre_holiday | S | 124 | -1,615 | 3 | 0.26 | -840 |
| MES | mon | L | 618 | -1,165 | 4 | 0.57 | -1,579 |
| MES | mon | S | 618 | -4,978 | 5 | 0.50 | -4,861 |
| MES | tue | L | 679 | -3,856 | 3 | 0.20 | -1,909 |
| MES | tue | S | 679 | -2,893 | 5 | 0.80 | -4,847 |
| MES | wed | L | 678 | -3,510 | 5 | 0.24 | -1,624 |
| MES | wed | S | 678 | -3,230 | 4 | 0.72 | -4,827 |
| MES | thu | L | 666 | +576 | 8 | 0.82 | -1,671 |
| MES | thu | S | 666 | -7,196 | 0 | 0.17 | -4,816 |
| MES | fri | L | 654 | -740 | 5 | 0.60 | -1,489 |
| MES | fri | S | 654 | -5,760 | 2 | 0.34 | -4,782 |

## T1b last hour 15:00 -> 15:54

| product | day set | side | days | net | +yrs/14 | placebo pct | placebo mean |
|---|---|---|---:|---:|---:|---:|---:|
| MNQ | month_end | L | 159 | -464 | 6 | 0.67 | -743 |
| MNQ | month_end | S | 159 | -521 | 5 | 0.35 | -237 |
| MNQ | quarter_end | L | 54 | -934 | 2 | 0.10 | -270 |
| MNQ | quarter_end | S | 54 | +599 | 7 | 0.94 | -125 |
| MNQ | opex | L | 157 | -658 | 2 | 0.53 | -645 |
| MNQ | opex | S | 157 | -313 | 4 | 0.49 | -288 |
| MNQ | tom | L | 636 | -465 | 6 | 0.94 | -2,868 |
| MNQ | tom | S | 636 | -3,472 | 2 | 0.04 | -999 |
| MNQ | all | L | 3295 | -14,466 | 0 | 0.00 | -14,466 |
| MNQ | all | S | 3295 | -5,930 | 2 | 0.00 | -5,930 |
| MES | month_end | L | 159 | -610 | 5 | 0.65 | -824 |
| MES | month_end | S | 159 | -970 | 4 | 0.32 | -684 |
| MES | quarter_end | L | 54 | -586 | 4 | 0.18 | -302 |
| MES | quarter_end | S | 54 | +49 | 5 | 0.82 | -253 |
| MES | opex | L | 157 | -858 | 2 | 0.55 | -903 |
| MES | opex | S | 157 | -703 | 3 | 0.48 | -684 |
| MES | tom | L | 636 | -1,838 | 4 | 0.94 | -3,385 |
| MES | tom | S | 636 | -4,483 | 1 | 0.08 | -2,960 |
| MES | all | L | 3295 | -17,759 | 0 | 0.00 | -17,759 |
| MES | all | S | 3295 | -14,994 | 2 | 0.00 | -14,994 |

## T2 day-set filters on the fixed 15m MNQ momentum rule (unfiltered +$5,714 / 4,145 trades / 5 of 14 years)

| filter | days | net | trades | +yrs/14 | placebo pct | placebo mean |
|---|---:|---:|---:|---:|---:|---:|
| tom | 636 | +1,170 | 753 | 5 | 0.40 | +1,923 |
| opex | 157 | +932 | 180 | 9 | 0.75 | +214 |
| mon | 675 | +2,080 | 763 | 5 | 0.65 | +1,493 |
| fri | 671 | +2,858 | 769 | 8 | 0.90 | +188 |
| ex_opex | 3240 | +4,782 | 3,965 | 5 | 0.50 | +5,053 |
| ex_tom | 2761 | +4,544 | 3,392 | 5 | 0.40 | +4,473 |

## Reading
- The RTH open-to-close drift of the index is negative after micro costs on every day set (long 'all' loses $14-18k over 14 years): the equity premium is earned overnight, so no intraday-only calendar bet survives. Turn-of-month and Thursday longs are the least bad (beat 75-94% of random day sets) but are still negative in dollars and in 5-8 of 14 years.
- The only variants that beat 95% of random day sets are short MES on OPEX (+$771, 8/14 years, 157 days) and short MNQ on quarter-end last hour (+$599, 54 days) - a handful of dollars per event over 14 years, below the 100-trade/10-year gates and well within what 100+ variants produce by chance.
- Calendar filters on the momentum rule (Friday-only beats 90% of random masks, 8/14 years, +$2,858) do not reach the gate either.

Calendar/seasonal effects are closed for intraday-only micro trading. With gap_1, anomaly_1, extstate_1, pairs_1 and this round, every mechanism that can be built from the price data, free daily external series and the calendar has now been tested under the fixed protocol.

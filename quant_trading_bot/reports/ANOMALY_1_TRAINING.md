# anomaly_1 result: published intraday anomalies on ES/NQ -> MES/MNQ, training 2010-2023 (protocol research/anomaly_1/PROTOCOL.md)

**Verdict: all three families REJECTED (0 of 24 + 6 + 4 variants pass).** Validation 2024-25 not run; 2026 never loaded. Costs: $0.61/side, 1 tick slippage/side, MNQ 1.75-tick / MES 1-tick spread (MNQ round trip ≈ $3.1, MES ≈ $5.0).

## A. Intraday momentum (first half-hour return -> last half-hour), 2010-23, 1 contract

| product | entry | abs z >= | r12 agree | net | trades | +yrs/14 | placebo pct |
|---|---|---:|---|---:|---:|---:|---:|
| MNQ | 1500 | 0.0 | False | -7,596 | 3,229 | 2 | 0.80 |
| MNQ | 1500 | 0.0 | True | -3,959 | 1,640 | 3 | 0.60 |
| MNQ | 1500 | 0.5 | False | -4,623 | 2,008 | 2 | 0.70 |
| MNQ | 1500 | 0.5 | True | -1,450 | 1,000 | 4 | 0.85 |
| MNQ | 1500 | 1.0 | False | -3,978 | 1,022 | 2 | 0.50 |
| MNQ | 1500 | 1.0 | True | -2,087 | 508 | 3 | 0.25 |
| MNQ | 1530 | 0.0 | False | -8,100 | 3,229 | 1 | 0.80 |
| MNQ | 1530 | 0.0 | True | -5,265 | 1,640 | 3 | 0.50 |
| MNQ | 1530 | 0.5 | False | -5,035 | 2,008 | 2 | 0.85 |
| MNQ | 1530 | 0.5 | True | -2,660 | 1,000 | 5 | 0.55 |
| MNQ | 1530 | 1.0 | False | -4,659 | 1,022 | 0 | 0.20 |
| MNQ | 1530 | 1.0 | True | -2,273 | 508 | 2 | 0.20 |
| MES | 1500 | 0.0 | False | -16,612 | 3,226 | 1 | 0.35 |
| MES | 1500 | 0.0 | True | -7,651 | 1,549 | 1 | 0.55 |
| MES | 1500 | 0.5 | False | -10,642 | 2,011 | 0 | 0.40 |
| MES | 1500 | 0.5 | True | -3,921 | 979 | 2 | 0.80 |
| MES | 1500 | 1.0 | False | -7,397 | 1,067 | 0 | 0.05 |
| MES | 1500 | 1.0 | True | -2,684 | 523 | 3 | 0.40 |
| MES | 1530 | 0.0 | False | -14,804 | 3,226 | 0 | 0.75 |
| MES | 1530 | 0.0 | True | -7,600 | 1,549 | 0 | 0.60 |
| MES | 1530 | 0.5 | False | -9,442 | 2,011 | 1 | 0.40 |
| MES | 1530 | 0.5 | True | -4,319 | 979 | 2 | 0.60 |
| MES | 1530 | 1.0 | False | -5,950 | 1,067 | 1 | 0.20 |
| MES | 1530 | 1.0 | True | -2,478 | 523 | 2 | 0.40 |

The published effect exists in sign (the unfiltered MNQ versions beat 80% of random-direction placebos, i.e. the first half-hour predicts the last by a couple of ticks on average) but every variant loses after costs - the gross per day is about 1-3 ticks against a 6-10 tick micro round trip. MES is worse. Best variant −$1,450 (MNQ, 15:00, |z| ≥ 0.5, r12 agree, 1,000 trades, 4 of 14 years positive).

## B. Pre-FOMC drift (long into the 14:00 ET statement; 110 events 2010-23)

| product | window | mean net / event | t | non-FOMC control mean | +yrs | placebo pct |
|---|---|---:|---:|---:|---:|---:|
| MNQ | day0_0930_1355 | -8.62 | -0.93 | -0.72 | 6 | 0.25 |
| MNQ | day0_1000_1355 | -10.33 | -1.68 | -3.11 | 2 | 0.31 |
| MNQ | daym1_0930_1555 | +6.40 | +0.36 | +0.10 | 7 | 0.69 |
| MES | day0_0930_1355 | -9.33 | -1.46 | -3.25 | 3 | 0.24 |
| MES | day0_1000_1355 | -10.52 | -2.32 | -4.42 | 3 | 0.16 |
| MES | daym1_0930_1555 | +2.81 | +0.24 | -2.71 | 8 | 0.69 |

No RTH pre-FOMC drift on index futures 2010-23: announcement-day mornings are slightly negative (t −0.9 to −2.3) and indistinguishable from ordinary days; the day-before session is +$3-6 per event (t 0.3, placebo pct 0.69). Consistent with the literature that the Lucca-Moench drift is an overnight/pre-2011 phenomenon and has decayed - not tradable intraday on a micro.

## C. Kaufman ER filter on a fixed 15m MNQ momentum rule (lb24, 09:45-15:30 entries, 2.0 ATR stop, 3R, hold 24, flat 15:55)

| ER(24) > | net | trades | +yrs/14 | placebo pct (same on-fraction random mask) | placebo mean |
|---|---:|---:|---:|---:|---:|
| none | +5,714 | 4,145 | 5 | - | - |
| 0.3 | +9,192 | 1,915 | 5 | 0.90 | +5,403 |
| 0.5 | +2,340 | 759 | 6 | 0.25 | +3,789 |
| 0.7 | -709 | 152 | 6 | 0.15 | +777 |

ER > 0.3 raises the rule's 14-year net from +$5.7k to +$9.2k, but random masks of the same size average +$5.4k and the ER mask beats only 90% of them (gate 95%); ER > 0.5 / 0.7 are below their placebo means. The base rule itself is positive in only 5 of 14 years, so even the best filtered version is a 2020-23 rule with fewer trades. Consistent with the Antigravity Dual-Regime replication (ER mask 80% vs placebo): the efficiency ratio is at best a weak trade-count reducer, not a regime detector that rescues 2010-19.

## Consequence
Published intraday anomalies (intraday momentum, pre-FOMC drift) are real in sign but 3-10x smaller than micro execution costs on 2010-23 index futures; ER regime filtering does not beat random masks. Closed; do not re-run with other windows, thresholds or products.

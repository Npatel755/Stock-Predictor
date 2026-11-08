# orderflow_2 pilot result: MNQ.c.0 trades Apr-Dec 2023 (pre-registered research/orderflow_2/PROTOCOL.md)

**Verdict: REJECTED.** Signed-volume (aggressor-side) imbalance has no predictive content beyond marketable costs on MNQ at 1 s-15 min horizons, and no executable rule in the registered grid passes. Spend $117.50 (second Databento account); 2024+ order-flow data untouched.

## Data
- Trades decoded to 1-second aggregates: 4,363,219 RTH seconds over 206 sessions, 93.9M trades; share of trades with no aggressor side 0.00000%. Joined to bbo-1s quotes on the same second; features are past-only (window ends at the previous second) and the simulator fills marketable at the next second after a 10 s reaction delay.

## Test 1: predictive (feature decile -> forward mid change, RTH 09:45-15:30, day-block t)

| feature | horizon | top-minus-bottom (ticks) | t | monotone rho | n |
|---|---:|---:|---:|---:|---:|
| svi60 | 10 s | -0.055 | -0.87 | -0.43 | 3,862,867 |
| svi60 | 60 s | -0.175 | -0.62 | -0.28 | 3,862,517 |
| svi60 | 300 s | -1.039 | -1.63 | -0.70 | 3,860,837 |
| svi300 | 10 s | -0.039 | -0.66 | -0.22 | 3,862,867 |
| svi300 | 60 s | -0.285 | -0.93 | -0.35 | 3,862,517 |
| svi300 | 300 s | -0.753 | -0.60 | +0.31 | 3,860,837 |
| svi900 | 10 s | +0.012 | +0.18 | +0.38 | 3,862,733 |
| svi900 | 60 s | +0.213 | +0.57 | +0.56 | 3,862,383 |
| svi900 | 300 s | +1.887 | +1.22 | +0.72 | 3,860,703 |
| bigimb300 | 10 s | -0.016 | -0.23 | -0.49 | 3,839,008 |
| bigimb300 | 60 s | -0.259 | -0.65 | -0.64 | 3,838,658 |
| bigimb300 | 300 s | -0.180 | -0.14 | +0.33 | 3,837,264 |

Gate: |t| > 4 and spread > 5.44 ticks (round trip excl. spread). Best is svi900 at 300 s: +1.89 ticks, t 1.22. Nothing passes; 1-5 min imbalance is weakly *negative* (mean-reverting) but at < 1 tick.

## Test 2: executable grid (58 configs, stop 4 ticks, 20 same-count random placebos where trades >= 50)

| feature | q | mode | hold s | net $ | trades | $/trade | months+ /9 | beats placebos |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| svi60 | 0.3 | cont | 120 | -44,176 | 14,943 | -2.96 | 0 | 100% |
| svi60 | 0.3 | cont | 300 | -39,494 | 13,443 | -2.94 | 0 | 100% |
| svi60 | 0.3 | cont | 900 | -32,856 | 11,308 | -2.91 | 0 | 100% |
| svi60 | 0.3 | rev | 120 | -50,746 | 16,878 | -3.01 | 0 | 100% |
| svi60 | 0.3 | rev | 300 | -41,565 | 14,541 | -2.86 | 0 | 100% |
| svi60 | 0.3 | rev | 900 | -35,701 | 11,734 | -3.04 | 0 | 100% |
| svi60 | 0.5 | cont | 120 | -1,439 | 471 | -3.05 | 0 | 100% |
| svi60 | 0.5 | cont | 300 | -853 | 444 | -1.92 | 3 | 100% |
| svi60 | 0.5 | cont | 900 | -842 | 410 | -2.05 | 2 | 100% |
| svi60 | 0.5 | rev | 120 | -1,854 | 495 | -3.75 | 0 | 100% |
| svi60 | 0.5 | rev | 300 | -1,894 | 455 | -4.16 | 0 | 100% |
| svi60 | 0.5 | rev | 900 | -1,701 | 408 | -4.17 | 0 | 100% |
| svi60 | 0.7 | cont | 120 | -192 | 30 | -6.4 | 1 |  |
| svi60 | 0.7 | cont | 300 | +15 | 30 | 0.51 | 1 |  |
| svi60 | 0.7 | cont | 900 | +15 | 30 | 0.5 | 1 |  |
| svi60 | 0.7 | rev | 120 | -166 | 29 | -5.72 | 1 |  |
| svi60 | 0.7 | rev | 300 | -144 | 28 | -5.15 | 2 |  |
| svi60 | 0.7 | rev | 900 | -307 | 27 | -11.39 | 0 |  |
| svi300 | 0.3 | cont | 120 | -145 | 157 | -0.92 | 2 | 100% |
| svi300 | 0.3 | cont | 300 | +69 | 131 | 0.52 | 2 | 100% |
| svi300 | 0.3 | cont | 900 | +262 | 114 | 2.3 | 3 | 100% |
| svi300 | 0.3 | rev | 120 | -1,031 | 209 | -4.94 | 1 | 100% |
| svi300 | 0.3 | rev | 300 | -1,132 | 198 | -5.71 | 0 | 100% |
| svi300 | 0.3 | rev | 900 | -924 | 189 | -4.89 | 1 | 100% |
| svi300 | 0.5 | cont | 120 | +88 | 4 | 21.91 | 1 |  |
| svi300 | 0.5 | cont | 300 | +91 | 3 | 30.28 | 1 |  |
| svi300 | 0.5 | cont | 900 | +96 | 3 | 32.11 | 1 |  |
| svi300 | 0.5 | rev | 120 | -114 | 4 | -28.59 | 0 |  |
| svi300 | 0.5 | rev | 300 | -110 | 3 | -36.72 | 0 |  |
| svi300 | 0.5 | rev | 900 | -110 | 3 | -36.72 | 0 |  |
| svi900 | 0.3 | cont | 120 | +262 | 10 | 26.23 | 2 |  |
| svi900 | 0.3 | cont | 300 | +270 | 8 | 33.78 | 2 |  |
| svi900 | 0.3 | cont | 900 | +273 | 7 | 38.99 | 2 |  |
| svi900 | 0.3 | rev | 120 | -176 | 15 | -11.75 | 0 |  |
| svi900 | 0.3 | rev | 300 | -201 | 15 | -13.39 | 0 |  |
| svi900 | 0.3 | rev | 900 | -194 | 15 | -12.92 | 0 |  |
| divergence | None | rev | 300 | -6,177 | 2,352 | -2.63 | 0 | 100% |
| divergence | None | rev | 900 | -7,114 | 2,315 | -3.07 | 0 | 100% |
| exhaustion | None | rev | 300 | -14,043 | 3,686 | -3.81 | 0 | 100% |
| exhaustion | None | rev | 900 | -11,066 | 3,031 | -3.65 | 0 | 100% |

(18 configs never fired: svi300/svi900 at q >= 0.5 and svi900 rev/cont at q >= 0.5.)

## Reading
- Every config with >= 50 trades is negative; the dense ones lose ~$3/trade, i.e. the round-trip cost (spread ~1.56 ticks + 2 ticks slippage + $1.22 commission). They still beat same-count random entries (placebo 100%), so signed volume carries *some* information - just less than one micro round trip, exactly as L1 imbalance did in orderflow_1.
- Delta divergence (-$6.2k/-$7.1k, ~2,300 trades) and buy/sell-volume exhaustion (-$11k/-$14k, ~3,000-3,700 trades) are the worst: the classic 'absorption / exhaustion fade' loses on MNQ at these horizons.
- The few positive nets (svi300 cont 900 s +$262 on 114 trades, 3 of 9 months positive; svi900 cont +$270 on 7-10 trades) fail the 7-of-9-months gate and are sample noise.
- Decision rule: predictive gate failed (no |t| > 4, no spread > cost), executable gate failed -> REJECTED, not PROXY-ONLY.

## Consequence
Order flow at the resolution a retail micro trader can act on (1 s quotes, true aggressor volume, 10 s reaction, marketable fills) is closed alongside 15-min price rules, 1-5 min fades, gap/Globex mechanics, news conditioning and vol filters. What is untested and would still be informative: (a) the five forward paper ledgers; (b) limit-order (passive) execution models, which require queue-position data (MBO) we do not have and which the funded-account copier cannot guarantee; (c) cross-asset lead-lag (ES/NQ vs MNQ, or bond/dollar shocks) at 1-min, which uses data already on disk. No further Databento purchases proposed.

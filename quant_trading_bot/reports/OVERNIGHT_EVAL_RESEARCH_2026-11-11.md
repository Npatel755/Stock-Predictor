# Overnight evaluation research, 2026-11-11 (Claude + 4 forked agents)

Goal: raise the chance of passing the Topstep $50K Static Combine ($4,000 target, static -$2,000 floor, $1,000 DLL, 55% consistency,
90 days). Incumbent: eval_8 plan (v5.3 + MNQ_BRK_E_2c + MES_MOM_3c + overnight leg; k3, k2 at -$500, k1 at -$1,000, k5 late when short),
60.0% per attempt on 2010-23 training (54.5% for 2010-16 starts, 65.6% for 2017-23). Training data only; every test pre-declared in its
script docstring; adoption needs both out-of-fold halves >= incumbent + 1 point.

## Correction (2026-11-11 afternoon) - read first

The pass rates in this report come from the v1 day simulator, which had a look-ahead: before each trade it counted the final P&L of
earlier trades that were still open (341 entries), so the daily stop could skip a trade because an open trade would lose. Same-minute
ties were also ordered by an unstable sort (~3 points of noise), and the training data has no bars for Jan 1 - May 5, 2019. Corrected
(eval_28 / eval_29, `pass_rate(v2=True)`, hole filled) the eval_8 plan passes **49.7% / 59.4% (~55% per attempt), fails 26%**.
Re-checking 9 size ladders under the corrected rules adopts nothing. Passed by attempt 1 / 2 / 3 / 4 / 5: 55 / 79 / 92 / 97 / 99%
(mean 1.8 purchases, median 65 days). The rejections below were by margins larger than the bias; readings within ~2 points (eval_18 F1,
eval_22, eval_25) are inside v1's noise. Afternoon studies: eval_24 purchase timing by regime (sign flips between halves, rejected),
eval_25 lock-the-pass / consistency cap (+0.5, common sense live), eval_26 day-to-day sizing (rejected).

## Evening review (2026-11-11): one real improvement - strict one-position routing

Re-checking the whole evaluation book under the corrected simulator (eval_30-32): the book's posthoc router lets a second trade open
while one is still on (384 overlapping pairs, 99.5% same direction, P&L correlation 0.66), i.e. doubled positions on trend days. Measured
on 1-minute bars, ~90% of the first trade's worst point coincides with the second's. With that risk priced, the incumbent passes
49.8 / 60.0; the live runner's own STRICT rule (never two positions) passes **54.4 / 61.1 with ~7 points fewer blow-ups**, and its result
does not depend on any overlap assumption. Pass by attempt 1..5: 58.8 / 80.9 / 94.8 / 99.1 / 99.9%. Sleeves: the night leg, Crabel and
TRD60 are essential; MES_MOM adds nothing; MNQ_BRK_E helps 2010-16 only. A DP sizer refit adds nothing.

On the strict book (eval_33-35): sizing is a flat plateau (14 ladder / stop / cap / lock cells within ~1 point; DEF_END stays);
of 14 sleeve changes both halves pick MNQ_E57 (55.3 / 62.7, misses the +1.0 bar by 0.1 - forward-paper candidate, not adopted); the
noise-area edge as a routed sleeve collapses the pass rate (36-45%). Final training estimate for the plan: strict routing + DEF_END,
~58% per attempt, ~81% within two, ~95% within three.

## Verdict

Nothing beats the incumbent. ~60% per attempt is the ceiling for this book with every edge available to us. The lever that works is a
second attempt bought right after a miss: ~82% pass within two attempts (77% / 88%), versus 64% for two attempts bought on the same day.

## New tool

`scripts/eval_harness.py`: `screen(daily)` checks in seconds whether a new stream can raise the book's daily Sharpe (0.151 at k3), which
is what the pass rate depends on; `Harness().pass_rate(book, extra)` runs the full simulator (reproduces 54.5 / 65.6 exactly).
Sensitivity: a ~20% rise in daily Sharpe is worth ~+10 points; +5% is the minimum worth a pass-rate run.

## What was tested

| Study | Idea | Result |
|---|---|---|
| eval_12 | Published noise-area intraday momentum (Zarattini, Aziz & Barbon 2024) on MNQ / MES | Real MNQ edge (PF 1.14 / 1.32, beats drift and 200/200 placebos); MES fails |
| eval_13 | Noise-area as a concurrent stream, 6 sizings | All worse (best 49.4 / 58.0): daily Sharpe 0.07 vs book 0.14, corr +0.36 - adds variance, not Sharpe |
| ovrv_1 (fork B) | NQ vs ES relative-strength continuation, 10 cells | Sign real, below 4-fill costs; all negative |
| ovrv_2 (fork B) | Europe-open / overnight breakouts and bands, 12 cells | All lose (PF 0.64-0.98); overnight breakouts revert, but the fade is below costs |
| ovrv_3 (fork B) | Exit overlays on the book's trades (breakeven, half off, trail, time stop) | Cut swings and profit equally; best daily Sharpe 0.154 vs 0.151 (gate 0.158) |
| bookx_1 (fork C) | Fail anatomy, leave-one-sleeve-out, routing, noise filter, Crabel size | Every sleeve earns its place; fails are slow bleeds at 1x from ~-$1,850 |
| tsm_1 (fork C) | Daily trend-following on MGC / SIL / MCL / MBT, re-entered daily | Uncorrelated but no gross edge 2011-23; costs 4.6-16.7x gross |
| xmkt (fork A) | ZN and micro FX (M6E / M6A / M6B) intraday, 40 cells, free HistData FX | All fail the screen; gross edge far below costs |
| eval_14 | Two Combines on the same day vs two in sequence | Parallel 64.1%; sequential 82% within two attempts |
| eval_15 | Waiting 10-40 sessions after a failed attempt | No gain; attempt 2 passes ~60% regardless - buy it immediately |
| eval_16 | Relative-volume filter; volatility-managed sizing | Skipped trades were profitable; vol-managed out-of-fold 51.4 / 63.8 - both rejected |
| regx_1 (fork D) | Every registry sleeve not in the book (22 ledgers) through the screen | None passes; top lifts are 2017-23-only era effects |
| eval_17 | The same Combine with the End-of-Day trailing drawdown ($3k target) | 56.2% vs static 60.0% - keep the static product |
| eval_18 | Stop-and-reverse after the book's own stop-outs (hedge stream) | Real small edge (PF 1.24 both halves, rho -0.07), first screen pass; pass rate +0.2 / +0.4 at 1 micro, out-of-fold 54.7 / 63.4 - not adopted |
| eval_21 | Swap the book's TRD60 sleeve for noise-area | Daily Sharpe 0.130-0.134 vs 0.151; pass 45.6 / 57.1 - TRD60 is better |
| check | Overlap assumption made optimistic | Hedge 55.5 / 66.0, noise 52.3 / 62.6 - rejections do not depend on it |
| eval_22 (morning) | Buy the 2nd attempt early (at a -$1,500 close, or day 60 under +$1,500) | Faster: within 90 days 67.0 / 76.9 vs 60.4 / 75.4; not more likely by 180 days; wastes a purchase 1-6%; 120-day out-of-fold +1.1 / +0.7 - not adopted |
| eval_23 (morning) | Stop-and-reverse hedge at 2-3 micros, every stop-out | Worse with size (2017-23 60.7-62.6); it adds losses on already-losing days |
| eval_19 | +1 / +2 ticks extra slippage per side | 54.1 / 64.5 and 53.0 / 64.2 - not execution-fragile |
| eval_20 | Pass rate by start year; consistency-rule near misses | 9% (2010) to 96% (2022); 3.8% of starts time out above $4k because the 55% rule raised the target |

## Why the ceiling holds

To lift the pass rate ~10 points, a new stream must raise the book's daily Sharpe ~20%. With low correlation that needs a stream with an
all-session daily Sharpe near 0.1 (annual ~1.6) after micro costs - a second book as good as the first. Everything tested tonight was
either cost-negative or trend-correlated with the book. Topstep's flat-by-16:10 ET rule also blocks the multi-day carry that most
non-equity edges rely on.

## Realism note

The base 3x book passed 53% on training but 39% on 2024-25 and 59% on 2026 (one-shot holdout, earlier). By start year the eval_8 plan
ranges from 9-43% in choppy years (2010, 2011, 2017, 2023) to 90-96% in trending ones (2021-22), so one attempt is close to a coin flip
whose odds depend on the year. Expect the forward per-attempt rate to be below the training 60%; forward paper (the challenger card on
the dashboard) is the real test. Plan the budget for two attempts.

## Recommendation

1. Keep the eval_8 plan (paper challenger) unchanged; nothing tested tonight earns a change.
2. Budget for a second attempt bought the session after a fail or timeout (~82% within two on training). Do not buy two at once.
3. Practical rule for the 55% consistency rule: a day above ~$2,200 raises the target; that is already modelled, and a daily profit stop
   was only worth ~+1 point.
4. For the funded side (Antigravity): the noise-area MNQ sleeve and the stop-and-reverse hedge are real small edges that could add dollars
   in a deep-cushion tier where the floor does not bind; test them 2-fold against Fortress 4X with the same tiers.

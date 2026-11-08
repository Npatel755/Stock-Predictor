# Strategy memory

- e57 baseline v1.0.0 preserves the user-selected momentum strategy and consumed holdout history. New challengers must be compared on training only; future independent confirmation needs fresh forward observations.

- novel_futures_2k_v1 completed all 2,000 TRAIN and 2,000 frozen VAL cases across eight statistical entry mechanisms.169 TRAIN and232 VAL positive-net/sub-$2k-DD cases; zero full TRAIN qualifiers and zero both-qualified. Leading VAL case +2536.50/DD1170.375 lost3671 on TRAIN. No replacement; no TEST access or validation-driven retry. See reports/NOVEL_FUTURES_2K.html.

- frontier_futures_2k_v1: another2000 new configurations across5 auction/profile/absorption/CUSUM/analog mechanisms.136 TRAIN,184 VAL,40both basic profit/DD passers;25VAL risk-check passers;0fullTRAIN/both qualifiers. Best V+6945.50/DD1686.75 had2 TRAIN locks. V#2+6902.50/DD1344.75 had TRAIN+3231/DD1636.25/no locks,but PF1.063,1160trades,and one losing year. Fixed gates preserved; no TEST access; no automatic promotion. See reports/FRONTIER_FUTURES_2K.html.

- explore_futures_2k_v1: user requested more; completed2000TRAIN+2000frozenVAL configurations of5additional entry algorithms.120TRAIN/333VAL/59both basic profit-DD passers;78VALriskqualifiers;0fullTRAIN/both qualifiers. Top V MNQordinalentropy +5191.50/DD976.25;TRAIN+141,PF1.005,only2/4positiveyears,no locks. No accepted replacement;TESTclosed. See reports/EXPLORE_FUTURES_2K.html.

- User designated Portfolio B3MESmomentum+1MNQbreakout as baseline. portfolio_b_train_refinement_v1 found verified TRAIN-only2MES+2MNQ challenger after5sizingtrials: matched continuous2019May-2023 net18642.25/DD1588.75 vs baseline14707.50/DD1572.50.2xcost net14104.75/DD1759.50,no locks;all4annual2020-23 folds positive at bothcosts. Same observed4contractcap/600allocatedrisk. Originalcost2baseline4343.25/DD1672 includes1sleevelock. No VAL/TEST evaluated;baselinev1.0.0 andchallengerv1.1.0-train-challenger saved separately. See reports/PORTFOLIO_B_TRAIN_REFINEMENT.html.

## 2026-11-08 overnight (Devin/codex): news, external-research and risk rounds on the 6 paper sleeves
- News rounds 1-3 (reports/NEWS_ROUND1-3.md): release blackouts, FOMC/NFP/CPI day skips, post-8:30 continuation sleeve,
  FOMC-afternoon continuation/fade - no filter or sleeve passes train gate + 2024-25 validation. The sleeves already earn
  part of their edge on release days; skipping NFP/CPI costs $300-1,600 per sleeve.
- Round 4 (reports/INTRADAY_MOMENTUM_ROUND4.md): Gao et al. 2018 last-half-hour intraday momentum is a few bp/day on
  SPY; at micro-contract costs it is -$3 to -$6.5 per trade on MES/MNQ, identical to placebo. Do not retest at 15 min.
- Round 5 (reports/CALENDAR_ROUND5.md): TOM / pre-holiday / OpEx day filters: 2 of 35 pass training, neither holds in
  validation beyond noise; TOM day-session long sleeve is flat. Published calendar effects are overnight effects.
- Round 6 (reports/VIX_ROUND6.md): prior-close VIX level/percentile/direction gates on all six sleeves: 0 of 42 pass.
- Risk of ruin (reports/RISK_OF_RUIN_CANDIDATES.md, 2020-23 day-block bootstrap): P(breach $2k) over 250 days is
  3.7% / 9.6% / 0.1% for E / Epsilon / Beta with the training edge, 57% / 56% / 18% with zero edge. Beta's sizing is the
  only one compatible with a $2k trailing drawdown if the out-of-sample edge is near zero.
- Working conclusion: at 15-min resolution with today's costs no additional filter class (news, calendar, VIX) improves
  the sleeves; remaining uncertainty is resolved only by the forward paper ledger (/futures).

## 2026-11-08 peer review of the Codex/Antigravity overnight run on Nick's PC
- Portfolio F (Beta + MNQ afternoon sleeve) and the 4-sleeve "institutional pod" both breach $2k in 2024-25 validation (DD $2,244 and $9,894). Not promotable. 2026 test was consumed for both.
- MES-agreement filter on MNQ AM breakout, afternoon 13:00-15:45 MNQ momentum, MES->MNQ lead-lag: training-only wins that failed validation or exceed $2k DD at 2c. Tested-negative.
- Portfolio E friction stress: validation DD $1,744 -> $1,946 at 2-tick slip + $1 fee. E is within $250 of the rule in 2024-25; Beta remains the only candidate sized for $2k.
- See reports/PEER_REVIEW_OVERNIGHT_INSTITUTIONAL.md.

## 2026-11-08 mass_v2 (reports/MASS_V2_SUMMARY.md)
- 1.2M-rule exhaustive grid (10 families) scored on ES/NQ 2010-2023 as MES/MNQ with the paper engine's costs and $2k rules: 9% net-positive, 74 pass the per-year gate (strict bars), 447 (lenient), 12 distinct pass both; DSR = 0 for all at N = 1.2M.
- Validation 2024-25 once: 1 of 12 holds, marginally (MNQ trend lb8 10-12 ET, +$437 / 2 yrs, DD $1.2k). Regime/hybrid rules flipped sign in 2025. MES: zero passers.
- Lesson: more variants of 15-minute price rules will not produce a funded-account edge; strict-bar rule distorts NQ pre-2018 (use lenient or require both).

## 2026-11-08 mass_v2 A2 (early-close fix applied; reports/MASS_V2_*_A2.md)
- 74 strict / 237 lenient / 23 both -> 13 distinct frozen (all MNQ trend/regime/hybrid). Validation once: 1/13 holds (v2_7f233cc729959bec, +$437/2y). All-day regime rules: +$1.6-2.6k in 2024, -$0.6-0.9k in 2025. 15-min price-rule universe closed; no counter-trend family passes (mean_reversion/vwap/opening_range: 0 on both bar rules).
- Next: 1-minute counter-trend search (VWAP snap-back, volume exhaustion, ORB fade) to pair with the morning trend runner.

## 2026-11-08 mass_1m: 1-minute counter-trend search - negative
198,720 configs (VWAP snap-back, volume exhaustion, ORB fade, RSI extreme, Keltner fade, stretch fade; 1/3/5-min; MES+MNQ; 14 train years, micro costs, early-close fix): 0 pass G1-G3, validation never run. Fast fades lose ~one round-trip of costs per trade (3-8k trades/14y, median net -$13k to -$28k). Only MNQ ORB fade has positive nets and its profit is entirely 2020-23. Lesson: 1-5 min mean reversion on MES/MNQ is cost-bound with OHLCV+volume inputs; do not re-run finer price/volume fade grids - need order-flow data or forward evidence. Report: reports/MASS_1M_TRAINING.md.

## 2026-11-08 orderflow_1: L1 imbalance on MNQ (bbo-1s 2023) — REJECTED
- Pre-registered (research/orderflow_1/PROTOCOL.md) before data was opened; ~$29 Databento spend (MNQ.c.0 bbo-1s 2023, bbo-1m 2019-25).
- Predictive test: top-vs-bottom decile of 30 s mean L1 imbalance moves the forward mid by +0.07 / -0.02 / -0.40 ticks at 10 s / 60 s / 300 s (day-block |t| < 1.1) vs ~5.4-tick marketable round trip. No predictive content at the one-second L1 level.
- Executable rule (36 configs incl. contra): |imb30| >= 0.3 fires ~1,350 times/yr and nets -$2.5 to -$3.4 per trade (= the round-trip cost); it beats same-count random entries by ~$7/trade, so there is some information, but it is smaller than spread+slippage+commission on a micro. q >= 0.5 fires 1-4 times a year.
- Data facts worth keeping: MNQ RTH spread averages 1.5-2.0 ticks (1-tick only 18-48% of the time, 2019-2025) and median displayed L1 size is 3-6 contracts — the engine's 1-tick spread assumption is optimistic for MNQ; L1 imbalance is noisy at these sizes. Databento bbo sizes are uint32: cast before subtracting.
- Lesson: do not re-run L1 imbalance variants on bbo-1s; the only untested order-flow class is true signed volume (trades/TBBO, ~$160+/yr), which is a separate decision for Nick. 2024-2026 bbo data untouched.
- 2026-11-08 spread sensitivity (scripts/spread_sensitivity_mnq.py, reports/SPREAD_SENSITIVITY_MNQ.md): MNQ spread 1 -> 1.75 ticks at $0.61/side costs the 15-min candidates $70-$215 per split except Portfolio E / E-scaled validation, which drops $1,006 (2,996 -> 1,991 over 2024-25) because the MNQ_BRK_E sleeve's thin 2024-25 edge is close to one extra tick per round trip. Epsilon moves +$140-270 (path dependence of stops, not edge). Use 1.75-tick MNQ spread as the default stress in future reports.
- 2026-11-08 vol attribution (reports/EDGE_ATTRIBUTION_VOL.md): 2020-23 profit of all surviving 15-min trend/breakout sleeves is an era effect, not a realized-vol effect - 2010-19 high-vol sessions lost; do not propose vol-regime filters as a fix.
- 2026-11-08 gap_1 (reports/GAP_1_TRAINING.md): overnight gap fade, gap-and-go and Globex-range break on 15-min bars, 152 configs, 0 pass the training gate; the RTH-open re-pricing is not an exploitable mechanism at micro costs. Do not re-run gap variants.
- 2026-11-09 orderflow_2 (reports/ORDERFLOW_2_PILOT.md, $117.50 MNQ trades Apr-Dec 2023): true aggressor-side signed volume at 1-15 min windows predicts the next 10 s-5 min by < 2 ticks (|t| <= 1.6) against a 5.4-tick marketable round trip; all 58 executable configs with >= 50 trades lose (~cost/trade), delta-divergence and exhaustion fades lose most. Order-flow leg closed at micro costs; do not re-run signed-volume variants or buy more tick data.
- 2026-11-09 leadlag_1 (reports/LEADLAG_1_TRAINING.md): ES/NQ 1-min residual lead-lag 2010-23 - NQ leads ES by 0.3-0.8 ticks (t up to 25, perfectly monotone) which is ~1/8 of a micro round trip; NQ shows no catch-up or reversion; all 54 MNQ configs lose ~cost/trade. Cross-contract lead-lag closed; do not re-run with other windows or an MES leg.
- 2026-11-09 Antigravity ER-regime pair (reports/ANTIGRAVITY_REGIME_REPLICATION.md): reproduces, but Kaufman-ER>0.5 mask beats only 80% of same-size random masks (gate 95%); 2010-16 flat (+$350/7y), profit = 2017-18 + 2021-22. Regime filters must be tested against same-on-fraction random-mask placebos before being credited.
- 2026-11-09 anomaly_1 (reports/ANOMALY_1_TRAINING.md): published intraday momentum (first->last half-hour) is real in sign (beats 80% of random-direction placebos) but 1-3 ticks gross vs 6-10 tick micro round trip -> all 24 variants lose; pre-FOMC drift has no RTH component 2010-23 (t -0.9 to -2.3 on day 0, +0.3 day -1); ER>0.3 filter beats 90% of same-size random masks (gate 95%). Published anomalies and ER filters closed.
- 2026-11-08 extstate_1 (reports/EXTSTATE_1_TRAINING.md): prior-close VIX/VIX3M/200d states give no day-direction edge (all 20 negative). Intraday 15m momentum earns only on VIX-backwardation days (+$5.2k/319 trades, beats 95% of random day masks) and is at/below random on contango days - the trend sleeves' edge is a stress-regime effect, not an all-weather one. Not promotable (7/14 years, ~23 trades/yr); use as a monitor, not a filter grid.
- 2026-11-08 pairs_1 (reports/PAIRS_1_TRAINING.md): beta-hedged NQ/ES 15m ratio mean reversion loses in all 36 configs and underperforms random-direction placebos - the intraday ratio continues (relative strength) rather than reverts; two-leg micro costs ($8-18/round trip) swamp the few-dollar predictive signal either way. Cross-contract family closed at 1-min, hours and daily horizons.

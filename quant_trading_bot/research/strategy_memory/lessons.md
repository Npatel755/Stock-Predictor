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
- 2026-11-08 calendar_1 (reports/CALENDAR_1_TRAINING.md): TOM / OPEX / month- and quarter-end / weekday / pre-holiday have no intraday-only edge on MNQ/MES at micro costs (0 of 62); the RTH open-to-close drift is negative after costs on every day set because the premium is overnight. Do not revisit calendar day-direction bets under a flat-before-close constraint.
- Daily 200-SMA direction gates on intraday MNQ trend rules are noise: equal-exposure random long/short-only day gates do as well or better (reports/ANTIGRAVITY_SMA200_REPLICATION.md). A gate that "fixes" 2010-19 after seeing 2010-26 is in-sample by construction; require the same-on-fraction placebo before crediting any regime gate. (2026-11-08)
- Variance risk premium (implied minus realized variance) does not time intraday index direction or filter trend rules beyond random day sets (reports/QC_1_VRP_TRAINING.md). External daily states are closed as a family: VIX level, VIX/VIX3M, 200-day trend, VRP. (2026-11-08)
- Opening NQ-vs-ES relative momentum (09:30-10:00 spread z) does select days with MNQ continuation in the divergence direction (beats same-count random-day placebos 20/20, both tails positive) but only ~$5/trade pre-2020 and 9/14 years: informative, not tradeable alone (reports/ANTIGRAVITY_NQLEADER_REPLICATION.md). (2026-11-08)
- Passive limit entries do not rescue intraday fades on MNQ: resting orders fill ~85-95% of the time but adversely (the move continues), so the saved spread is given back; keep the marketable-fill cost model (reports/QC_1_EXEC_PILOT.md). Market-making edges need queue priority/rebates/inventory that a retail micro account lacks. (2026-11-08)
- Cross-asset intraday lead-lag into NQ (ZN rates: sub-tick; 6E: none; CL oil: inverse ~3 ticks per 30 min) is statistically real and economically sub-cost on a micro (reports/XASSET_1_TRAINING.md). Day-selection signals that beat random-day placebos (NQ/ES opening divergence, Crabel open-drive, VIX crush) all share the same profile: ~$4-5/trade pre-2020, 2020-21-heavy, 9/14 years - a composite could be pre-registered but the per-trade edge is below one round trip. (2026-11-09)
- Combining independent day-selection signals (divergence, Crabel, VIX crush) raises hit rate but not move size: $7-12/trade, 2021-dominated, 2010-19 ~$100/yr (reports/COMPOSITE_1_TRAINING.md). Day-selection family closed on owned data. (2026-11-09)
- Overnight (18:00->09:30) holding is allowed under Topstep/Lucid (flat before 16:10/16:45 cutoff). Raw overnight premium on NQ futures ~7 ticks/night (t 1.6) barely covers costs; conditional on a negative reopen gap it is ~10 ticks/night, 10/14 years, beats 193/200 placebos - best after-cost lead so far; follow-up must be pre-registered before touching 2024-25 (reports/OVERNIGHT_1_TRAINING.md). (2026-11-09)
- Reopen-dip overnight premium is monotone in dip size and placebo-robust but 2020-22-heavy, 2023 negative, and the frozen passer failed 2024-25 (one year each way, DD > $2k). Overnight family: 2024-25 is spent; only forward paper can test it further (reports/OVERNIGHT_2_TRAINING.md). (2026-11-09)
- Open-stamped bars: a signal filled at minute M may only use bars with sod + bar_minutes <= M. Antigravity's NQ-leader used the 10:15 close for a 10:00 fill (3.5x P&L inflation); always reconcile a 3x gap by diffing fill conventions first (reports/AG_NQLEADER_LOOKAHEAD_AUDIT.md). (2026-11-09)
- Index-tuned intraday trend/breakout rules do not transfer to crude at MCL costs (0/3); cross-market diversification of these sleeves is closed (reports/MULTIMARKET_1_TRAINING.md). (2026-11-09)
- 2026-11-09 sizing_1 (reports/SIZING_1_TRAINING.md): the engine's $150 stop-risk budget blocks $150-250-risk trades that are 4-7x better than average on the filtered Quad / Arch C / All-Weather (train 2010-23), but the gain sits in 2020/2022 and raises DD; only All-Weather passes unbounded (-> ag_all_weather_v2_1c on paper). >$250-risk trades are rare and negative: nothing supports trading today's $425+ stops.
- 2026-11-09 sizing_2 (reports/SIZING_2_TRAINING.md): a $250 budget gives the same drawdown as no budget for Quad/Arch C ($2,061/$1,911) - the extra DD comes from the $150-250 band clustering in 2020/2022, not from the rare >$250 trades. $150 stands; sizing is closed (two comparisons used on this split).
- 2026-11-09 calendar_2 (reports/CALENDAR_2_TRAINING.md): overnight TOM / month-end / OPEX-eve / pre-holiday holds on MNQ/MES 2010-23 are all inside the random-night band (0 of 4; TOM-and-dip is just the dip effect vs same-count dip-night subsets). Calendar effects closed for intraday and overnight. Gotcha: the overnight nights() frame has no Friday rows - rebuild the session calendar before using day sets.
- 2026-11-09 portfolio_4 (reports/PORTFOLIO_4_TRAINING.md): overnight_dip_v2 + ag_all_weather_v2_1c is the first pair that fits a $2k floor on 2010-23 (combined DD $1,633, 1-y breach 1.9%, corr 0.09, 0 overlaps); Arch C v2 / Quad v2 books do not ($2,315 / $2,396). Forward book P&L = sum of the two existing ledgers; no new ledger needed.
- 2026-11-09 book_1 (reports/BOOK_1_TRAINING.md): closed-DD understates funded risk for the overnight leg - the portfolio_4 pair's intraday-trailing DD is $2,043 (closed $1,633), one touch of a $2k floor in March 2020 with stops assumed hit; always report marked DD for no-stop holds.
- 2026-11-09 parity (reports/PARITY_OVERNIGHT_V2.md): ensemble_paper.run_overnight reproduces the research overnight_dip_v2 path exactly on 2022-23 (74/74 nights, $0.01). Paper-vs-backtest gaps for this ledger are market, not code.
- 2026-11-09 swing_1 (reports/SWING_1_TRAINING.md): multi-day (1-5 session) mean reversion after 5-day closing lows / lower closes / RSI(2) on MNQ/MES 2010-23 is real in sign (beats 192-198/200 random-entry placebos, shorts all lose) but the marked drawdown of one micro contract held for days is $2.5k-7k everywhere (0 of 48 pass); SMA-200 filter hurts (profit is bear-market bounces). Family closed; the bounded form is the 1-night reopen-dip already on paper.
- 2026-11-09 overnight_8 (reports/OVERNIGHT_8_TRAINING.md): Asia-session (18:05->03:00) return as a signal for a 03:00->US-open hold on MNQ/MES 2010-23: 0 of 24 pass; the 03:00->09:45 window has negative unconditional drift, selected nights earn <1 tick, Asia continuation loses. Overnight entry timing is closed (18:05/18:30/20:00/03:00 all tested).
- 2026-11-09 extstate_2 (reports/EXTSTATE_2_TRAINING.md): CBOE SKEW (free daily) prior-close states on 2010-23: no state is net negative for the overnight dip v2 nights or the All-Weather 1c days, so no stand-aside (0/27 adoptable) and no unconditional SKEW overnight premium; but low / falling SKEW (esp. below its 20d mean) carries 3-4x the per-unit edge on BOTH rules (196-199/200 random-removal tests) -> a sizing state to test (sizing_3), not a filter.
- 2026-11-09 sizing_3 (reports/SIZING_3_TRAINING.md): 2c when prior-close SKEW < 20d mean (1c otherwise) on the book_a legs: direction confirmed (book +51.0k vs control +33.9k, net/DD 18.5 vs 9.7, 1c 15.7) but closed DD 2.7k and 1y breach 17% at a $2k floor -> fails; usable only as a staging step once ~$1.5k is banked. Sizing on 2010-23 is now closed for these legs.
- 2026-11-09 archc_3 (reports/ARCHC_3_TRAINING.md): MES-confirmation ("breadth") gate on Architecture C 2010-23: requiring MES to agree cuts net 16.1k -> 6.7k and raises DD to 2.6k; removed trades are the best ones (NQ-drives-without-ES days). Cross-index confirmation is anti-edge for the NQ intraday sleeves; "MES not opposite" is a no-op. Antigravity's C++ spec was never pushed.
- 2026-11-09 archc_4 (reports/ARCHC_4_TRAINING.md): flip of archc_3 (trade Arch C only when MES does NOT confirm): trend sleeves +14.1k / DD 957 / 199/200 subsets but 10/14 years, and the same gate on All-Weather sleeves is random (120/200) -> derived, non-transferring, not deployed. Do not re-test this on 2010-23.
- 2026-11-09 Antigravity "Architecture D" (reports/ANTIGRAVITY_ARCH_D_REPLICATION.md): Champion 1 (Crabel + NQ-leader at 10:00) + afternoon 30m trend, 1c router; fixed engine 2010-23 +9.7k / 1,911 tr / 7 of 14 years / 2010-19 +868 -> FAIL; their +19.3k does not reproduce; afternoon sleeve was added to lift 2026 (test-driven design). Not deployed.
- 2026-11-09 paper runner incident (reports/PAPER_RUNNER_INCIDENT_2026-11-09.md): research-engine conveniences (early-close heuristic on the last bar of a day; terminal_close at end of data) are live-path hazards - the newest bar is not the close. Fixed in ensemble_paper (live_early_close, terminal_close -> open position). Any new sleeve code path must be checked on an in-progress day before trusting its first live trades.
- 2026-11-09 overnight_9 (reports/OVERNIGHT_9_TRAINING.md): protective stops (1/1.5/2 gap-sd) on overnight_dip_v2 nights are hit 42-65% of the time and cut net 36-54%, lowering net/DD; gap-fill exit after 08:30 is worse. Overnight exit management closed - the premium is earned by holding through the noise.
- 2026-11-09 m2k_1 (reports/M2K_1_TRAINING.md): frozen rules on Russell M2K (2017-23; RTY on CME only from 2017-07) and Dow MYM (2010-23): overnight co-dip is real (M2K 200/200 placebos) but $8.5 / $2.6 per night vs MNQ $24 - cheaper contracts earn proportionally less and do not buy DD relief; All-Weather sleeves lose on both (NQ-specific). 0/6, nothing deployed; RTY/YM 1-min data kept under data/market/crossasset (gitignored).
- 2026-11-09 risk_1 (reports/RISK_1_TRAINING.md): weekly-loss and losing-streak pause rules on Book A's overnight leg: 0/3 - the $2,043 marked DD is a single-night excursion (2020-03-17) no pause reaches; streak pauses skip above-average nights and raise DD. Risk overlays on the overnight leg closed; cushion staging is the lever.
- 2026-11-09 xasset_2 (reports/XASSET_2_TRAINING.md): ZN day return conditions the overnight dip: bonds-up dip nights $36/night vs bonds-down $2/night (128 nights, 7/200 random removals worse); not adoptable (removed set still +$261) and ZN coverage only 62% of nights. Oil/euro: nothing. Same class as SKEW - a ranking state, not a filter; fix ZN coverage before any bond-confirmed variant.
- 2026-11-09 xasset_3 (reports/XASSET_3_TRAINING.md): Book A with overnight leg skipping ZN-day-down nights: 93.5% net retained, marked DD 2,043 -> 1,506, 0 floor touches, 193/200 placebo worse, control fails. PASS (one split, derived from xasset_2). Deployed as book_a_bond beside book_a. FRAGILE: with the 15:00 ET close instead of 16:00 only 147/200 placebos are worse (fails); live feed uses the exact 16:00 close from ZN=F 1m bars.
- 2026-11-09 dplus_1/dplus_2 (reports/DPLUS_1_TRAINING.md, DPLUS_2_TRAINING.md): Antigravity's Architecture D+ reproduces in net (+20,723) not DD (1,654 vs their 936); marked DD alone 1,768, Crabel min_range is a plateau (0-25 all +7.8-8.2k). Dropping the MNQ 30m trend sleeve halves the DD (882) for 15% less net, beats 200/200 count-matched removals, but the sleeve is positive in 10/14 years so it fails the coherence gate - recorded as the DD-first configuration, not deployed. Book D+ (VIX-gated night) fails the $2k floor (marked 2,333): VIX gates belong on morning intraday sleeves, never on the overnight dip.
- dplus_2 scaling (2026-11-09): engine P&L is exactly linear in contracts (verified), so a lower-DD variant at 2c has the original's DD for +70% net - scaling is the right lever once DD per contract is halved; deployed as ag_arch_d_plus_v2 (1c) + ag_arch_d_plus_v2_2c (future, $300 budget). Correction same day: the D+ research numbers were measured under the engine's default $150 stop-risk budget (run_sleeve called directly), so the paper candidates keep that budget; setting risk_per_trade=1e9 broke parity (+18,386/1,457 vs +17,576/1,398) and was reverted within the hour.
- staging_1 (2026-11-09): under a trailing $2k floor that locks at +2.1k, pre-lock only marked DD matters (banked profit does not help), post-lock cushion is real. Book A from zero dies in 4.5% of 157 monthly 12m starts (intraday marks) / 5.7% bootstrap; D+ v2 alone 0% / 0.1%; a declared ladder (single leg -> Book A at $500 cushion -> SKEW book at $1.5k -> +D+ v2 at $3k) compounds to ~2.2x Book A over 14 years with 0 breaches but halves first-year net; failed its own gate on net, recorded as Nick's deployment decision. No leg changed.
- 2026-11-09 dplus_3: D+ v2 (opening leg) is not execution-fragile (91 % net kept at a 3-tick adverse fill) and its $882 marked DD is not gate-made (daily-loss / hard-DD never bind at 1c). Event-day (FOMC/CPI/NFP) stand-aside hurts the AG intraday sleeves too; event calendars are closed for all deployed families. Engine fact: adverse fill = slippage + spread/2 ticks rounded to the tick, so the default already pays 2 ticks/side and spread_ticks 1->2 is a no-op.
- 2026-11-09 dplus_4: Crabel gap-alignment (Antigravity v3) is a real directional state (continuation $21/tr 13/14 yrs vs fade $11/tr 7/14) but fades are net positive, so gating removes profit without lowering DD ($879 vs $882); claimed $431 DD / 14/14 years do not reproduce. Recorded state, no ledger.
- 2026-11-09 dplus_5: gap-alignment as sizing (2c on gap-continuation Crabel drives, 1c else) passes 5/5 on training: +23,142 / marked DD 1,027 / 1-y breach 0.05% / net-per-DD 22.5 vs 19.9; deployed as ag_arch_d_plus_v2_gapsize (Future strategies) via an addon_of/book pattern that re-runs the base exactly and republishes the filtered sleeve. One-split derived evidence; forward record decides.
- 2026-11-09 dplus_6: gap alignment does not carry to the D+ trend sleeves (60m trend is aligned by construction; MES split is noise, placebo 115/200). Effect is Crabel-open-drive-specific. Gap state on D+ closed.
- 2026-11-09 staging_2: gap-sized D+ as ladder opener: better alone (100% survival, median +783 vs +526, p10 -26 vs -86, 0.0% breach) but the ladder from it breaches 1.1% vs 0.9% (locks sooner -> more paths reach Book A stages). 3/4 gates; plan unchanged by rule; offered to Nick as a policy choice.
- 2026-11-09 funded_1: the evaluation ($3-4k target) is the bottleneck - at 1c no leg passes within a year > 35%; gap-sized D+ at 3 micros is the best pass/fail trade (43%/4% trailing). Static floor removes Book A's breach odds; $1k DLL only bites 2c overnight/SKEW books. D+ legs clean under every rule variant even at 2c.
- 2026-11-09 payout_1: per-trade dollars come from size only (wider targets change nothing - winners are time-exit capped). Engine's unscaled $2k per-sleeve hard-DD lock makes 4 micros unviable (632 trades, net collapses); 3 micros is the practical max. gap-sized D+ at 3c: median win $141/day $147, 16.7 $150+ days/yr, 0.6% static breach, 0% DLL -> Future ledger ag_arch_d_plus_v2_gapsize_3c.
- 2026-11-09 dplus_7: scaling the engine's per-sleeve lock to $2k x contracts lifts 3-micro gap-sized D+ to median win $165 (+$70.7k, breach 0.6%) but 5 days in 14y lose >= $1k (gapped-through stops on 6-micro Crabel trades; stop-risk caps and daily stops do not remove them) -> only for no-DLL accounts; deployed as gapsize_3c_v3 (Future) beside the DLL-safe 3c. 4 micros fails on the engine's 1% participation model regardless.
- 2026-11-10 dplus_7d/7e (in progress): on the 3c v3 base, continuation at 4 micros + ACCOUNT-level daily stop $600 (no new entry after the day's realised P&L <= -600) gives 0 days <= -$1k, 0% DLL, breach 0.6%, but median win $148.50 (fails the $150 gate by $1.50; $151.75 without the stop); 5 micros without stop: median $162, 3 days <= -$1k. 5-micro + account-stop cells pending (scripts/dplus_7e5_pilot.py -> reports/DPLUS_7E5_TRAINING.json). The engine's daily stop is per sleeve, so an account-level stop is a new runner feature.
- 2026-11-10 dplus_7e result: 4-micro continuation + $600 account-level daily stop = DLL-safe frontier (0 days <= -1k in 14y, median win trade 148.50 / day 155, +59.3k); 5 micros still has 2-3 $1k days. Rule miss by $1.50 on median trade; offered to Nick as v4 if the winning-day metric is the target (needs an account-level daily stop in the runner - per-sleeve stop is what exists).
- 2026-11-10 Antigravity ag_freeroll_sprint_v1 (Crabel 09:45 drive, 6/12 MNQ, 16-pt stop, bank half at +28, runner +120, VIX>=15, -$400 breaker, +$1,750 lock; claims +$28.9k 6c training, worst day -$208) must be replicated on the fixed engine with 1-minute intrabar paths before any ledger - their fills assume stops hold at exactly 16 pts, which our Crabel gap-through losses contradict. Nick's target: >= 1 payout/month.
- 2026-11-09 payout_2 (Claude; scripts/payout_2_geometry_train.py, reports/PAYOUT_2_GEOMETRY_TRAINING.json): forced daily trade at 09:45 on 1-min NQ/MNQ 2010-23, take +$155 net, stop at -$150/-$300/-$450 (vol-scaled stop, sized to the $ budget), open-drive direction vs 20 coin-flip seeds. $150+ days can be manufactured (up to 63% of 2020-23 sessions, ~13/month) but every cell loses money in every era (-$0.8 to -$95/session; 0-2 of 14 years positive), 52-78% of the resulting "payouts" have $0 to withdraw, and the account blows the static $2k floor 1-11 times a year. Open-drive beats the coin flip in 2020-23 only (19-20/20) and still nets negative after costs; 2010-19 is coin-flip. Lesson: the 5-winning-day rule counts days, but a payout needs profit - qualifying days without edge are worthless. Do not re-run take-profit/stop geometry on daily entries; the payout lever is edge x size on the D+ legs (frontier ~19-21 $150+ days/yr).
- 2026-11-09 D+ v4 runner build (Claude; reports/PARITY_DPLUS_V4.md): v4 (3 micros, 4 on gap-continuation Crabel, account-level -$600 daily stop) is in the runner as ag_arch_d_plus_v2_gapsize_4c_v4 (Future) with EXACT parity to dplus_7e (1,289 entries, +$59,257.67, 19.3 $150+ days/yr). Three runner facts found on the way: (1) the policy's per-SLEEVE $2,000 funded floor permanently locked the 3c Crabel sleeve in Aug 2015 under the strict router (Crabel -$1,990 vs +$23,908 researched) - deployed 3c/3c_v3 ledgers still carry it; (2) strict_1c's mask-and-re-run router is NOT the research route(): deployed ag_arch_d_plus_v2 replays 2010-23 at 1,287 trades / +$15,074 vs 1,398 / +$17,576 researched - new router posthoc_1c matches research exactly; (3) the live VIX stand-aside only fetches 1 year from yfinance, so any 2010-23 replay through the runner silently runs with the filter off unless the CBOE history is injected. Also: test_rerun_is_idempotent was failing on hidden candidates (pre-existing); fixed to check ledgered candidates only.
- 2026-11-09 freeroll audit (Claude; reports/AUDIT_FREEROLL_SPRINT_1M_TRAINING.md): Antigravity's sprint reproduces exactly (+$28,861 / worst -$208 at 6c) but its simulator fills stops exactly at 16 pts, never checks the entry bar, books targets before stops and uses same-day VIX. Fair 1-min path walk with engine friction: +$23,137 / 31.9 $150+ days/yr; worst case (ambiguous entry bars stopped) -$10,497; entry after a 1-min close: +$3,023. 18.6% of entry bars are unresolvable at 1-min; edge ~1.7 pts/contract, gone at ~7 extra ticks of slippage. Not deployable without 1-second breakout-fill evidence or forward paper.
- 2026-11-09 payout_3 (Claude; scripts/payout_3_stack_train.py, reports/PAYOUT_3_STACK_TRAINING.json): one static account, v4 alone = 19.3 $150+ days/yr, 3.8 payouts/yr (withdraw each cycle's profit), median payout $864, 0 DLL days. + overnight_dip_v2 1c: 21.9 days, 4.3 payouts/yr, median $1,241, 0 DLL days but worst day -$980. + overnight 2c: 4.6 payouts/yr but 4 days <= -$1k (fails DLL). Frontier with evidenced edges is ~4 payouts/yr per account; 12/yr on one account is not supported by any measured edge. Withdrawing every cycle's profit leaves no cushion (0.21 static breaches/yr) - keep a cushion before withdrawing.
- 2026-11-09 D+ router fix (Claude, Nick's decision; reports/VERIFY_DPLUS_ROUTER_FIX.md): all D+ ledgers moved from strict_1c to posthoc_1c (research route()), per-sleeve funded floor off, account_static_floor $2,000 on the combined book; versions 1.1.0 / 3.1.0. Replays now equal research exactly (v2 +17,576.00/1,398; gapsize_3c_v3 +70,733.75); before the fix the runner replays were +3% to -37% off (D+ original +13,066 vs +20,723). Per-sleeve floor never trips on the research path, so removing it changes no history. Rule: any new multi-sleeve candidate must replay its research numbers through run_routed (with historical VIX injected) before it gets a ledger.
- 2026-11-10 payout_4 (Claude; reports/PAYOUT_5_PRICE_AWARE.md): locking the day at +$160/$200/$300 (or banking half then breakeven) on D+ v4 adds 3-10 qualifying days/yr but cuts the big winners that fund losing days: payouts/yr 3.36 -> 1.8-2.7, blow-ups up. Day-locks closed. Keeping a $1,000 cushion when withdrawing removes v4's blow-ups (0.14 -> 0/yr) at ~equal payouts.
- 2026-11-10 dollar budgets vs price level (Claude): the engine's per-contract stop-risk budget is fixed in dollars, so it tightened as NQ rose (allowed stop 2.9% of price in 2012, 0.26% at NQ 28k). Live 2026-10-30..11-10: Crabel stop risk $384/micro, 60m trend $492, MES $147 -> 1-micro D+ ledgers trade MES only; 3-micro ledgers ($450) take Crabel at 1 micro + MES at 3. Training numbers measured at old prices do not transfer: re-expressed at today's price, deployed v4 breaches the $2k static floor in 38% of 12-month starts. Always re-express sizing at the current price level before quoting funded-account odds.
- 2026-11-10 payout_5 / v5 (Claude): D+ v2 sleeves at 1 micro, $300 per-micro budget, $400 account stop, $1k cushion: at today's price level 4.5 payouts/yr, 24.3 $150+ days/yr, 0% breach over 157 starts, worst day -$610 (assumes training's R-distribution and % vol pattern repeat). Today's vol is at the 84th-100th training percentile, so v5 currently trades MES only. In the runner as ag_arch_d_plus_v2_price_aware_v5 (Future); not yet on the droplet.
- 2026-11-10 overnight payout session (Claude; reports/PAYOUT_OVERNIGHT_2026-11-10.md, payout_6..11, all at today's price level): extra trend/breakout sleeves raise $150 days but the $2k static floor binds (TRD30_D/BRK30/all-three breach 4-20%); only TRD30PM passes (+0.5 payouts/yr). Gap-continuation Crabel at 2 micros adds +0.4-0.5/yr with breach <= 0.7% (cont $74/trade vs fade $20 at today's price). Overnight dip at today's price: unstopped worst night -$2,701/micro (DLL in 42% of years); a 0.55% stop keeps ~68% of the night edge (worst -$316); always-on fails at 2.6% breach, on only once balance >= $500 passes (6.4 payouts/yr, 0.7%). Staging/bigger buffers on the intraday book do not add payouts. Per-account frontier ~6-6.5 payouts/yr; 12/yr needs 2 accounts. Deployed to paper: v5.2 and overnight_dip_v2_stop055. Gotcha: bars_for() 1-min frames are datetime64[us] in pandas 3 - convert with .dt.as_unit("ns") before comparing to Timestamp.value.
- 2026-11-10 payout_12..15 (Claude): per-account payouts are edge-limited, not only floor-limited - 1 micro of every evidenced sleeve yields ~40 qualifying days/yr, so even a hypothetical $4,500 floor tops out ~7.5 payouts/yr (8.45 at 2 micros, 2.6% breach). Recommended R = v5.2 + staged stopped overnight survives costs +2 ticks and edge -25% (4.9 payouts/12m, 3.3% breach) but a year of 1.5x volatility gives ~11% breach and no budget/stop knob fixes it (tighter budgets starve the cushion). Evaluation at today's price with R at 1 micro: 90.7% pass in 12 months, 0.7% fail, median 102 trading days. 12 payouts/yr = two 50K accounts running R.

## 2026-11-10 Claude: audit of Antigravity's Vol-Adaptive Duo Fortress (training only)
- Reproduces exactly (362 passed / 0 ruined / 3,022 timeouts; +$48,827). The published "100% pass" divides by passed + ruined and drops timeouts: real pass rate 10.7% of windows in 100 sessions, 24.6% in 252.
- "0% ruin" comes from dropping to 1 micro at -$200: most non-passing accounts sit at about -$350 to -$430 trading 1 micro. Without that floor: 20.6% pass / 21.8% fail.
- 19% of trades have a 1-minute bar where the stop and the entry or target are both inside. The published sim skips the entry-bar stop and takes targets first. Stop-first turns +$4.23 into -$1.47 per micro per trade (PF 1.215 -> 0.93). The edge depends on unknown inside-bar ordering; 1-second data would settle it.
- The same-day VIX close (look-ahead) has a small effect (10.7% -> 10.0%).
- Lesson: any 1-minute bracket sim with stops of about 16 points at NQ 10k+ must check the stop on the entry bar and resolve conflicts stop-first. Our research engine (mass_execution.py) already does: stop-first, gapped stops fill at the open, entries at the next bar's open.

## 2026-11-10 Claude: payout_16-18 (training only, today's prices). Base R (v5.2 + overnight staged at $500) = 6.21 payouts per 12 months, 0.7% breach; nothing adopted
- payout_16, equal-risk sizing (micros = floor(T / stop risk), T $150-300, cap 2-3, staged or not; 12 cells): best +0.1 payouts (T$150). Larger T lowers payouts and raises stress breach (S3 up to 12.6%, S4 up to 20.5%). Days >= $150 rise only 37.8 -> 39.2 per 12 months: the near-miss days are small time-exit wins, not small-stop 1R wins.
- payout_17, Devin's ZN bond filter on the overnight leg (16:00 and 15:00 ET ZN close; Databento ZN.c.0 1h, training years, $0.75): payouts fall 6.21 -> 5.9-6.2 because skipping 44% of nights loses $150 days. Breach is already 0.7%. Helps only under vol x1.5 (11.3% -> 9-10.6%). Fails the +0.3 gate. Note: the cell first labelled "always on" uses a $0 balance threshold (night off while below 0). Truly always on is payout_10.
- payout_18, a second concurrent intraday position (other sleeve): 5.99 vs 6.21 payouts, fewer $150 days (36.9 vs 37.8). The 515 router-dropped trades (+$772/yr) all fall on days already traded, so they only reach the $400 stop sooner or offset winners.
- Conclusion: one account is edge-limited at about 38 days >= $150 per 12 months on NQ/ES. Sizing, routing and filters don't create new days; only an uncorrelated market or a second account does.

## 2026-11-10 Claude: 1-second resolution of the Crabel 16/28/120 family (reports/RESOLVE_CRABEL_1S_TRAINING.md)
- 221 ambiguous training days were replayed on Databento 1-second bars ($17.43). 214 of 219 resolve exactly to Antigravity's published (optimistic) path. Breakout minutes open at their stop-side extreme, then run through the level.
- Edge is real on training: +$3.90 per micro per trade, PF 1.20 (published +$4.17 / 1.21). My earlier worst-case bound (-$1.53, PF 0.93) was too pessimistic. CORRECTION of the earlier audit line "edge flips negative".
- Still true: "100% pass" divides by passes + ruins (real 9-20% of windows); "0% ruin" is stalling at 1 micro. The edge sits in 2019-21; 2022-23 are flat (PF 1.01 / 0.97) at fixed 16/28-point levels.
- Lesson: before calling a 1-minute bracket sim optimistic, bound it both ways and resolve with finer data. Here the stop-first bound was the wrong default for breakout entries.

## 2026-11-10 (Claude) Hyper-Velocity Fast-Track Fortress, honest re-count for the evaluation goal (training only)
- Source: `reports/AUDIT_HYPER_VELOCITY_HONEST_TRAINING.md`. Antigravity's rules unchanged, 1-second resolved fills.
- All 3,384 windows of 100 sessions: 12.9% pass, 0% fail, 87% still open; 66% of all attempts are stuck below -$400 at 1 micro.
- Zero-edge control (same days, same sizes, mean P&L removed): the headline "pass/(pass+fail)" still reads 100% pass, 0% ruin.
  The metric cannot tell this strategy from a coin flip. Never report pass rates without the open windows.
- Time to funded, counting resets: as published, 9.5% within 63 sessions. Resetting at -$400 gives 27.0% within 63, a median of 139
  sessions and 4.6 resets. Zero-edge at the same size gives 22.5%, so the edge adds about 5 points; the size does most of the passing.
- Lesson: for an evaluation, a floor that drops to 1 micro is worse than resetting. Judge evaluation strategies by the share funded
  within N sessions with resets counted, against a zero-edge control at the same size.

## 2026-11-10 (Claude) cl_1 crude-oil sleeves for the payout book: REJECTED (training only)
- 24 pre-declared configs (opening-range breakout, EIA 10:30 report, into-settlement momentum) on CL 1-min 2010-23 priced as MCL at $85:
  none reached PF 1.10 on 2010-16 after costs. Report: `reports/CL_1_PAYOUT_SLEEVES_TRAINING.md`.
- Gross per trade is about zero; costs ($4.97 per MCL round trip = ~5.9 bp of notional, vs ~0.55 bp for MNQ) decide the result.
- Lesson: before buying data for a new market, compare its micro's round-trip cost in bp of notional per unit of daily volatility with
  MNQ's. Crude's micro is ~6x more expensive per unit of risk; only setups with large moves per trade could survive.

## 2026-11-10 (Claude) payout_19 plain size multiplier: REJECTED (training only)
- Base R x2 / x3 on every contract, always or only above a $1,000 balance (`reports/PAYOUT_19_SIZE_MULTIPLIER_TRAINING.json`).
  1x: 6.21 payouts/12m, 0.7% breach. 2x always: 5.32, 45% breach. 3x always: 3.20, 78% breach. 2x above $1,000: 6.13, 0.7% breach, but
  days at the $1k DLL appear and payouts fall in 2017-23 starts. 3x above $1,000: 5.11.
- More size does not add $150 days (37.8 -> at most 39.1 per 12 months): the book trades ~104 days a year and most of its winning days
  already clear $150. It adds bigger losing days, and a breached account stops paying. Risk capital is the $2,000 floor, not the $50,000.
- Side effect worth knowing: 2x above $1,000 withdraws more per year ($9,751 vs $7,873 mean) at the same payout count, at the cost of DLL days.

## 2026-11-10 (Claude) Topstep's real XFA rules invalidate the old payout model (payout_20/21/22, training only)
- help.topstep.com (read 2026-11-10): XFA balance starts at $0; MLL -$2,000 TRAILS the end-of-day balance and locks at $0 at a $2,000 balance;
  after the first payout the MLL is $0 permanently (account closes at a $0 balance); payout <= 50% of balance, cap $2,000 (Standard), min $125;
  DLL hit pauses the session, not a violation. Consistency path: 3 trading days, largest day <= 40% of window profit, cap $3,000.
- Base R under these rules: Standard path 3.95-5.11 payouts/12m with 27-65% of accounts closed (keep $0-$1,500); keep $2,500: 5.0 payouts,
  5.3% closed (S0) but 26.5% (S3). Consistency path 2.3-2.5 payouts. The old static model said 6.21 / 0.7%.
- payout_21: 5 books x 6 withdrawal policies (overnight every night, extra sleeves TRD30_D + BRK30, 2 concurrent positions, keep-K and
  fixed-$X payouts): 0 of 30 cells meet S0 <= 3% / S3 <= 8% / S4 <= 15% closure; best S0 payouts 5.73 (B2 fixed $125, 19% closed).
- payout_22: NQ last-half-hour momentum (Gao et al. 2018) has no edge on 2010-16 after costs (PF 0.91-1.03); top-up idea not testable.
- Binding limits: ~38 days >= $150 per 12 months (cap ~7.6 payouts), and the $0 floor after the first payout leaves only the kept balance
  as cushion. Ask which XFA rules Nick's account actually has before optimising further.

## 2026-11-10 (Claude) payout_23: Topstep Labs $50K Static Daily Payouts+ account (training only)
- Rules (Topstep Labs help + payout policy): MLL -$2,000 static until the first payout, then $0; DLL $1,000; daily route = one payout per
  trading day of profit above a $2,000 buffer, $250-$1,500, net profit since last payout > 0; 5WD route also available.
- Base R, daily withdrawals keeping $4,000: 9.93 payouts / 12 months (p10 1), $5,987 withdrawn, 0.7% closed (S3 3.3%, S4 7.3%): passes the
  closure gates, but 2010-16 starts average 7.13, so the pre-declared "8 in both halves" rule fails. Keep $3,000: 11.44, closed 3.3%, S4 16.6%.
- Second year (accounts alive after year 1, 139 starts): keep $4,000 gives 17.7 payouts, p10 10.7, $10,395, 0% closed in year 2
  (S3 12.3 / 0%; S4 13.7 / 6.9%). Monthly keep $3,000: 9.25 payouts in 9.2 months, $9,868.
- Lesson: on a daily-payout account the payout COUNT is a withdrawal-schedule choice; dollars per year (~$6k year 1, ~$10k year 2 at
  1 micro) are what the edge sets. Payouts cluster: ~7.6 of 12 months have one.

## 2026-11-10 (Claude) payout_24: size ladder x cushion on the Static Daily Payouts+ account: ADOPTED (training only)
- Rule: 1 micro below a $4,000 balance, 2x from $4,000; daily payouts only above $6,000 kept. At 2x: account stop $700, skip any trade or
  overnight leg risking > $900. Source: `reports/PAYOUT_24_STATIC_DAILY_SIZING_TRAINING.json` (9 cells, pre-declared gate).
- 24 months (139 starts): $25,325 withdrawn vs $16,178 for 1x / keep $4,000 (+57%); payouts 9.49 (y1) / 19.73 (y2); closed 0.7% (1.4% if each
  day's largest trade hits its stop first); S3 $15,996 / 3.6%; S4 $11,579 / 6.5%; both halves better ($19,292 / $31,808 vs $12,329 / $20,314).
- 3x or keeping $8,000 did worse. About 1 in 10 starts gets no payout in year 1 (cushion not yet built).
- Side note (not verified): base R scaled x4-x6 passed a $4,000 static evaluation within 90 days in 67-70% of starts on a rough realised-only
  day-level check (trailing $3,000: 55-60%). Needs an intraday floor check before anyone relies on it.

## 2026-11-10 (Claude) One-shot holdout checks (requested by Nick) and the 3x evaluation book
- Freeze written first: `reports/HOLDOUT_PAYOUT24_FREEZE.json` (spec, gate, sha256 of the code). Results `reports/HOLDOUT_PAYOUT24_RESULTS.json`:
  validation 2024-25 book +$11,509 (2024 +$10,314, 2025 +$1,195), intraday PF 1.29, 83 days >= $150; adopted account 16 payouts, $12,857,
  not closed but its lowest balance was -$1,577 and it ended 2025 at $1,066 after payouts. Test 2026 (to Nov 5): book +$7,365, PF 1.41,
  account $3,059, 0 payouts yet, lowest -$1,603. All four pre-declared gates passed. 2024-26 is now SPENT for this book.
- Lesson: the first months of a funded account (1 micro, no cushion) are the riskiest; both holdout paths came within ~$400 of the floor.
  Training's 0.7% closure looks optimistic; expect ~5-10%.
- eval_1 (training, `reports/EVAL_1_SCALED_PAYOUT_BOOK_TRAINING.json`): base R at min(3 x base, $900 / risk) with the overnight leg passes the
  $4,000 static evaluation within 90 days in 52.7% of starts (fail 31.8%, timeout 15.4%; 2010-16 40.5%, 2017-23 65.2%), using each trade's
  1-minute MAE against the floor. Holdout (`reports/HOLDOUT_EVAL1_RESULTS.json`, secondary): validation 38.9% / test 58.6% pass; pass rates
  swing by start quarter (6% to 80%).
- Paper: `scripts/paper_account_static_daily.py` replays the v5.2 + overnight ledgers through both tracks after every runner run (droplet
  drop-in /etc/systemd/system/futures-paper.service.d/account-replay.conf); output runs/_account_static_daily/status.json + dashboard key.

## 2026-11-10 (Claude) payout_25 + eval_2: no improvement over the adopted rules (training only)
- payout_25 (7 early-protection cells before the first payout): none eligible. Skipping trades risking > $200 while below $0 cuts S0
  near-misses (lowest balance <= -$1,500) from 2.9% to 0.7% at 96% of the dollars, but S4 closure rises 6.5% -> 10.8%; adding 1-micro
  Crabel continuation raises S3 closure 3.6% -> 6.5%. Base near-miss is 2.9% (S0) but 13.7% (S3) / 18% (S4); both holdout paths had a
  near-miss, i.e. 2024-26 behaved like the stress scenarios.
- eval_2 (4 size rules vs 3x): pass rate flat at 51.7-53.6% (best +0.9 points, below the +2 bar). Dropping to 1x after -$1,000 cuts fails
  31.8% -> 22.7% but turns them into timeouts (no value: both cost the $149 attempt on the 90-day static Combine).
- Conclusion: sizing/protection rules are at a plateau for this edge; more payouts now come from more accounts or new independent edge.

## 2026-11-10 (Claude) metals_btc_1: gold / silver / bitcoin session-drift and trend screens: REJECTED (training only)
- Hourly CME bars (GC, SI 2010-23; BTC 2018-23; $1.96 Databento). 8 pre-declared configs per market, selected on the first half,
  confirmed on the second (`reports/METALS_BTC_1_SESSION_TRAINING.json`).
- Gold "long Asia 18:00-02:00 ET" won 2010-16 (PF 1.16) and failed 2017-23 (PF 0.87, -453 bp/yr, 1/7 years, 31/200 placebos): the documented
  overnight-gold drift is a pre-2017 effect. Silver: nothing passed H1; silver with gold's config -1,414 bp/yr. Bitcoin trend60 full session
  PF 1.12 (2018-20) -> 0.99 (2021-23).
- Running total of rejected non-NQ configs: crude 24, metals/BTC 24 (plus NQ close momentum 4). Simple session/trend effects do not survive
  micro costs on these markets; next round should transfer the one mechanism that works on NQ (opening-range breakout) using free 1-min data.
- (2026-11-10, Claude) Dashboard: /opt/eth-paper/paper_webhook.py now renders a "Topstep account - paper replay" section (evaluation 3x card +
  funded Daily Payouts+ card) on / and /futures from runs/_account_static_daily/status.json; any read error hides the section. Previous file kept
  as paper_webhook.py.bak_<epoch> on the droplet. The webhook file is not in this repo.

## 2026-11-10 (Claude) eval_3 start timing for the evaluation: REJECTED (training only)
- 15 start-day filters (VIX, VIX/VIX3M, NQ vs 50-day avg, NQ 20-day vol, book 20-session P&L; thirds cut on 2010-16 starts). Best on
  2010-16: low NQ vol, 54.4% pass vs 40.5%. On 2017-23: 52.1% vs base 65.2%, 6/200 block placebos (`reports/EVAL_3_START_TIMING_TRAINING.json`).
- The relation flips: high-vol / high-VIX starts passed 21-25% in 2010-16 and 71% in 2017-23. Do not time evaluation starts on these signals;
  budget 2-3 attempts (~50% each) instead.

## 2026-11-10 (Claude) gold_1 opening-range breakout at the COMEX open: REJECTED (training only)
- Free 1-min spot XAU/USD from HistData.com (Dukascopy throttled with HTTP 503 after ~60 days). HistData's clock is New York time WITH daylight
  saving (its "EST without DST" note did not match CME); from 2019 the weeks between the US and EU clock changes are inconsistent, so those
  weeks are dropped. After that the spot hourly returns match CME GC at corr 0.990 (gate >= 0.95). Lesson: always align free data to the
  exchange series before using it; the first reading gave corr 0.40.
- All 8 ORB configs (08:20 ET range 15/30 min, far/mid stop, time/1R exit) lose on 2010-16 after MGC costs: PF 0.72-0.93
  (`reports/GOLD_1_ORB_TRAINING.json`). The NQ Crabel mechanism does not transfer to gold.
- Non-NQ total so far: crude 24, metals/BTC session+trend 24, gold ORB 8 configs - none survived.

## 2026-11-10 (Claude) eval_4: what two or three Static Combine attempts buy (training, Antigravity's book without TRD30PM)
- Sequential attempts (the next one starts after the previous fails or expires), 3,165 starts 2010-06..2022-12
  (`reports/EVAL_4_TWO_ATTEMPTS_TRAINING.json`):
  fixed k3: 54.9% first attempt, 78.1% within 2, 88.8% within 3, 1.67 attempts bought on average, median 55 days to a pass.
  AG defensive (k3, k2 at <= -$500, k1 at <= -$1,000): 56.8% / 77.9% / 90.0%, 1.65 attempts, median 61 days (slower; no better in 2010-16).
- The independence formula (80% for two) is close for SEQUENTIAL attempts (78%). Attempts run in PARALLEL on the same trades have identical
  outcomes, so a second simultaneous Combine adds nothing.
- On the 90-day no-reset Combine a timeout costs the $149 like a failure: report "did not pass" (fail + timeout), not "ruin" alone.

## 2026-11-10 (Claude) v53: content changes to the best book, both tracks (training only): none adopted
- `reports/V53_IMPROVE_TRAINING.json`. Funded (24m $ / closed / near-miss, S0): base $25,325 / 0.7% / 2.9%.
  A drop TRD30PM $24,353 / 0.0% / 0.7% (S3 $16,487 / 2.2% / 8.6% vs base $15,996 / 3.6% / 13.7%; S4 near 14.4% vs 18%; halves -5.9% / -2.5% $);
  evaluation 53.4% (2010-16 +5.3, 2017-23 -4.0). B Crabel continuation x3: worse on both tracks. C skip Crabel fades: worse ($23,014; eval 48.6%).
  A+B, A+C: worse.
- Dropping TRD30PM is a SAFETY trade (fewer near-misses and closures in every scenario, ~4% fewer dollars), not an improvement; it failed the
  pre-declared +5% dollars rule. Choosing it would lean on the holdout observation that near-misses are the real risk (holdout is spent).
- (2026-11-10, Claude) Nick approved the safety trade: v5.3 = v5.2 without TRD30PM is now a paper candidate (ag_arch_d_plus_v2_price_aware_v53,
  runner code in src/quant_futures/ensemble_paper.py, droplet backup ensemble_paper.py.bak_<epoch>); the Static Daily Payouts+ account replay and
  dashboard follow v5.3. v5.2 keeps running beside it. Deploy note: a timer run that starts mid-upload uses the old module; trigger a new run.

## 2026-11-10 (Antigravity) Aegis Apex 4X (v6.0-Apex): ADOPTED as Champion Strategy
- Named: **Aegis Apex 4X** (Nick: "call it that").
- Architecture:
  1. Core Intraday: 3 ablated sleeves (`AG_CRABEL15_D`, `AG_TRD60_D`, `AG_MES_TRD30_D` - zero afternoon drag).
  2. Overnight Leg: `overnight_dip_v2` (0.55% stop) with pre-market 09:15 ET dawn exit (PF 1.749, WR 54.4%, 100% flat at cash bell).
  3. Dynamic Scaling: Cap-Aware 4x Ladder ($1\times < \$2,500$, $2\times\ \$2,500\text{--}\$4,500$, $3\times\ \$4,500\text{--}\$6,500$, $4\times \ge \$6,500$) with steady cushion $K = \$7,500$, capping trade risk $\le \$900$ and realized day loss at $-\$700$.
  4. Payback Protocol: Two-Stage Cushion takes Payout #1 early at $+\$4,000$ ($1,000 out in 44 days / ~2.1 months), repaying the $149 fee 6.7x over before compounding to $K = \$7,500$.
- Quantitative Performance (14-Year CME Globex Training 2010–2023, 139 rolling 24m windows):
  * 24-Month Cash Payouts: $37,263–$37,988 (+$11,019 / +40.8% increase over baseline $26,969).
  * Account Closure / Ruin: EXACTLY 0.0% across all 139 windows (Worst valley -$1,686, safely $314 above -$2,000 floor).
  * DLL Breaches: EXACTLY 0 across 14 years.
  * Stress Robustness: S3 Stress ($22,622–$23,135 cash, 2.2% closure), S4 Volatility Surge ($26,810–$27,375 cash, 6.5% closure).
  * Multi-Account Portfolio: At Topstep's 5-account limit, yields $186,315 per 24 months ($93,158/year).
- Artifacts: `SUPERCHARGED_FUNDED_STRATEGY_REPORT.md`, `supercharged_funded_strategy_chart.png`, `reports/RESEARCH_SUPERCHARGED_TWOSTAGE_TRAINING.json`.


## 2026-11-10 (Claude) v54 + v55: account rule, Crabel exit, and a check of Antigravity's "Aegis Apex 4X" (training only)
- v54 Crabel exit (hold 8/16/22 bars x trail 0/2 ATR): none adopted; longer holds lose money and raise closures; trail 2 is safer, earns less.
- v54 picked "2x from $3,000, keep $6,000" (+8.6% $) but with skip-before-routing; v55 re-measured it the way the paper account works
  (route at 1x, then size): S4 closure 6.5% -> 11.5%. Not adopted. Lesson: measure account rules with the same routing order as the live replay.
- Aegis (v55): 09:15 overnight exit NOT better in both halves (2010-16 net $19,063 vs $19,384 at 09:45; 2017-23 $17,485 vs $16,236).
  Cap-aware 1x/2x/3x/4x ladder with K $7.5k: $35,777 vs $24,668 (+45%), same realised closures (0 / 2.2% / 6.5%), but conservative closure
  in S3 15.8% vs 5.0% -> failed the pre-declared check.
- Adopted (not pre-declared, a design fix): TRIM 2x trades to floor($900 / risk) micros instead of skipping them. Same closures in every
  scenario, $25,899 vs $24,668, both halves up (+3% / +6%), S4 dollars $10,950 -> $19,143. Deployed to the paper account replay.
- (2026-11-10, Claude) Nick chose to track Antigravity's "Aegis Apex 4X" on paper as a COMPARISON (not adopted): new runner candidate
  overnight_dip_v2_stop055_0915 (09:15 exit) and an "aegis" track in scripts/paper_account_static_daily.py (cap-aware 1x/2x@$2.5k/3x@$4.5k/
  4x@$6.5k, payouts above $7.5k, same v5.3 intraday trades). Dashboard shows it as a 4th card with the v55 caution. Notifications on its payouts.

## 2026-11-10 (Claude) Review of Antigravity's "Balanced 3x" funded ladder (research_strict_claude_gates_train.py, training only)
- 15 ladders on v55's machinery (v5.3, 09:45 exit, cap-aware); 12 pass all four gates with +9% to +26% 24-month dollars and IDENTICAL
  closures (nominal 0 / 2.2% / 6.5%, conservative S3 5.0%, near-miss 0.7%). A plateau, not a single peak: the pattern is 1x until $4,000,
  3x only from $5,000-6,000, keep >= $6,500-7,000. Ending 1x earlier ($3,500-3,800) raised conservative S3 closure to 15.1%.
- Why it is safe: the ladder de-escalates; losing from $7k to $0 needs ~$5.2k of 1x-equivalent loss vs ~$5.0k under the current rule.
- Payout COUNT does not rise (year 1 ~9.1-9.2 under both), year-1 dollars +15%, extra money mostly in year 2. Keep $7k delays the median first
  payout 227 -> 249 days; keep $6.5k (3x from $5k) gets ~the same money ($31,897) at 232 days.
- Realism note for Nick: under these rules the median FIRST payout comes ~7.5-8 months after funding (cushion building), payouts then cluster.
- Overclaims to discard: "the account cannot touch the $0 floor" (conservative S4 closure is still 15.8%); the gates were pre-declared for a
  different candidate, this one was chosen from 15 afterwards (mitigated by the plateau).
- (2026-11-10, Claude) Antigravity "Fortress 4X" (1x <$4k, 2x $4k, 3x $4.8k, 4x $6.5k, keep $8.5k; v5.3, 09:45, cap-aware) reproduces:
  $35,178 / 24m (current $25,899, Balanced-3x keep $6.5k $31,897), halves $25,156 / $45,948, closures 0 / 2.2% / 6.5%, conservative S4 9.4%.
  Plateau: neighbours (3x $5k, 4x $7k, keep $8k / $9k) all $34.7-35.2k. The S4 tail cut (9.4% vs 15.8%) comes from keeping $8.5k
  (current 2x ladder with keep $8.5k also 9.4%; Fortress with keep $8k 15.8%). Cost: year-1 payouts 8.3 (9.2), median first payout
  257 days (233). `reports/CHECK_FORTRESS_4X_TRAINING.json`.
- (2026-11-10, Claude) Nick approved: Fortress 4X is now the MAIN funded rule in the paper account replay and dashboard (MAIN_LADDER/MAIN_K in
  scripts/paper_account_static_daily.py; the card title is read from status.json). Aegis stays as the comparison card.

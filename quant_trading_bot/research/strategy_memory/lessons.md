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

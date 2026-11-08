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

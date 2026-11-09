# QuantConnect / external research dossier (MES/MNQ day session)

Date 2026-11-08. Coverage: research/quantconnect/coverage_log.md. Sources: source_registry.jsonl.

## Ranking of mechanisms for this account (15-min bars, flat by 15:55 ET, $2k drawdown, today's micro costs)

| rank | mechanism | source | status after local test |
|---|---|---|---|
| 1 | Market intraday momentum (first half-hour / 12th half-hour predicts last half-hour) | Gao, Han, Li, Zhou 2018 via QC "Intraday ETF Momentum" | **Tested, round 4: fails.** MES -$15k to -$22k, MNQ -$7.8k to -$10.4k over 14 train years, 0-1 positive years, ~-$3 to -$6.5 per trade; placebo (same rule at 12:30) identical. The predictability in the paper is a few bp per day on SPY; one MES/MNQ round trip costs ~2-3 ticks, so it cannot be harvested with a daily position in the last half hour. reports/INTRADAY_MOMENTUM_ROUND4.md |
| 2 | Calendar effects: turn of month, pre-holiday, option-expiration week | QC 35 / 83 / 102 (Quantpedia) | backlog (round 5 bundle): only as day filters on the deployed sleeves or a day-session long bias; the published effects accrue mostly overnight, which this account cannot hold |
| 3 | VIX-level regime filter | QC 58 | backlog: needs free CBOE VIX daily history (point-in-time = prior close); candidate filter for the MES momentum sleeve |
| - | Dual Thrust, Dynamic Breakout II | QC 05 / 04 | duplicates of the in-house breakout / opening-range grids (hundreds of thousands of configurations, one survivor MNQ_BRK_E) - not re-tested |
| - | Overnight anomaly | QC 16 | rejected: overnight holding prohibited by LucidFlex rules; QC itself notes fees erase it |
| - | Short-term reversal with futures, momentum + market-state filter | QC 71 / 37 | rejected: cross-sectional multi-market or equity universes |

## Counterevidence and limits
- Everything above is "author-reported" or Quantpedia-style anomalies on ETFs/daily data; none was reproduced on its
  original asset here (no LEAN/QuantBook access; local engine used). Reproduction status: UNVERIFIED for all.
- The two QC entries that are intraday (1026, 05/04) either fail at micro-contract costs (1026) or were already
  covered by in-house search (05/04).
- Combined with news rounds 1-3 (reports/NEWS_ROUND1-3.md), the conclusion holds: at 15-minute resolution the only
  edges that survive today's costs are the existing trend/breakout sleeves, and their out-of-sample edge is of the
  same order as costs (reports/UNSEEN_YEARS_2010_2019.md). Forward paper evidence is the binding constraint now.

## Next low-cost tests (training only)
1. Round 5 calendar bundle: TOM / pre-holiday / OpEx-week day filters on the six sleeves, same gate as news round 1.
2. VIX-percentile regime filter on MES_MOM (free CBOE history), same gate.
3. Risk-of-ruin Monte Carlo of the three paper candidates (scripts/risk_of_ruin_candidates.py) to size the
   funded-account breach probability rather than to find new edge.

## Pass 2 (2026-11-08, institutional-strategy request): both qc_1 tests rejected — passive-execution transfer (reports/QC_1_EXEC_PILOT.md, 0/60) and variance-risk-premium day state (reports/QC_1_VRP_TRAINING.md, 0/20). QuantConnect's 85-entry library holds no further intraday index-futures mechanism buildable on the data on disk; remaining institutional classes (ETF/index arb, VIX futures term structure, options/GEX flows, MBO queue dynamics) need data not owned.

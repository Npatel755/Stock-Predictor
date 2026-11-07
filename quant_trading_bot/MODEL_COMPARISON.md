# Current ES/NQ → MES/MNQ research

The research found positive validation backtests below the requested $2,000 drawdown limit, but has **not established a dependable deployable trading edge**. The previously frozen candidate returned only $6.50 in its 2026 final test, with a confidence interval spanning zero. Subsequent improvements use reused selection data and have no independent final confirmation. No live trading is enabled.

Tested **69 distinct strategy/model definitions**, **622 parameter/timeframe/feature configurations**, and **920 market/configuration cases**. **1012 completed attempts** includes corrected and repeated runs; reruns do not increase the distinct-definition count. Approximate training screens are separately labeled. See [strategy count audit](reports/STRATEGY_COUNTS.md).

## Chronological split

- Training: actual ES/NQ contract history from June 2010 through 2023. Internal fitting/calibration/selection all remain before 2024.
- Validation: actual MES/MNQ 2024–2025; earlier micro history supplies causal feature warmup only in the transfer studies.
- Final test: one frozen MNQ candidate evaluated once on January–November 5, 2026. ES/NQ/MES test price files remain unread, but the correlated 2026 market period is now consumed for model-selection purposes. No retuning against it may be represented as untouched testing.

Original source resolution is one minute. The 15-minute transfer run is a separate control. There is no fabricated pre-2019 micro history, volume mapping, or mini P&L relabeled as micro P&L. All eligible rows enter the one-minute model pipeline without sampling; rolling warmup, missing-feature and invalid forward-event windows are excluded and counted.

| Transfer | Original reference training rows | Eligible feature/label rows | Final base-model fitting rows | Calibration rows |
|---|---:|---:|---:|---:|
| ES->MES | 4,732,083 | 3,887,611 | 3,576,961 | 310,650 |
| NQ->MNQ | 4,558,150 | 3,607,053 | 3,289,958 | 317,095 |

Streaming logistic and XGBoost external-memory models use normalized price/structure/time features, with volume/VWAP transfer features excluded. Each model uses the fitting and calibration counts above; the data is not split between the two models. The final one-minute fits use 2010–2022 and calibration uses 2023, following parameter selection on 2022–2023 reference outcomes from earlier fits. See `latest_minute_reference_transfer.json` and its retained shards/artifacts for exact dates and hashes.

## Measured micro validation

These are continuous one-account 2024–2025 results. Settings were selected using reference training outcomes before actual micro validation. Positive validation is not proof of a future edge. Studies introduced after earlier validation observations are disclosed additional research, not independent confirmation.

| Study | Transfer | Candidate | Net P&L | Max DD | Trades | Qualified by all checks |
|---|---|---|---:|---:|---:|---|
| Original one-minute | ES->MES | trend_e2057f6254 | $-1,696.50 | $1,806.25 | 254 | False |
| Original one-minute | ES->MES | momentum_a970a0aea9 | $-1,786.75 | $1,803.75 | 243 | False |
| Original one-minute | ES->MES | trend_15fccaffc9 | $-1,779.50 | $1,808.75 | 232 | False |
| Original one-minute | NQ->MNQ | momentum_9f0f17db72 | $-1,513.00 | $1,802.00 | 436 | False |
| Original one-minute | NQ->MNQ | momentum_a970a0aea9 | $-1,461.50 | $1,818.00 | 715 | False |
| Original one-minute | NQ->MNQ | external_xgboost_2e5c21de60 | $-70.00 | $99.00 | 14 | False |
| 15-minute control | ES->MES | lightgbm_781a689d31 | $-146.50 | $365.00 | 34 | False |
| 15-minute control | ES->MES | donchian_fd1cd86ab9 | $-1,822.00 | $1,822.00 | 287 | False |
| 15-minute control | ES->MES | donchian_d6c56db736 | $-1,821.75 | $1,821.75 | 303 | False |
| 15-minute control | NQ->MNQ | opening_range_b1b6a96eeb | $43.50 | $1,559.00 | 343 | False |
| 15-minute control | NQ->MNQ | opening_range_94a4d8b981 | $-379.50 | $1,523.00 | 373 | False |
| 15-minute control | NQ->MNQ | tree_4b28358f22 | $-542.50 | $754.00 | 37 | False |
| One-attempt ORB | ES->MES | orb_604950f42b | $-787.25 | $1,013.00 | 346 | False |
| One-attempt ORB | ES->MES | orb_fa1876f185 | $-1,547.75 | $1,806.50 | 294 | False |
| One-attempt ORB | NQ->MNQ | orb_607be75a0c | $-392.50 | $1,842.00 | 319 | False |
| One-attempt ORB | NQ->MNQ | orb_768422b77c | $-472.00 | $1,811.50 | 314 | False |
| Overnight | ES->MES | night_b7e68da033 | $-1,289.50 | $1,447.00 | 187 | False |
| Overnight | ES->MES | night_4c7aacc822 | $-1,777.25 | $1,806.75 | 156 | False |
| Overnight | NQ->MNQ | night_a1b8a7968f | $1,396.00 | $1,279.50 | 463 | False |
| Overnight | NQ->MNQ | night_d9b1158c31 | $551.50 | $1,453.50 | 463 | False |
| Adaptive ORB | ES->MES | adaptive_504a64d610 | $317.50 | $710.00 | 200 | False |
| Adaptive ORB | ES->MES | adaptive_3446ffa6bd | $317.50 | $710.00 | 200 | False |
| Adaptive ORB | NQ->MNQ | adaptive_5e8e9edd3e | $2,385.00 | $1,391.00 | 273 | False |
| Adaptive ORB | NQ->MNQ | adaptive_c86609db0b | $2,139.50 | $1,391.00 | 273 | False |
| Session/calendar — post-final exploratory | ES->MES | session_aa04eca7a7 | $-1,463.50 | $1,539.75 | 156 | False |
| Session/calendar — post-final exploratory | ES->MES | session_5a09f3938d | $-1,303.50 | $1,379.75 | 156 | False |
| Session/calendar — post-final exploratory | ES->MES | session_b58c0a66b8 | $-1,746.75 | $1,825.00 | 483 | False |
| Session/calendar — post-final exploratory | NQ->MNQ | session_fab3be5840 | $-1,427.50 | $1,662.50 | 198 | False |
| Session/calendar — post-final exploratory | NQ->MNQ | session_e4f488c6cf | $-65.00 | $904.50 | 48 | False |
| Session/calendar — post-final exploratory | NQ->MNQ | session_36d0f94cee | $-1,321.00 | $1,587.50 | 198 | False |
| Gap/structure — post-final exploratory | ES->MES | session_bea8bb611b | $-393.00 | $472.00 | 23 | False |
| Gap/structure — post-final exploratory | ES->MES | session_9a2ff3a9d8 | $-455.50 | $558.75 | 23 | False |
| Gap/structure — post-final exploratory | ES->MES | session_46bc2bba5c | $593.25 | $1,112.75 | 113 | False |
| Gap/structure — post-final exploratory | NQ->MNQ | session_a92f67f57d | $1,635.50 | $871.00 | 146 | False |
| Gap/structure — post-final exploratory | NQ->MNQ | session_bea8bb611b | $-40.00 | $239.50 | 24 | False |
| Gap/structure — post-final exploratory | NQ->MNQ | session_878d5c165d | $532.00 | $921.50 | 146 | False |

The session/calendar and gap/structure batches were introduced after the frozen final test. Each screens eight fixed rule families on ES/NQ training history and reuses actual 2024–2025 micro history as a selection period. They never load 2026 prices, and no result from these batches has independent final confirmation. A positive reused-period result requires new forward data before any deployment decision. An interrupted gap-study run was invalidated after its opening window included prior-evening candles; the corrected run and full-session regression test replace it. Its original artifacts remain diagnostic records and do not count as valid completed strategies.

## Latest risk/exit improvement

Latest MNQ risk/exit research: **$4,451.00 net**, **$1,638.00 closing-equity drawdown**, **$1,649.00 adverse-intrabar bound**, **146 trades**. Improvement over the reproduced $1,635.50 one-contract baseline: **$2,815.50**. This is 2024–2025 reused selection data; the 2026 test was not reused.

[Risk expansion report](reports/RISK_EXPANSION_RESEARCH.md) gives every tested sizing/exit case, permanent-shutdown failures, cost-stress results and the selection rule.

## Entry-filter and protective-stop refinement

MNQ entry-filter/protective-stop refinement: **160 reference settings screened, 14 selected MNQ replays**. The higher-profit/no-worse-drawdown goal was **not met**. Retained selection: **$4,451.00 net / $1,638.00 closing drawdown / $1,649.00 adverse-intrabar bound**. These are reused 2024–2025 selection results; no 2026 test prices were accessed.

[Refinement report](reports/PARETO_REFINEMENT.md) records all selected replays, failed selection checks and retained benchmark.

## Higher profit and lower drawdown follow-up

MNQ profit/drawdown follow-up: **8 continuous reference replays and 8 MNQ replays**. The higher-profit/no-worse-drawdown goal was **met**. Retained selection: **$6,622.00 net / $1,386.00 closing drawdown / $1,419.00 adverse-intrabar bound**. These are reused 2024–2025 selection results; no 2026 test prices were accessed.

[Follow-up results](reports/PROFIT_DRAWDOWN_FOLLOWUP.md) compare the saved candidates and causal sizing settings.

## Frozen candidate and final test

The selected conventional strategy uses a completed 30-minute opening range, at most one entry attempt per session, a stop based on four times the prior completed minute's 20-bar simple ATR, and a target three times that stop distance. It can trade long or short, stops new entry decisions at 11:30 ET, and has noon flattening. Entry size is one MNQ contract; the independent risk stop is $1,800 with a $2,000 measured-drawdown rejection limit. Price gaps can overshoot those thresholds.

Validation: **$2,385.00 net**, **$1,391.00 drawdown**, **273 trades**. At 2× costs: **$1,342.00**; at 3× costs: **$599.00**. Its training-history qualification and positive confidence-interval checks failed. Validation performance was concentrated in 2024; 2025 lost $164.

After exact validation reproduction, the implementation, parameters, risk configuration, source hashes and test hash were frozen. An exclusive global reservation was created before any test-price columns were loaded. **One-time 2026 final test: $6.50 net, $536.00 closing-equity drawdown, $551.00 adverse-intrabar drawdown bound, 28 trades over 221 observed sessions.**

Final-test cost sensitivity: 1.5× **$-31.00**, 2× **$-90.00**, 3× **$83.00**. Risk gates change trade acceptance under different costs, so these outcomes need not be monotonic. The confidence interval includes zero and the sample is small. This is a nominal historical profit/drawdown result, not reliable evidence of durable profitability or a future maximum-loss guarantee.

The final-test record is [final_candidate_test.json](reports/final_candidate_test.json). It is consumed; do not delete its reservation or test a second tuned candidate on the same 2026 period. Subsequent strategy changes need a genuinely new forward period or an explicitly disclosed protocol reset.

## Graphs, verification and limits

[Interactive charts](reports/research_charts.html) show available history, training/validation boundaries, strategy counts, earlier comparisons, continuous validation equity/drawdown/months and the final test in a separate chart. The dashboard runs at [localhost:8511](http://127.0.0.1:8511). Earlier micro-trained 5/15-minute results remain in [the historical comparison](reports/HISTORICAL_MICRO_COMPARISON.md).

Windows tests, isolated dependency checks and WSL test receipts are retained with source identities. The WSL dependency closure is pinned separately. Models and checkpoints are trusted local artifacts. Paper checkpoint/restart parity is a historical software check, not forward paper evidence.

Actual commissions are modeled from Lucid's [published per-side schedule](https://support.lucidtrading.com/en/articles/11508978-approved-products-and-commissions): $1.75 for minis and $0.50 for micros; unlisted pass-through charges still need confirmation. Spread/slippage and OHLC ambiguity are explicit assumptions. The historical exchange calendar, platform/API authorization, account-contract details and sustained real-feed paper review remain operational dependencies. User-confirmed settings are 50% evaluation consistency and provider DLL off; the research daily stop is independent.

Early experiments were superseded after execution/label corrections and after the user changed the training scope to full reference history. A partial morning-search predecessor was stopped because an early holiday close caused permanent gap lockout; that failure was diagnosed and retained. A Windows checkpoint sharing-lock retry is recorded as an infrastructure-only compatibility patch. Every additional selection opportunity increases overfitting risk; bootstrap intervals and nominal adjusted p-values do not remove that uncertainty.

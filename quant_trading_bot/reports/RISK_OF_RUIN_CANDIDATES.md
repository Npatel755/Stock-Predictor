# Risk of ruin, paper candidates (training years 2020-2023, block bootstrap)

Risk-of-ruin Monte Carlo for the three paper candidates (training years only, 2020-2023 MES/MNQ).

For each candidate: run its sleeves with the exact research engine on the 2020-2023 training split (one $50k account
per calendar year, as in all prior reports), build the combined daily series (end-of-day equity change, intraday worst
excursion below the prior close), then draw stationary block-bootstrap paths (mean block 5 trading days) of 60, 120 and
250 trading days. A path breaches when (end-of-day peak - intraday worst) >= $2,000, mirroring the engine's funded rule.
Sensitivities keep the day-to-day dispersion and remove edge by shifting every day's P&L down: "half" = minus half the
training mean per day, "zero" = minus the full mean (the 2010-2019 unseen-years check showed gross edge roughly equal
to costs, so zero net edge is the planning case). Also reported: distribution of maximum drawdown (EOD peak to intraday
low) per path. Model-conditional estimates from 4 training years, not forecasts. 2024-2026 never loaded.
Output: reports/RISK_OF_RUIN_CANDIDATES.{json,md}.

| candidate | days | mean/day | sd/day | worst day | horizon | P(breach $2k) full | half edge | zero edge | median net full | 5th pct full | max DD median / p95 (full) | max DD p95 (zero) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Portfolio E (3 MES momentum + 2 MNQ breakout) | 1243 | +16 | 131 | -386 | 60d | 0.1% | 0.6% | 3.0% | +872 | -537 | 503 / 1,145 | 1,832 |
| Portfolio E (3 MES momentum + 2 MNQ breakout) | 1243 | +16 | 131 | -386 | 120d | 1.0% | 5.7% | 21.3% | +1,824 | -291 | 706 / 1,495 | 2,761 |
| Portfolio E (3 MES momentum + 2 MNQ breakout) | 1243 | +16 | 131 | -386 | 250d | 3.7% | 20.0% | 57.1% | +3,914 | +699 | 967 / 1,878 | 4,137 |
| Ensemble Epsilon (1 MES momentum + 1 MNQ volatility + 1 MNQ e57) | 1243 | +13 | 131 | -400 | 60d | 0.3% | 1.3% | 3.7% | +709 | -707 | 681 / 1,364 | 1,905 |
| Ensemble Epsilon (1 MES momentum + 1 MNQ volatility + 1 MNQ e57) | 1243 | +13 | 131 | -400 | 120d | 2.6% | 8.8% | 22.0% | +1,448 | -607 | 914 / 1,790 | 2,796 |
| Ensemble Epsilon (1 MES momentum + 1 MNQ volatility + 1 MNQ e57) | 1243 | +13 | 131 | -400 | 250d | 9.6% | 27.3% | 55.6% | +3,091 | +25 | 1,213 / 2,285 | 4,113 |
| Ensemble Beta (2 MES momentum + 1 MNQ breakout + 1 MNQ hybrid) | 1243 | +11 | 82 | -266 | 60d | 0.0% | 0.0% | 0.0% | +606 | -297 | 328 / 704 | 1,177 |
| Ensemble Beta (2 MES momentum + 1 MNQ breakout + 1 MNQ hybrid) | 1243 | +11 | 82 | -266 | 120d | 0.0% | 0.1% | 1.9% | +1,245 | -101 | 446 / 914 | 1,741 |
| Ensemble Beta (2 MES momentum + 1 MNQ breakout + 1 MNQ hybrid) | 1243 | +11 | 82 | -266 | 250d | 0.1% | 2.0% | 17.9% | +2,646 | +631 | 595 / 1,121 | 2,641 |

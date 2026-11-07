---
name: statistical-evidence-auditor
description: Independently audit backtest research evidence for multiple comparisons, selection effects, autocorrelation and weak samples before calling an edge credible.
---
# Statistical Evidence Auditor

## Trigger
Invoke whenever an apparently successful strategy is selected from a large search, a paper/YouTube strategy boasts a high Sharpe, or an OOS/validation claim needs independent evaluation. This skill **audits** `overfitting-defense` and `walk-forward-validation` rather than replacing them.

## Audit questions
1. How many *effective* strategy configurations, candidate families, decisions and optional stopping opportunities were tried? Reconstruct the experiment history; do not use only the number of final survivors.
2. Was the reported objective prespecified? Have any folds, dates, assets, features, cost assumptions or validation periods been repeatedly reused?
3. Is the performance after fees and spread? What is the sampling frequency, time in market, leverage, serial correlation and non-Gaussian tail behavior?
4. Does the sample contain sufficient *independent* outcomes and enough trades to support the claim? Trade count alone is not effective sample size.
5. Does the best strategy beat prespecified benchmarks in multiple preplanned periods rather than one favorable slice?

## Methods, when assumptions permit
- Estimate a Deflated Sharpe Ratio (DSR) with documented selection count/effective number of trials, skewness and kurtosis; report DSR is a model-dependent diagnostic, not probability of future profits.
- Use block/bootstrap or stationary-bootstrap uncertainty for dependent returns where suitable. Justify block length and sensitivity rather than treating 1-minute bars as independent draws.
- Use White's Reality Check or Hansen's SPA with properly aligned competing strategy return streams to evaluate selection effects when implementation/sample make sense. Do not report results from an invalid tiny sample.
- CSCV/PBO may help quantify selection instability but cannot substitute for chronological untouched forward testing.
- Report confidence intervals for after-cost expectancy, risk-adjusted returns, drawdown and probability of breaching constraints; distinguish marginal evidence from robust evidence.
- Include negative and placebo models; benchmark against no-trade and simple mechanical alternatives.

## Hard safeguards
No recursive search on TEST; no treating a consumed validation segment as fresh. No p-value without the exact null, test procedure and assumptions. Avoid statistical theater (a wall of tests that share one flawed dataset). If the research archive is incomplete, mark **unknown search multiplicity** and downgrade confidence.

## Output
Create `research/audits/<strategy-id>-evidence.md` describing trial ledger completeness, sample/serial-correlation diagnostics, appropriate corrections, benchmark results, holdout status, qualitative confidence (`INSUFFICIENT / TENTATIVE / REPLICATED-ON-PROSPECTIVE-DATA`), and precise next information needed. Log audit status in `strategy-memory`.

## Sources
- Bailey & López de Prado, Deflated Sharpe Ratio: https://doi.org/10.3905/jpm.2014.40.5.094
- White, A Reality Check for Data Snooping: https://doi.org/10.1111/1468-0262.00152
- Hansen, Test for Superior Predictive Ability: https://doi.org/10.1198/073500105000000063

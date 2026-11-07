---
name: overfitting-defense
description: Detect and limit backtest overfitting and selection bias; use when optimizing many variants, comparing strategies, evaluating holdouts or quoting Sharpe statistics.
---

# Overfitting Defense

## Objective
Protect statistical evidence from adaptive reuse and multiple testing.

## Procedure
1. Maintain immutable, timestamped TRAIN, VALIDATION, TEST assignments and an experiment registry with all tried strategies, parameters and filters. Decide the selection protocol in advance.
2. All fitting/feature discovery/hyperparameter tuning uses TRAIN only; use nested time-series CV or rolling training experiments as needed. VALIDATION supports limited predeclared model selection, not endless refinement; TEST is accessed once after strategy/specification freeze.
3. Purge overlapping-label observations at split boundaries and apply embargo where necessary; size depends on label horizon and information overlap, not a fixed arbitrary percentage.
4. Explicitly account for multiple comparisons. Where valid, estimate Deflated Sharpe Ratio (DSR) using trial multiplicity and nonnormality; CSCV/PBO can diagnose selection instability, but must not substitute for chronological forward testing. Disclose assumptions and unreliable small samples.
5. Use block/bootstrap or regime-aware uncertainty estimates rather than iid resampling of every bar. Evaluate performance deterioration across unseen folds and sensitivity to costs and parameters.
6. If a researcher examines TEST and then changes a rule, mark the test contaminated. Create a genuinely new forward holdout (future data) instead of relabeling old data.
7. Log negative results. Require plausible baseline comparisons. Report confidence ranges, trial count, selection process and data exposure.

## Decision
No reliable evidence -> REJECT or RESEARCH-ONLY. Never claim a discovered profitable strategy has been proven profitable.

## References
Bailey et al., Probability of Backtest Overfitting: https://escholarship.org/uc/item/4w1110bb
Bailey & Lopez de Prado, Deflated Sharpe Ratio: https://doi.org/10.3905/jpm.2014.40.5.094

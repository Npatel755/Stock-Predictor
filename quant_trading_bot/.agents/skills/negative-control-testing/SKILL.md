---
name: negative-control-testing
description: Challenge apparent trading edges with fair placebo baselines, randomized controls and sensitivity diagnostics without misusing holdout data.
---
# Negative controls and falsification tests

Use whenever a candidate exhibits attractive in-sample performance, especially after hundreds or thousands of trials. This complements `overfitting-defense`: it tests whether the alleged edge survives attempts to falsify the research explanation.

## Baselines and falsification
- Compare to no-trade, simple session-specific buy-and-hold/always-in-market (when appropriate), naive trend/reversal models and random-entry baselines matched on turnover and holding periods.
- Generate timestamp-randomized or block-randomized signal controls **only within training partitions** while preserving key constraints (session, exposure, signal count, volatility clustering where feasible).
- Shift signals deliberately in diagnostic runs to detect suspicious immediate fills or future information, but **never** claim shifted strategies are legitimate production candidates.
- Check dependence on single anomalous days, rare trades, one instrument, a vendor artifact, roll week or a particular cost assumption.
- Examine confidence intervals using chronology-aware blocks; clearly distinguish diagnostic p-values from pre-registered confirmatory statistics.

## Required protocol
1. State a concrete, falsifiable economic/market hypothesis before tests.
2. Define fair matched baselines and diagnostics, plus allowed training-only thresholds.
3. Run all falsification tests against the training sample; document variants attempted and multiplicity.
4. Report whether the candidate beats baseline net of comparable costs and exposures.
5. Freeze hypotheses and selection rules before limited validation; leave final test untouched.

## Interpretation rules
- Beating shuffled signals is *supporting evidence*, not proof that future returns will be positive.
- A strategy that cannot distinguish itself from appropriately matched null controls should be rejected or flagged as unproven.
- Never keep searching new controls until they appear to support the desired strategy.

## Outputs
A falsification matrix (hypothesis / control / purpose / result / decision), exact random seeds, reproducible code and honest negative findings.

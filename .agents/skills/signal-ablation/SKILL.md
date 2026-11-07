---
name: signal-ablation
description: Test whether indicators and filters in an algorithm contribute independent value, or merely increase curve-fitting risk.
---

# Signal Ablation and Feature Sanity

## Setup
Snapshot the baseline strategy and full experiment configuration. Restrict exploration to training data; validation/test must not be used to choose components.

## Experiments
1. Remove one feature, filter or decision rule at a time while holding all other settings fixed.
2. Test individual features, minimal pairs, and simple baselines; compare comparable sizing, exposure, turnover, and net-of-cost returns.
3. If ML-based, use fold-local feature transforms and training-only permutation tests; avoid fitting scalers on future periods.
4. Shuffle signals, delay entries, shift calendar timestamps, replace parameters with neighbors and examine negative controls.
5. Use confidence intervals or block-based resampling where dependence exists; do not treat repeated correlated trades as independent observations.
6. Check interactions: a feature may improve only a particular regime or exit; do not promote that claim without sufficient samples.
7. Prefer the **simplest** candidate that meets predeclared training/validation requirements; record all ablation trials and rejected features.

## Output
Ablation matrix, uncertainty, marginal net benefit, trade overlap, complexity score, and recommendation to retain/remove/defer.

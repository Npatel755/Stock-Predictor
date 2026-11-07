# Additional10,000 training configurations

The fixed next seed extends the original parameter domains without responding to protected-period results. No prior configuration is repeated:20,000 distinct active configurations are now recorded across both completed batches.

**10,000 completed configurations; 10,000 unique IDs verified.** 6 met the declared training qualification checks. Validation and final testing are **BLOCKED** because the available later periods have already been observed.

This is a training research result, not a claim of profitable unseen performance. No market-price data are read by this report publisher. The search reports that validation and test prices were not opened. Existing split boundaries remain unchanged: training ends before 2024; validation is 2024–2025; testing is 2026. Repartitioning or forgetting earlier results would not restore an untouched holdout.

## Protocol and reproducibility

Seed: `20261107`. Fixed search target: **10,000**. Configuration IDs were reconciled between the ranked CSV and configuration manifest. These checks establish record identity and completeness; equivalence deduplication depends on the search generator's declared canonicalization.

Split/selection policy:

`"Existing physical training before2024, validation2024\u20132025, testing2026 unchanged. Only TRAIN may be loaded."`

Source identities:

```json
{
  "continue_mass_research.py": "95d3d14a499a1180dbc73b002b0e0efca60027dfce44230dfe94064347a04601",
  "mass_configurations.py": "b0e0f8909c1df7db775f91899f45fdb56b4587362f59ac67d83653a6ef88cf91",
  "mass_continuation_configurations.py": "7acbe721813f9f7be7d60a76d4f17699334298ae5d62d32da237ef216e2b4c78",
  "mass_execution.py": "a31ef27f3df1e02fc59d4cb86ed9cbb512eec90ad5d361dcd202a5a6da9cd6af",
  "mass_features.py": "a096e4d3e667d7eb042d411605e7969fb0675d1d034b261824a519b4e1c8aad5",
  "mass_metrics.py": "11523f178f317d6fdb551f5171687f3b0d13c8246e3b6dec0dc20d08d52f18ff",
  "mass_research.py": "35703d03706afd9c8767d2edf433d8987bc808aa9d64b29639a203180545f442",
  "mass_verify.py": "f00df91c30890e7f9621d1a35998c175dda3d11ea4bef5c22d38b8b2aa87b666"
}
```

[Ranked results for all configurations](../runs/mass_training_continuation_v1/ranked.csv) · [Reproducible configuration manifest](../runs/mass_training_continuation_v1/configurations.jsonl)

## Training shortlist

All values below are training measurements under the recorded contract specifications, costs and account assumptions. Mini-contract results must not be relabeled as micro-contract history. Training drawdown below $2,000 does not guarantee a future loss ceiling. Net sums four disjoint fold accounts with capital reset. Drawdowns are worst separate folds. Profit factor pools trade P&L; Sharpe is the mean of fold daily Sharpes. Duration is minutes.

| Configuration | Instrument | Family | Net | Closing DD | Cash DD | Intrabar DD | Profit factor | Sharpe | Win rate | Expectancy | Trades | Avg duration | Positive folds | Training qualified |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| mass_aade3d08eb001ccc3d3e | MNQ | momentum | $6,236.50 | $1,219.00 | $1,133.50 | $1,250.25 | 1.25 | 1.22 | 48.2% | $7.53 | 828 | 30.72 | 4/4 | True |
| mass_2eafe88e993469aedb12 | MNQ | hybrid | $5,989.00 | $841.50 | $780.50 | $841.50 | 1.36 | 1.42 | 52.4% | $12.45 | 481 | 55.70 | 4/4 | True |
| mass_4077260e9698c6a220bf | MNQ | regime | $2,955.00 | $548.00 | $548.50 | $562.75 | 1.31 | 1.06 | 52.7% | $7.64 | 387 | 24.22 | 4/4 | True |
| mass_8c8f64ec70a765ae6eb7 | MNQ | trend | $5,989.00 | $962.00 | $916.50 | $979.75 | 1.24 | 1.28 | 54.8% | $7.70 | 778 | 29.31 | 4/4 | True |
| mass_44b8a3fc9ecea9420d38 | MNQ | trend | $4,270.00 | $1,079.00 | $1,036.50 | $1,112.75 | 1.17 | 0.81 | 45.8% | $6.04 | 707 | 32.89 | 4/4 | True |
| mass_d744bdc7bca1b354a2ea | MNQ | hybrid | $4,668.50 | $1,057.50 | $1,044.00 | $1,081.25 | 1.15 | 0.95 | 52.8% | $5.28 | 885 | 30.92 | 4/4 | True |
| mass_2eeaa376331d39ed0cec | MNQ | trend | $1,747.50 | $427.50 | $389.50 | $445.75 | 1.53 | 1.41 | 54.1% | $6.52 | 268 | 43.54 | 4/4 | False |
| mass_a8b93c0634fd8efc35e4 | MNQ | opening_range | $2,893.50 | $484.50 | $418.00 | $495.25 | 1.75 | 1.69 | 59.6% | $12.86 | 225 | 75.33 | 4/4 | False |
| mass_0046339b34ebad2db92f | MNQ | momentum | $1,463.50 | $356.50 | $300.50 | $365.75 | 1.62 | 1.38 | 51.7% | $7.14 | 205 | 41.34 | 4/4 | False |
| mass_64d031af0fb83b2013fd | MNQ | opening_range | $2,277.00 | $378.00 | $319.00 | $393.38 | 1.79 | 1.48 | 58.3% | $12.65 | 180 | 72.50 | 4/4 | False |

## Event-driven verification

Every search configuration uses the sequential JIT event simulator. Frozen finalists reproduce their base run and receive a2× cost stress. Independent ledger arithmetic covers every finalist trade; up to25 evenly spaced trades per fold are also replayed through the separate shared simulator. These isolated trade checks verify fills and economics. Account-path equivalence is not claimed: the older simulator omits pre-exit adverse bounds and exit-cost reserves. No strategy is promoted automatically.

| Candidate | Base reproduced | Ledger trades checked | Shared trade replays | 2× cost net | 2× closing DD | 2× intrabar DD | 2× training qualified |
|---|---|---:|---:|---:|---:|---:|---|
| mass_aade3d08eb001ccc3d3e | True | 828 | 100 | $4,499.00 | $1,542.50 | $1,575.00 | False |
| mass_2eafe88e993469aedb12 | True | 481 | 100 | $5,305.00 | $983.50 | $1,008.50 | True |
| mass_4077260e9698c6a220bf | True | 387 | 100 | $2,333.50 | $510.50 | $527.50 | True |
| mass_8c8f64ec70a765ae6eb7 | True | 778 | 100 | $4,170.00 | $1,019.50 | $1,058.00 | True |
| mass_44b8a3fc9ecea9420d38 | True | 707 | 100 | $1,599.50 | $1,221.50 | $1,227.75 | False |
| mass_d744bdc7bca1b354a2ea | True | 885 | 100 | $2,676.50 | $1,429.00 | $1,467.50 | False |
| mass_2eeaa376331d39ed0cec | True | 268 | 84 | $860.00 | $490.00 | $509.50 | False |
| mass_a8b93c0634fd8efc35e4 | True | 225 | 84 | $2,138.50 | $542.00 | $552.50 | False |
| mass_0046339b34ebad2db92f | True | 205 | 83 | $900.00 | $378.50 | $389.00 | False |
| mass_64d031af0fb83b2013fd | True | 180 | 82 | $1,462.00 | $418.50 | $435.25 | False |

## PASS/FAIL and missing confirmation

- Full training search: **PASS** — 10,000 completed records reconciled to unique configuration IDs.
- Declared training qualification: **PASS for 6 configurations**.
- Profitability on genuinely unseen validation: **NOT ESTABLISHED — BLOCKED**. Do not claim a pass from earlier reused validation results.
- Drawdown below $2,000 on genuinely unseen validation: **NOT ESTABLISHED — BLOCKED**.
- Final untouched test: **NOT RUN — BLOCKED**. The 2026 period has already been consumed.
- Exact funded-account compliance: **NOT ESTABLISHED** unless separately verified against the actual account agreement, platform permission, charges, trailing-loss mechanics and consistency rules. Configurable assumptions do not establish compliance.
- Live deployment: **FAIL / not eligible**. No live execution is authorized.

The 50% consistency requirement and every other funded-account rule must remain explicit in the account configuration. No unverified account-specific term is assumed here. A strategy must pass the complete execution, cost, account and independent-observation checks before any success claim.

## Artifacts and next legitimate evaluation

[Strategy rules, fold detail, exported curves and trade ledgers](../runs/mass_training_continuation_v1/RESEARCH_DETAILS.md). [Frozen protocol](../runs/mass_training_continuation_v1/protocol.json) · [Finalist verification](../runs/mass_training_continuation_v1/finalist_training_checks.json).

Equity/drawdown and trade-by-trade artifacts, when generated by event-driven verification, remain under the run directory. The publisher does not fabricate curves or trades for a vectorized screen. Review the execution-verification records for exact available filenames and unresolved checks.

[Validation status](MASS_CONTINUATION_VALIDATION_REPORT.md) · [Final test status](MASS_CONTINUATION_TEST_REPORT.md) · [Dashboard](http://127.0.0.1:8511)

A new evaluation requires genuinely untouched forward observations and a frozen shortlist/ranking/evaluation protocol. Do not tune candidates from validation/test outcomes or repeatedly inspect those periods during continued training research.

## Doubled-cost training survivors

3 of the6 base-qualified new candidates also met all training gates at2x costs. This is a diagnostic subset preserving the frozen training ranking; no protected-data selection was performed. See [candidate configurations and metrics](../runs/mass_training_continuation_v1/COST_ROBUST_TRAINING_CANDIDATES.md).

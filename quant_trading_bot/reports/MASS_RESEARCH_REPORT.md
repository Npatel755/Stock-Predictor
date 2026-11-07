# 10,000-configuration training research

**10,000 completed configurations; 10,000 unique IDs verified.** 4 met the declared training qualification checks. Validation and final testing are **BLOCKED** because the available later periods have already been observed.

This is a training research result, not a claim of profitable unseen performance. No market-price data are read by this report publisher. The search reports that validation and test prices were not opened. Existing split boundaries remain unchanged: training ends before 2024; validation is 2024–2025; testing is 2026. Repartitioning or forgetting earlier results would not restore an untouched holdout.

## Protocol and reproducibility

Seed: `20261106`. Fixed search target: **10,000**. Configuration IDs were reconciled between the ranked CSV and configuration manifest. These checks establish record identity and completeness; equivalence deduplication depends on the search generator's declared canonicalization.

Split/selection policy:

`"Existing physical training before2024, validation2024\u20132025, testing2026 unchanged. Only TRAIN may be loaded."`

Source identities:

```json
{
  "mass_configurations.py": "b0e0f8909c1df7db775f91899f45fdb56b4587362f59ac67d83653a6ef88cf91",
  "mass_execution.py": "a31ef27f3df1e02fc59d4cb86ed9cbb512eec90ad5d361dcd202a5a6da9cd6af",
  "mass_features.py": "a096e4d3e667d7eb042d411605e7969fb0675d1d034b261824a519b4e1c8aad5",
  "mass_metrics.py": "11523f178f317d6fdb551f5171687f3b0d13c8246e3b6dec0dc20d08d52f18ff",
  "mass_research.py": "35703d03706afd9c8767d2edf433d8987bc808aa9d64b29639a203180545f442",
  "mass_verify.py": "f00df91c30890e7f9621d1a35998c175dda3d11ea4bef5c22d38b8b2aa87b666"
}
```

[Ranked results for all configurations](../runs/mass_training_v2/ranked.csv) · [Reproducible configuration manifest](../runs/mass_training_v2/configurations.jsonl)

## Training shortlist

All values below are training measurements under the recorded contract specifications, costs and account assumptions. Mini-contract results must not be relabeled as micro-contract history. Training drawdown below $2,000 does not guarantee a future loss ceiling. Net sums four disjoint fold accounts with capital reset. Drawdowns are worst separate folds. Profit factor pools trade P&L; Sharpe is the mean of fold daily Sharpes. Duration is minutes.

| Configuration | Instrument | Family | Net | Closing DD | Cash DD | Intrabar DD | Profit factor | Sharpe | Win rate | Expectancy | Trades | Avg duration | Positive folds | Training qualified |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| mass_85721bb33e324b248878 | MNQ | breakout | $8,421.00 | $926.50 | $908.50 | $960.25 | 1.53 | 1.66 | 49.4% | $23.79 | 354 | 49.87 | 4/4 | True |
| mass_853576a710b834b0ad13 | MNQ | trend | $6,330.50 | $1,055.50 | $853.00 | $1,067.50 | 1.37 | 1.57 | 57.5% | $10.31 | 614 | 77.32 | 4/4 | True |
| mass_a2ac4a632df00701ac49 | MNQ | opening_range | $5,434.50 | $1,123.00 | $1,055.50 | $1,145.00 | 1.36 | 1.41 | 56.1% | $9.58 | 567 | 74.21 | 4/4 | True |
| mass_9c4239762fe64389ef65 | MNQ | trend | $3,431.50 | $1,168.50 | $1,166.00 | $1,182.50 | 1.13 | 0.64 | 46.6% | $4.98 | 689 | 31.76 | 4/4 | True |
| mass_f00118a9502d5bf8e4ca | MNQ | hybrid | $2,735.50 | $317.50 | $295.50 | $330.75 | 1.88 | 1.59 | 58.7% | $12.55 | 218 | 67.29 | 4/4 | False |
| mass_db3be4b16e555f40dd81 | MNQ | opening_range | $2,445.00 | $377.50 | $343.00 | $392.88 | 1.56 | 1.60 | 50.5% | $8.23 | 297 | 48.59 | 4/4 | False |
| mass_bef317dfc03e0aa8a0c6 | MNQ | opening_range | $2,910.50 | $419.00 | $325.00 | $434.50 | 1.76 | 1.67 | 59.5% | $13.11 | 222 | 75.47 | 4/4 | False |
| mass_efc9160cb99fab8e80ea | MNQ | momentum | $1,881.50 | $409.50 | $347.50 | $426.25 | 1.58 | 1.31 | 58.8% | $9.70 | 194 | 70.90 | 4/4 | False |
| mass_80a9938f1c35a22003d7 | MNQ | hybrid | $1,521.00 | $356.50 | $300.50 | $365.75 | 1.67 | 1.43 | 52.7% | $7.57 | 201 | 41.94 | 4/4 | False |
| mass_f6a2bab65c0358d09639 | MNQ | trend | $3,531.00 | $671.00 | $554.00 | $678.50 | 1.83 | 1.37 | 52.0% | $27.80 | 127 | 70.04 | 4/4 | False |

## Event-driven verification

Every search configuration uses the sequential JIT event simulator. Frozen finalists reproduce their base run and receive a2× cost stress. Independent ledger arithmetic covers every finalist trade; up to25 evenly spaced trades per fold are also replayed through the separate shared simulator. These isolated trade checks verify fills and economics. Account-path equivalence is not claimed: the older simulator omits pre-exit adverse bounds and exit-cost reserves. No strategy is promoted automatically.

| Candidate | Base reproduced | Ledger trades checked | Shared trade replays | 2× cost net | 2× closing DD | 2× intrabar DD | 2× training qualified |
|---|---|---:|---:|---:|---:|---:|---|
| mass_85721bb33e324b248878 | True | 354 | 100 | $7,370.00 | $956.00 | $1,003.50 | True |
| mass_853576a710b834b0ad13 | True | 614 | 100 | $4,053.50 | $1,256.00 | $1,272.50 | False |
| mass_a2ac4a632df00701ac49 | True | 567 | 100 | $3,373.00 | $1,265.50 | $1,287.00 | False |
| mass_9c4239762fe64389ef65 | True | 689 | 100 | $1,525.00 | $1,237.50 | $1,293.50 | False |
| mass_f00118a9502d5bf8e4ca | True | 218 | 83 | $2,116.50 | $371.50 | $386.50 | False |
| mass_db3be4b16e555f40dd81 | True | 297 | 84 | $1,314.50 | $400.50 | $416.75 | False |
| mass_bef317dfc03e0aa8a0c6 | True | 222 | 84 | $1,832.00 | $529.00 | $543.00 | False |
| mass_efc9160cb99fab8e80ea | True | 194 | 83 | $1,188.00 | $454.50 | $490.00 | False |
| mass_80a9938f1c35a22003d7 | True | 201 | 83 | $963.50 | $378.50 | $389.00 | False |
| mass_f6a2bab65c0358d09639 | True | 127 | 92 | $3,135.00 | $550.50 | $600.50 | False |

## PASS/FAIL and missing confirmation

- Full training search: **PASS** — 10,000 completed records reconciled to unique configuration IDs.
- Declared training qualification: **PASS for 4 configurations**.
- Profitability on genuinely unseen validation: **NOT ESTABLISHED — BLOCKED**. Do not claim a pass from earlier reused validation results.
- Drawdown below $2,000 on genuinely unseen validation: **NOT ESTABLISHED — BLOCKED**.
- Final untouched test: **NOT RUN — BLOCKED**. The 2026 period has already been consumed.
- Exact funded-account compliance: **NOT ESTABLISHED** unless separately verified against the actual account agreement, platform permission, charges, trailing-loss mechanics and consistency rules. Configurable assumptions do not establish compliance.
- Live deployment: **FAIL / not eligible**. No live execution is authorized.

The 50% consistency requirement and every other funded-account rule must remain explicit in the account configuration. No unverified account-specific term is assumed here. A strategy must pass the complete execution, cost, account and independent-observation checks before any success claim.

## Artifacts and next legitimate evaluation

[Strategy rules, fold detail, exported curves and trade ledgers](../runs/mass_training_v2/RESEARCH_DETAILS.md). [Frozen protocol](../runs/mass_training_v2/protocol.json) · [Finalist verification](../runs/mass_training_v2/finalist_training_checks.json).

Equity/drawdown and trade-by-trade artifacts, when generated by event-driven verification, remain under the run directory. The publisher does not fabricate curves or trades for a vectorized screen. Review the execution-verification records for exact available filenames and unresolved checks.

[Validation status](MASS_VALIDATION_REPORT.md) · [Final test status](MASS_TEST_REPORT.md) · [Dashboard](http://127.0.0.1:8511)

A new evaluation requires genuinely untouched forward observations and a frozen shortlist/ranking/evaluation protocol. Do not tune candidates from validation/test outcomes or repeatedly inspect those periods during continued training research.

# Positive Training Cohort: Validation Evaluation (2024–2025)

Evaluated all **3,243** positive-P&L, sub-$2,000 drawdown training configurations on the **2024–2025 Validation split** without tuning.

- Total completed: **3,243**
- Positive Validation Net P&L & Drawdown < $2,000: **1,107** strategies
- Strategies Passing BOTH Validation AND Test Checks: **423** strategies

## Top 15 Validation Strategies (Net P&L under $2,000 DD)

| # | Candidate ID | Instrument | Family | Val Net | Val Intrabar DD | Val Trades | Test Net (Reused) | Test Intrabar DD |
|---|---|---|---|---:|---:|---:|---:|---:|
| 1 | `mass_e0aac7b0fb35c788eae9` | MNQ | breakout | $5,091.00 | $1,599.75 | 392 | $2,164.50 | $1,358.38 |
| 2 | `mass_31d1122b68eaa5cb0726` | MNQ | breakout | $4,965.00 | $1,367.88 | 174 | $1,395.00 | $288.88 |
| 3 | `mass_4a0b95329be1d0438243` | MNQ | breakout | $4,434.00 | $1,290.00 | 148 | $3,645.50 | $1,124.50 |
| 4 | `mass_c66ade7109abf047e3e4` | MNQ | breakout | $4,268.00 | $1,084.25 | 105 | $1,917.00 | $288.75 |
| 5 | `mass_3f42bcddc9a30d686002` | MNQ | breakout | $4,119.50 | $1,774.38 | 437 | $645.00 | $1,801.00 |
| 6 | `mass_9590d898d3d922b9d898` | MNQ | breakout | $3,963.50 | $941.88 | 170 | $246.00 | $278.38 |
| 7 | `mass_85721bb33e324b248878` | MNQ | breakout | $3,685.00 | $779.38 | 169 | $-190.00 | $998.88 |
| 8 | `mass_87a9306831fc6fb89747` | MNQ | breakout | $3,661.00 | $1,172.25 | 220 | $2,837.00 | $619.75 |
| 9 | `mass_17fd59cc76253abac1c4` | MNQ | breakout | $3,499.50 | $1,225.25 | 151 | $695.00 | $257.75 |
| 10 | `mass_aa0559d329f520d66d8e` | MNQ | opening_range | $3,282.00 | $1,397.38 | 390 | $914.50 | $1,063.38 |
| 11 | `mass_b0a5d764ee548a9c6971` | MNQ | momentum | $3,091.50 | $915.00 | 94 | $1,756.00 | $588.50 |
| 12 | `mass_ee8bcb3305737f1e034b` | MNQ | momentum | $2,921.50 | $1,040.25 | 416 | $936.00 | $1,262.25 |
| 13 | `mass_730baa9e2bf0a07bcce0` | MNQ | trend | $2,854.00 | $969.75 | 282 | $-729.00 | $1,181.50 |
| 14 | `mass_009d843e631eea1b01f3` | MNQ | breakout | $2,843.50 | $1,303.75 | 313 | $2,051.50 | $1,326.75 |
| 15 | `mass_f1fe71c0eee6b7a9a4ad` | MNQ | opening_range | $2,840.50 | $1,344.38 | 472 | $784.50 | $975.88 |

## Top 15 All-Rounders: Robust Across Training, Validation AND Test

Strategies with positive net profit and drawdowns < $2,000 across all 3 independent time splits without tuning:

| # | Candidate ID | Instrument | Family | Training Net | Val Net | Test Net | Combined Val+Test | Max Intrabar DD (Val) |
|---|---|---|---|---:|---:|---:|---:|---:|
| 1 | `mass_4a0b95329be1d0438243` | MNQ | breakout | $6,893.50 | $4,434.00 | $3,645.50 | **$8,079.50** | $1,290.00 |
| 2 | `mass_e0aac7b0fb35c788eae9` | MNQ | breakout | $5,926.50 | $5,091.00 | $2,164.50 | **$7,255.50** | $1,599.75 |
| 3 | `mass_87a9306831fc6fb89747` | MNQ | breakout | $3,508.50 | $3,661.00 | $2,837.00 | **$6,498.00** | $1,172.25 |
| 4 | `mass_31d1122b68eaa5cb0726` | MNQ | breakout | $4,511.50 | $4,965.00 | $1,395.00 | **$6,360.00** | $1,367.88 |
| 5 | `mass_c66ade7109abf047e3e4` | MNQ | breakout | $2,577.00 | $4,268.00 | $1,917.00 | **$6,185.00** | $1,084.25 |
| 6 | `mass_009d843e631eea1b01f3` | MNQ | breakout | $4,077.50 | $2,843.50 | $2,051.50 | **$4,895.00** | $1,303.75 |
| 7 | `mass_b0a5d764ee548a9c6971` | MNQ | momentum | $8,267.00 | $3,091.50 | $1,756.00 | **$4,847.50** | $915.00 |
| 8 | `mass_3f42bcddc9a30d686002` | MNQ | breakout | $2,118.00 | $4,119.50 | $645.00 | **$4,764.50** | $1,774.38 |
| 9 | `mass_d6739397c054eaa2dbbd` | MNQ | breakout | $4,271.00 | $2,510.50 | $2,236.50 | **$4,747.00** | $1,749.38 |
| 10 | `mass_ebf1aa6f14ebb8abd177` | MNQ | breakout | $5,062.50 | $1,647.00 | $2,883.00 | **$4,530.00** | $945.25 |
| 11 | `mass_1f301f261ad3a17d3a12` | MNQ | breakout | $1,663.50 | $1,774.50 | $2,531.50 | **$4,306.00** | $894.25 |
| 12 | `mass_9590d898d3d922b9d898` | MNQ | breakout | $2,093.50 | $3,963.50 | $246.00 | **$4,209.50** | $941.88 |
| 13 | `mass_aa0559d329f520d66d8e` | MNQ | opening_range | $7,769.50 | $3,282.00 | $914.50 | **$4,196.50** | $1,397.38 |
| 14 | `mass_17fd59cc76253abac1c4` | MNQ | breakout | $3,113.00 | $3,499.50 | $695.00 | **$4,194.50** | $1,225.25 |
| 15 | `mass_ee8bcb3305737f1e034b` | MNQ | momentum | $404.00 | $2,921.50 | $936.00 | **$3,857.50** | $1,040.25 |

## Artifacts and Data Separation
- [Full Validation Results CSV](validation_results.csv)
- [Frozen Cohort Manifest](frozen_cohort.json)

All configurations were evaluated once on 2024-2025 validation data with base costs and no parameter changes.
Test data (2026) was not opened or rerun by this evaluation; test numbers shown are previously saved diagnostics.
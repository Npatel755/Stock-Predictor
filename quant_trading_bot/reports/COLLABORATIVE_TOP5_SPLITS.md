# Frozen top five: validation and test without tuning

**All five displayed training candidates were frozen before new price access. Each was evaluated once on validation and once on test, at identical base costs. No parameter, feature, filter, sizing, stop, cost or candidate selection changed between stages.**

Validation: existing2024–2025 physical MNQ partition. Test: existing2026 partition through its saved coverage end. Each candidate/split uses one continuous$50,000 account, split-local feature warmup and the original96-bar entry embargo/16-bar terminal entry purge. Training totals shown below sum four separate2020–2023 annual accounts; those training drawdowns are worst-year figures. Validation/test drawdown covers the entire respective continuous split account.

**These periods have been observed in earlier work. This is an explicitly requested reused-period evaluation, not independent unseen confirmation.**

| Training rank / ID | Family | Training net | Validation net | Validation intrabar DD | Val trades | Val permanent lock | Test net | Test intrabar DD | Test trades | Both profit/DD checks |
|---|---|---:|---:|---:|---:|---|---:|---:|---:|---|
| 1: `mass_8190d72d308b603c1725` | trend | $11,365.50 | $-1,703.00 | $1,834.00 | 28 | maximum drawdown | $489.50 | $1,150.88 | 66 | FAIL |
| 2: `mass_74a481aa30c484a442b6` | breakout | $11,219.50 | $1,390.50 | $1,534.00 | 179 | none | $812.00 | $879.50 | 46 | PASS |
| 3: `mass_b839a1ec768d3babc0b7` | trend | $10,938.00 | $-1,500.00 | $1,814.00 | 29 | maximum drawdown | $290.00 | $1,005.50 | 70 | FAIL |
| 4: `mass_6dfbc230bb4d7f9f0e83` | trend | $10,913.50 | $-1,735.50 | $1,841.50 | 31 | maximum drawdown | $28.50 | $1,291.38 | 60 | FAIL |
| 5: `mass_3f98bb0221b65643d358` | breakout | $10,765.00 | $634.00 | $1,823.50 | 200 | maximum drawdown | $-2.00 | $1,548.00 | 63 | FAIL |

## Outcome

Profitability plus all three drawdown measures strictly below$2,000: **2/5 on validation, 4/5 on test, 1/5 on both**. Additional scenario checks on both splits (at least30 trades, no permanent risk lock or funded-floor breach): **1/5**. Including the50% evaluation-account consistency diagnostic on both splits: **0/5**.

All reported test outcomes were produced after every validation evaluation finished, on the same frozen versions, irrespective of validation gains/losses. A positive test does not erase a validation loss. The original$1,800 internal drawdown stop can lock an account before the outer$2,000 reporting threshold; a positive-net/sub-$2,000 case with a permanent lock still fails the additional scenario checks. Flat marks after a lock do not represent continued trading.

## Complete split metrics

| Rank | Split | Net | Cash DD | Closing DD | Intrabar DD | Trades | 50% consistency | Scenario without50% | Evaluation-account scenario | Last trade exit UTC |
|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| 1 | validation | $-1,703.00 | $1,832.00 | $1,834.00 | $1,834.00 | 28 | undefined | False | False | 2024-04-09 15:15:00+00:00 |
| 1 | test | $489.50 | $999.00 | $1,098.00 | $1,150.88 | 66 | 99.90% | True | False | 2026-10-16 14:30:00+00:00 |
| 2 | validation | $1,390.50 | $1,493.50 | $1,493.00 | $1,534.00 | 179 | 47.75% | True | True | 2025-12-24 17:00:00+00:00 |
| 2 | test | $812.00 | $807.50 | $807.00 | $879.50 | 46 | 53.82% | True | False | 2026-10-22 16:00:00+00:00 |
| 3 | validation | $-1,500.00 | $1,812.00 | $1,814.00 | $1,814.00 | 29 | undefined | False | False | 2024-04-09 15:00:00+00:00 |
| 3 | test | $290.00 | $946.50 | $952.50 | $1,005.50 | 70 | 168.62% | True | False | 2026-10-16 14:30:00+00:00 |
| 4 | validation | $-1,735.50 | $1,781.50 | $1,841.50 | $1,841.50 | 31 | undefined | False | False | 2024-05-08 15:00:00+00:00 |
| 4 | test | $28.50 | $1,065.00 | $1,238.50 | $1,291.38 | 60 | 1715.79% | True | False | 2026-10-16 14:30:00+00:00 |
| 5 | validation | $634.00 | $1,823.50 | $1,823.50 | $1,823.50 | 200 | 110.25% | False | False | 2025-11-06 15:15:00+00:00 |
| 5 | test | $-2.00 | $1,476.00 | $1,475.50 | $1,548.00 | 63 | undefined | False | False | 2026-10-23 16:00:00+00:00 |

The user-provided50% consistency rule applies only to the account evaluation phase. Chronological validation/test partitions are not account phases, so both account-phase interpretations are reported without modifying execution. Actual account contract terms, all-in fees, holidays and operational eligibility remain unverified.

## Frozen rules and audit

Original completed15-minute raw-contract bars, causal indicators, next-open fills, adverse stop gaps, conservative stop-first ambiguity, strict target trade-through, volume/contract safeguards and fees/spread/slippage remained unchanged. Each of the10 executions has an exclusive per-candidate/split reservation, trade ledger, equity/cash/intrabar curve, execution verification and result hash. Test reservations record all five completed validation-result hashes, verified again after testing. Frozen code/configuration hashes and prior training artifacts reconcile. No holdout result guided changes or further candidates.

Cohort hash: `4bc3667c6c411528e31f1bb7024fb6fcd8568c701c093e69fbcdd5f9833e5084`. Three reservation/order/tamper guard tests passed before any evaluation. All10 ledgers and curves reconcile to their reported net and drawdowns. This publication only reads saved artifacts; it does not replay strategies.

Test coverage: {'rows': 301755, 'start': '2026-01-01 23:00:00+00:00', 'end': '2026-11-05 23:59:00+00:00'}. Validation coverage: {'rows': 707652, 'start': '2024-01-01 23:00:00+00:00', 'end': '2025-12-31 21:59:00+00:00'}.

Results retain the original training order. They do not authorize a new selection/tuning cycle on these observed periods. Fresh forward observations are required for independent confirmation.

## Frozen configurations

```json
[
  {
    "display_rank": 1,
    "candidate_id": "mass_8190d72d308b603c1725",
    "parameters": {
      "config_id": "mass_8190d72d308b603c1725",
      "experiment_order": 50560,
      "family": "trend",
      "hold_bars": 12,
      "instrument": "MNQ",
      "lookback": 8,
      "max_contracts": 2,
      "session_end": 720,
      "session_start": 600,
      "stop_atr": 1.0,
      "target_r": 4.0,
      "threshold": 0.75,
      "trailing_atr": 1.0
    }
  },
  {
    "display_rank": 2,
    "candidate_id": "mass_74a481aa30c484a442b6",
    "parameters": {
      "config_id": "mass_74a481aa30c484a442b6",
      "experiment_order": 123840,
      "family": "breakout",
      "hold_bars": 16,
      "instrument": "MNQ",
      "lookback": 24,
      "max_contracts": 3,
      "session_end": 720,
      "session_start": 600,
      "stop_atr": 1.0,
      "target_r": 3.0,
      "threshold": 0.75,
      "trailing_atr": 2.0
    }
  },
  {
    "display_rank": 3,
    "candidate_id": "mass_b839a1ec768d3babc0b7",
    "parameters": {
      "config_id": "mass_b839a1ec768d3babc0b7",
      "experiment_order": 30432,
      "family": "trend",
      "hold_bars": 4,
      "instrument": "MNQ",
      "lookback": 8,
      "max_contracts": 3,
      "session_end": 720,
      "session_start": 600,
      "stop_atr": 1.0,
      "target_r": 4.0,
      "threshold": 0.75,
      "trailing_atr": 1.0
    }
  },
  {
    "display_rank": 4,
    "candidate_id": "mass_6dfbc230bb4d7f9f0e83",
    "parameters": {
      "config_id": "mass_6dfbc230bb4d7f9f0e83",
      "experiment_order": 190300,
      "family": "trend",
      "hold_bars": 12,
      "instrument": "MNQ",
      "lookback": 8,
      "max_contracts": 2,
      "session_end": 720,
      "session_start": 600,
      "stop_atr": 1.0,
      "target_r": 4.0,
      "threshold": 0.75,
      "trailing_atr": 0.0
    }
  },
  {
    "display_rank": 5,
    "candidate_id": "mass_3f98bb0221b65643d358",
    "parameters": {
      "config_id": "mass_3f98bb0221b65643d358",
      "experiment_order": 63652,
      "family": "breakout",
      "hold_bars": 12,
      "instrument": "MNQ",
      "lookback": 8,
      "max_contracts": 3,
      "session_end": 720,
      "session_start": 600,
      "stop_atr": 1.0,
      "target_r": 3.0,
      "threshold": 0.75,
      "trailing_atr": 0.0
    }
  }
]
```

Artifacts: `../runs/collaborative_top5_splits_v1/frozen_cohort.json`, `split_metrics.csv`, `all_trades.csv`, per-candidate result JSON/curve/trade Parquet, `top5_split_curves.png`, `top5_split_curves.svg`. Machine summary: `COLLABORATIVE_TOP5_SPLITS.json`. Verification: `COLLABORATIVE_TOP5_SPLITS_verification.json`.

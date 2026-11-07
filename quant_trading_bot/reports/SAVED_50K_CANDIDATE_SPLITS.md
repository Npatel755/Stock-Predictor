# Saved MNQ trend strategy: unchanged validation then test

Candidate `mass_ca28dbb9316d2d9ced10` is permanently saved with its original training parameters and source hashes. It was the highest base-qualified net-profit candidate in the new50k training search. Its stored training net was$9,972.50 and worst annual intrabar DD$1,478. Training totals cover four separate yearly2020–2023 accounts.

**Both later stages used the exact frozen configuration: validation once, followed by test once, at base costs. No tuning, fitting, parameter changes, cost variants or alternate candidates were evaluated between outcomes.**

| Metric | Validation 2024–2025 | Test 2026 |
|---|---:|---:|
| Net P&L | $-1,699.50 | $1,784.00 |
| Realized-cash DD | $1,831.00 | $716.00 |
| Closing-equity DD | $1,833.00 | $715.50 |
| Intrabar DD bound | $1,833.00 | $768.50 |
| Trades | 40 | 77 |
| Profit + DD checks | False | True |
| Evaluation-phase scenario checks | False | True |
| Post-evaluation scenario checks | False | True |

## Outcome and safety locks

Validation **failed profitability and the no-permanent-lock check**. It stayed below$2,000 drawdown, but the original$1,800 internal safety margin triggered a maximum-drawdown lock. Later flat marks are not additional trading performance. Test was evaluated afterward on the identical configuration, as authorized; it returned a positive net and passed the recorded scenario checks. A positive test does not conceal the validation failure.

Validation: last recorded trade exit 2024-05-08 15:00:00+00:00; permanent lock: maximum drawdown. Source coverage: 2024-01-01 23:00:00+00:00 through 2025-12-31 21:59:00+00:00 UTC.
Test: last recorded trade exit 2026-10-16 14:30:00+00:00; permanent lock: none. Source coverage: 2026-01-01 23:00:00+00:00 through 2026-11-05 23:59:00+00:00 UTC.

## Account phase versus data split

Per the user instruction, the50% consistency rule is scoped to the **account evaluation phase only**. A chronological validation/test split is not itself an account phase. Both phase scenarios are therefore reported on each split, with the same executions. Consistency remains visible as a diagnostic, and the earlier doubled-cost training failure is preserved. This phase preference did not change entries, exits, stops, sizing or costs.

Validation consistency ratio: None (undefined when total net is nonpositive). Test consistency ratio: 26.68%.

The phase scope is user-provided, not an independently verified current account agreement. Exact funded-account eligibility, actual all-in fees and operational permission are not established.

## Data separation and reproducibility

Both periods had previously been observed during earlier research. These are explicitly requested reused-period diagnostics, not independent confirmation. Candidate selection and all parameters were frozen before either new evaluation. Separate exclusive reservations were written before price access; failures also consume the attempt. The validation result hash was recorded before test access and verified afterward. Prior training and test artifacts remain unchanged.

Original complete15-minute aggregation, causal indicators, next-open execution, prior-volume participation, original risk limits and first96/last16 entry suppression were preserved. Each split uses one continuous$50,000 account with warmup within that split only.

Frozen parameters:

```json
{
  "instrument": "MNQ",
  "family": "trend",
  "lookback": 8,
  "threshold": 0.75,
  "stop_atr": 1.0,
  "target_r": 3.0,
  "hold_bars": 2,
  "session_start": 600,
  "session_end": 720,
  "max_contracts": 3,
  "trailing_atr": 1.0,
  "config_id": "mass_ca28dbb9316d2d9ced10",
  "experiment_order": 5326
}
```

[Saved frozen strategy](/saved50k/frozen_candidate.json) · [Validation trade CSV](/saved50k/validation_trades.csv) · [Test trade CSV](/saved50k/test_trades.csv) · [Dashboard](http://127.0.0.1:8511/#saved-50k-results)

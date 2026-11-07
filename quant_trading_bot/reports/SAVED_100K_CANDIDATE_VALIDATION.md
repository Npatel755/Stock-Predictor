# Saved 100k MNQ trend candidate: unchanged validation evaluation

Candidate `mass_40950c7086a169459879` was selected from the 100k training search over 2020–2023 data. It was the highest base-qualified net-profit candidate ($13,920.50 training net, worst annual intrabar DD $1,593.00, surviving 2x costs at $6,677.50 net), topping the saved benchmark ($9,972.50).

**Validation evaluation used the exact frozen configuration on MNQ 2024–2025 at base costs. No tuning, fitting, parameter variants, or alternatives were tested. Test data (2026) was strictly NOT touched or opened.**

| Metric | Training (2020–2023) | Validation (2024–2025) |
|---|---:|---:|
| Net P&L | $13,920.50 | $-777.00 |
| Realized-cash DD | $1,479.00 | $1,845.50 |
| Closing-equity DD | $1,519.00 | $1,847.50 |
| Intrabar DD bound | $1,593.00 | $1,847.50 |
| Trades | 1303 | 136 |
| Profit + DD checks (<$2,000 DD) | PASS | FAIL |
| Evaluation-phase scenario checks | True | False |
| Post-evaluation scenario checks | True | False |

## Outcome and safety locks

Validation net P&L: **$-777.00**. Intrabar drawdown: **$1,847.50**. Trades: **136**.
Permanent lock: **maximum drawdown**.
Last recorded trade exit: 2024-05-24 17:15:00+00:00. Source coverage: 2024-01-01 23:00:00+00:00 through 2025-12-31 21:59:00+00:00 UTC.

## Account phase versus data split

Per the user instruction, the 50% consistency rule is scoped to the **account evaluation phase only**. A chronological validation/test split is not itself an account phase. Consistency remains visible as a diagnostic: undefined (nonpositive net)

## Data separation and test data protection

Per user instructions, **TEST DATA WAS NOT TOUCHED**. No test partition was resolved, no test reservation was made, and no 2026 test prices were opened. Validation was evaluated once on the frozen candidate without tuning.

Frozen parameters:

```json
{
  "instrument": "MNQ",
  "family": "trend",
  "lookback": 16,
  "threshold": 0.75,
  "stop_atr": 1.0,
  "target_r": 1.5,
  "hold_bars": 16,
  "session_start": 585,
  "session_end": 945,
  "max_contracts": 3,
  "trailing_atr": 0.0,
  "config_id": "mass_40950c7086a169459879",
  "experiment_order": 33075
}
```

[Saved frozen candidate](../runs/saved_100k_candidate_mass_40950c7086a169459879/frozen_candidate.json) · [Validation trade CSV](../runs/saved_100k_candidate_mass_40950c7086a169459879/validation_trades.csv) · [Dashboard](http://127.0.0.1:8511/#training-100k)

# Frozen MNQ breakout: one reused-test evaluation

Candidate `mass_85721bb33e324b248878` was selected as training rank1 before test access. Its code, parameters, costs and risk settings were frozen unchanged. Exactly one candidate and one base-cost test case were evaluated. No validation data were opened.

**Overall: FAIL on the recorded research scenario checks.**

| Metric | Test result |
|---|---:|
| Net profit after modeled costs | $-190.00 |
| Realized-cash drawdown | $953.50 |
| Closing-equity drawdown | $956.50 |
| Intrabar drawdown bound | $998.88 |
| Trades | 25 |
| Profit factor | 0.897 |
| Expectancy per trade | $-7.60 |
| Win rate | 36.0% |

Profitability: **FAIL**. Drawdown below$2,000: **PASS**. At least30 trades: **FAIL**. The50% consistency diagnostic: **FAIL / undefined with nonpositive total net**. Exact funded-account eligibility is not established: actual charges, contractual rule details, and platform permissions remain unverified.

This training-selected strategy did not demonstrate profitable generalization in the requested test diagnostic. The loss is preserved as observed. No alternate finalist, revised filter, parameter change or cost variant was evaluated after this outcome.

Existing source coverage: 2026-01-01 23:00:00+00:00 through 2026-11-05 23:59:00+00:00 UTC. The replay used 20,117 exact complete15-minute bars, from 2026-01-01 23:00:00+00:00 through 2026-11-05 23:45:00+00:00. One continuous$50,000 account was used over this test partition. The same frozen first96/last16 entry-bar suppression was applied; all warmup was within test, with no validation warmup or fitted preprocessing.

The2026 test period had already been observed for earlier strategies. This explicitly requested single-use replay is a reused-test diagnostic, not an untouched independent holdout. Existing split boundaries, prior results, training rankings, and earlier reservations remain byte-identical. A new reservation was written before hashing/loading any test price file; failed attempts would also consume the reservation.

Frozen strategy parameters:

```json
{
  "instrument": "MNQ",
  "family": "breakout",
  "lookback": 8,
  "threshold": 0.75,
  "stop_atr": 1.5,
  "target_r": 2.0,
  "hold_bars": 8,
  "session_start": 600,
  "session_end": 720,
  "max_contracts": 2,
  "trailing_atr": 0.0,
  "config_id": "mass_85721bb33e324b248878"
}
```

Recorded checks:

```json
{
  "positive_net": false,
  "realized_drawdown_under_2000": true,
  "closing_drawdown_under_2000": true,
  "intrabar_drawdown_under_2000": true,
  "no_permanent_lock": true,
  "no_funded_scenario_breach": true,
  "minimum30_trades": false,
  "consistency50": false
}
```

Execution verification: 25 independent ledger checks; 25 fixed chronological shared-simulator trade samples. Isolated fills/economics match; full account-path equivalence to the older simulator is not claimed.

[Saved result](mass_best_reused_test.json) · [Dashboard](http://127.0.0.1:8511/)

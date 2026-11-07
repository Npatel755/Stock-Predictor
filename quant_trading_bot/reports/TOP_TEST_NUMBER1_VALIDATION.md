# Displayed number1 strategy: requested validation diagnostic

`mass_4a0b95329be1d0438243` was ranked #1 by recorded test net P&L before validation access. Exactly that fixed MNQ breakout was evaluated once at base costs. No fitting, parameter changes, cost alternatives, validation-guided substitutions or test replay were performed.

| Metric | Validation 2024–2025 | Saved test 2026 |
|---|---:|---:|
| Net P&L | $4,434.00 | $3,645.50 |
| Realized-cash drawdown | $1,182.00 | $896.50 |
| Closing-equity drawdown | $1,256.50 | $1,068.00 |
| Intrabar drawdown bound | $1,290.00 | $1,124.50 |
| Trades | 148 | 81 |

**Positive validation net and drawdowns below$2,000: PASS on the requested observations. Overall recorded risk scenario: FAIL because of the permanent safety lock.**

A permanent safety lock was triggered by gap in usable market bars. Last trade closed at 2024-12-01 23:00:00+00:00. All later equity marks are flat because new entries were disabled. This is not uninterrupted trading over the full validation period.

The supplied validation source covers 2024-01-01 23:00:00+00:00 through 2025-12-31 21:59:00+00:00 UTC. Only exact complete15-minute windows were aggregated; first96/last16 entry bars were suppressed under the unchanged protocol. One continuous$50,000 account was replayed. A missing usable quote cannot be replaced with an invented flattening fill.

The validation period was previously viewed, and this candidate was selected using test outcomes. This is a reused-validation diagnostic, not independent confirmation or funded-account eligibility. The original training robustness failure and safety lock remain disclosed. Saved tests and earlier reservations remain byte-identical.

Frozen parameters:

```json
{
  "instrument": "MNQ",
  "family": "breakout",
  "lookback": 32,
  "threshold": 0.75,
  "stop_atr": 1.0,
  "target_r": 4.0,
  "hold_bars": 16,
  "session_start": 585,
  "session_end": 945,
  "max_contracts": 3,
  "trailing_atr": 1.0,
  "config_id": "mass_4a0b95329be1d0438243"
}
```

Recorded checks:

```json
{
  "positive_net": true,
  "realized_drawdown_under_2000": true,
  "closing_drawdown_under_2000": true,
  "intrabar_drawdown_under_2000": true,
  "minimum30_trades": true,
  "consistency50": true,
  "no_permanent_lock": false,
  "no_funded_scenario_breach": true
}
```

[Dashboard](http://127.0.0.1:8511/#top1-validation) · [Saved result](top_test_number1_validation.json)

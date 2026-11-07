# Frozen training-selected strategy: validation and test

Candidate `train_725a5b5da1` used the exact same frozen parameters in both evaluations. No fitting or tuning used either outcome.

| Period | Net P&L | Closing DD | Intrabar DD | Trades | Permanent shutdown |
|---|---:|---:|---:|---:|---|
| Validation: 2024–2025 | $5,071.00 | $1,062.00 | $1,095.00 | 109 | False |
| Testing: 2026 | $-126.00 | $911.00 | $945.00 | 45 | False |

The strategy lost $126 in the test evaluation. It remained under the $2,000 closing/intrabar drawdown ceilings but failed profitability and positive-confidence checks. The positive validation result did not carry over to test profitability. No adjustments, cost variants or alternate candidates followed this test result.

Test coverage: 2026-01-01 23:00:00+00:00 through 2026-11-05 23:59:00+00:00 UTC. The 2026 testing period was already used for earlier strategies, and the 2024–2025 validation period was previously observed. Neither is fresh independent confirmation. The new ranking used NQ training results only, but inherited design contamination and the training-consistency failure remain disclosed.

The existing validation evaluation was preserved without replay. Earlier test reports, reservations and validation artifacts remain byte-identical. A new exclusive reservation was written before reading test prices; failure would also have consumed this version's attempt.

Frozen parameters: `{"contracts": 2, "exit_minute": 720, "gap_high": 0.6, "gap_low": 0.1, "momentum_min": 0.05, "name": "gap_continuation_refined", "payoff": 4, "protection": "entry_075", "risk_stop": 1900, "sizing": "fixed", "stop_points": 25}`.

Test checks: `{"closing_drawdown_under_2000": true, "enough_trades": true, "intrabar_drawdown_under_2000": true, "no_permanent_shutdown": true, "positive_confidence": false, "positive_net": false}`.

Test session-bootstrap confidence interval for mean daily return: `[-0.00018183710407239815, 0.00020209954751131235]`.

No strategy is enabled for live trading. Fresh forward observations are needed for independent confirmation.

[Training selection audit](TRAINING_SELECTED_VALIDATION.md) · [Validation result](training_selected_validation.json) · [Test result](training_selected_test.json) · [Dashboard](http://127.0.0.1:8511)

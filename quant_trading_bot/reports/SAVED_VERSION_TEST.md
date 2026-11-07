# Frozen saved-version test evaluation

Saved candidate `follow_cf9f62ca20`: **$-356.00 net / $1,065.00 closing drawdown / $1,113.00 intrabar drawdown / 45 trades**.

The exact saved version that made $6,622 on reused 2024–2025 development data was frozen before test-price access. One base-cost replay was evaluated, without fitting, parameter changes, cost variants or tuning against the result.

Test coverage: 2026-01-01 23:00:00+00:00 through 2026-11-05 23:59:00+00:00 UTC. The 2026 period had already been evaluated for an earlier strategy, so this is a disclosed reused-test diagnostic, not independent out-of-sample confirmation. The original consumed reservation and original test report remain byte-for-byte unchanged.

The frozen strategy lost money. It remained below the $2,000 closing/intrabar drawdown limits, but profitability and positive-confidence checks failed. No parameter adjustment or follow-up variant will use this test outcome. Future strategy selection must use training history; fresh independent confirmation requires untouched forward observations.

Parameters: `{"contracts": 2, "exit_minute": 720, "gap_high": 0.6, "gap_low": 0.1, "momentum_min": 0.05, "name": "gap_continuation_refined", "payoff": 4, "protection": "entry_075", "risk_stop": 1900, "sizing": "fixed", "stop_points": 30}`.

Checks: `{"closing_drawdown_under_2000": true, "enough_trades": true, "intrabar_drawdown_under_2000": true, "no_permanent_shutdown": true, "positive_confidence": false, "positive_net": false}`.

[Machine-readable outcome](saved_version_reused_test.json) · [Saved development candidates](SAVED_CANDIDATES.md) · [Charts](research_charts.html)

# Current research handoff

**68 strategy/model definitions, 448 configurations, 746 market/configuration cases and 824 completed attempts** are recorded. Reruns and training screens are explicitly separated. See [STRATEGY_COUNTS.md](STRATEGY_COUNTS.md).

ES/NQ original one-minute reference history from 2010–2023 was used for fitting and internal selection; actual MES/MNQ 2024–2025 was validation. Reference fitting uses all eligible observations, with per-contract shards and external-memory/batched learners. The longer reference history is not relabeled as pre-2019 micro P&L.

Previously selected drawdown-constrained validation: **$2,385.00 net / $1,391.00 max DD** on MNQ. Frozen single-use 2026 test: **$6.50 net / $536.00 max DD / 28 trades**. This meets the nominal historical profit/drawdown target but fails to establish a dependable profitable trading bot. The test period is consumed; no repeated tuning or second untouched-test claim is allowed.

[Graphs](research_charts.html), [full measured results](../MODEL_COMPARISON.md), [strategy-count audit](STRATEGY_COUNTS.md), [final-test manifest](final_candidate_test.json). No real-money execution is enabled.

Forward paper data/review, exact account charges and platform permissions, and an authoritative historical calendar remain external dependencies. No paid data, account or subscription was purchased. Earlier crypto experiments and the original Databento ZIP remain preserved.

Automatic approval review previously rejected removal of the disposable `.clean-check` environment with “blocked by policy.” It remains a verification environment, not an active price dataset.

Additional post-final-test session/calendar research is recorded in [latest_session_window_study.json](latest_session_window_study.json). Its 2024–2025 results are reused-period exploration; independent confirmation requires new forward data.

The additional opening-gap/prior-session-structure batch is recorded in [latest_gap_structure_minutes_study.json](latest_gap_structure_minutes_study.json), under the same post-final-test exploratory restriction.

Latest MNQ risk/exit research: **$4,451.00 net**, **$1,638.00 closing-equity drawdown**, **$1,649.00 adverse-intrabar bound**, **146 trades**. Improvement over the reproduced $1,635.50 one-contract baseline: **$2,815.50**. This is 2024–2025 reused selection data; the 2026 test was not reused.

The [risk/exit improvement report](RISK_EXPANSION_RESEARCH.md) includes baseline comparisons and rejected risk-shutdown cases.

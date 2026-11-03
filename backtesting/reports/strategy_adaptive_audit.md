# Causal quarterly allocation diagnostic

The allocation rule was fixed before this run. It scores only marks/exits available at each UTC quarter boundary, using the preceding 12 months. It requires at least 20 closed legs and profit in both chronological halves, then chooses the best score (net less half drawdown), or cash if none qualifies.

**This is not independent walk-forward validation.** The candidate configurations were previously discovered using later 2023–2025 observations. Causality in allocation does not erase that candidate-selection bias. No strategy profile was overwritten.

| Scenario, 2022-01-01 to 2026-10-28 exclusive | Net P&L | Closed legs | Running-peak intrabar drawdown |
| --- | ---: | ---: | ---: |
| adaptive | $-98.29 | 57 | 2.96% |
| baseline | $-2,368.42 | 216 | 7.97% |
| first_v1_2 | $2,351.30 | 187 | 4.52% |
| refined_v1_2 | $2,832.35 | 187 | 4.73% |

Adaptive cash quarters: 15 of 20. Cash earns zero. Every comparator retains $100 planned risk. The adaptive strategy closes at scheduled quarter boundaries with commissions/slippage and resets setup state; fixed comparators run continuously. These differences are disclosed rather than hidden.

The complete decisions, their historical evidence, shadow ledgers, realized adaptive ledger, equity marks and source/data hashes are saved under `artifacts/optimization/adaptive_trailing_audit_verified/`. A cash-heavy result is reduced exposure, not proof of stronger entry signals. No live orders or future observations are included.

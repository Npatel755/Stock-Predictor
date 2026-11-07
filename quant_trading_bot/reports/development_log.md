# Implementation and experiment log

- Audited the existing worktree and pasted request before writing; isolated the futures project without changing existing crypto experiments.
- Foundation acceptance: 9 tests passed. Data timestamps, OHLCV, missing/optional quotes, completed aggregation, causal feature invariance, contract adjustments and purged folds were verified.
- Execution acceptance expanded to 15 tests: next-bar fills, commissions, integer quantity, partial fills, duplicate prevention, conservative limit/stop matching, raw roll-gap rejection and hard risk.
- Strategy/model/funded acceptance expanded to 20 tests. An invalid timestamp alignment implementation exposed pandas 3 datetime-unit differences; it was corrected using timestamp flooring, and regression coverage was added.
- Initial full synthetic MES campaign completed 22 candidates; missing XGBoost and insufficient meta-event counts were preserved as failures. Neither led to a profitability claim.
- Downloaded public MES/MNQ samples at no cost; recorded actual bounds/hashes/quality. Missing raw contract identity/adjustment provenance blocks their execution use.
- Verified official LucidFlex rules; retained checkout-setting conflicts and unknowns instead of guessing. Verified CME June 2026 holiday-adjusted expiration and customary roll dates.
- Five small neural networks, Gymnasium compatibility and PPO/DQN training were functionally exercised. Combined tests transiently failed under Windows memory/resource pressure; isolated groups passed, the self-test runner avoided duplicating numerical-library processes, and final suites passed.
- Additional free disk permitted XGBoost/Optuna/DuckDB/Plotly installation. A separate locked clean environment installed without global packages and passed dependency checking and core tests.
- Later MES/MNQ functional campaigns completed 23 candidates each. The sparse Donchian meta-event failure remains logged. Final holdouts were not evaluated; temporary synthetic tests alone exercise holdout-consumption guards.
- A full paper replay found a transient Windows sharing violation on atomic state replacement in the OneDrive workspace. Bounded retry was added without reverting to partial writes, with a dedicated regression test; a new replay version is retained separately.
- Final acceptance receipts and handoff manifest record the exact source hashes and latest run paths. No paid service, account purchase, message to another person, live execution, or unrelated process shutdown occurred.

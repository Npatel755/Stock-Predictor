# Training-selected candidate: one validation evaluation

**MNQ validation: $5,071.00 net, $1,062.00 closing drawdown, $1,095.00 intrabar drawdown, 109 trades.**

Candidate `train_725a5b5da1` was selected by the fixed NQ training-only ranking, frozen, then evaluated once at base costs on actual MNQ 2024–2025. No validation or test metrics entered the selection procedure. No parameters were fitted or adjusted after this validation outcome. Test prices were not opened.

This is not a fresh holdout: the inherited strategy design came from earlier validation-guided experiments, and 2024–2025 was already inspected. A new training-only ranking cannot erase that contamination. Fresh forward observations remain necessary for independent confirmation.

## Selection procedure

Use the eight candidates shortlisted from the 36-case NQ screen before the latest test evaluation. No new parameters. Exact continuous NQ 2022–2023 base and 2x-cost runs; prior 2010–2021 reference screening supplies older-history context.

Lexicographically prefer training qualification, no base/2x shutdown, positive base/2x profit, then worst-cost net divided by worst closing/intrabar drawdown, then candidate id. Qualification: positive 2010–2021 approximate NQ screen; positive 2022 and 2023 in both cost cases; >=60 trades per cost case; base/2x closing/intrabar DD <20000 actual NQ dollars; no shutdown. Freeze exactly one, even if none qualifies, as a disclosed diagnostic; never promote failure as a qualifying strategy.

Training-qualified candidates: 0 / 8. Selected candidate qualified: **False**. If no candidate qualified, the fixed procedure still selected the top-ranked diagnostic, as declared before evaluation; that does not make it a qualifying strategy.

Actual NQ dollars below reflect mini-contract economics and 10× micro risk budgets. They are not MNQ backtest results.

| Candidate | Base NQ net | Base DD | 2× NQ net | 2× DD | Base lock | 2× lock | Training qualified |
|---|---:|---:|---:|---:|---|---|---|
| train_725a5b5da1 | $9,781.50 | $14,982.50 | $6,758.00 | $15,465.00 | False | False | False |
| train_450a4eb2fa | $49,761.50 | $19,024.50 | $45,310.00 | $19,097.00 | True | True | False |
| train_235fdf637f | $46,278.50 | $19,127.50 | $41,830.00 | $19,137.00 | True | True | False |
| train_6fb9d2f342 | $40,381.50 | $19,024.50 | $39,250.00 | $19,097.00 | True | True | False |
| train_ce5b2e8c07 | $40,701.50 | $19,024.50 | $36,410.00 | $19,097.00 | True | True | False |
| train_e25a6fcaa8 | $40,078.50 | $19,127.50 | $35,790.00 | $19,137.00 | True | True | False |
| train_47784ba432 | $32,721.50 | $19,024.50 | $31,750.00 | $19,097.00 | True | True | False |
| train_14ba0a7b5e | $35,821.50 | $16,974.00 | $28,908.00 | $19,105.00 | False | True | False |

## Frozen validation outcome

Parameters: `{"contracts": 2, "exit_minute": 720, "gap_high": 0.6, "gap_low": 0.1, "momentum_min": 0.05, "name": "gap_continuation_refined", "payoff": 4, "protection": "entry_075", "risk_stop": 1900, "sizing": "fixed", "stop_points": 25}`.

Validation checks: `{"closing_drawdown_under_2000": true, "enough_trades": true, "intrabar_drawdown_under_2000": true, "no_permanent_shutdown": true, "positive_confidence": true, "positive_net": true}`.

Annual net: `{"2024": 2235.0, "2025": 2836.0}`.

Session-bootstrap mean-return confidence interval: `[5.3468085106383004e-05, 0.00034732301740812385]`. Multiple-testing diagnostic upper p-value: `1`. Nominal confidence after extensive prior research does not establish a durable edge.

No validation-driven adjustment or alternate candidate will follow this result. No live execution is enabled.

[Dashboard](http://127.0.0.1:8511) · [Training audit](training_only_selection.json) · [Validation result](training_selected_validation.json)

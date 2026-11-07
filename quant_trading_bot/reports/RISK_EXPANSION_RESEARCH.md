# Higher-profit risk and exit research

Latest MNQ risk/exit research: **$4,451.00 net**, **$1,638.00 closing-equity drawdown**, **$1,649.00 adverse-intrabar bound**, **146 trades**. Improvement over the reproduced $1,635.50 one-contract baseline: **$2,815.50**. This is 2024–2025 reused selection data; the 2026 test was not reused.

Selected parameters: `{"contracts": 2, "exit_minute": 690, "name": "regular_gap_continuation", "payoff": 3, "risk_stop": 1900, "sizing": "fixed", "stop_points": 40}`. Actual integer fills, prior-volume participation, per-contract commissions, spread/slippage and a size-dependent impact allowance are replayed. Profit was not obtained by multiplying an existing equity curve.

The first stage screens 72 NQ risk/exit combinations over the 2010–2023 training history, then freezes reference-ranked candidates plus explicit size/taper anchors before micro replay. The disclosed follow-up combines the longer exit with larger size after inspecting the first stage; it is additional reused-validation optimization. Original entry conditions remain unchanged. The internal drawdown stop is $1,800 in stage one and $1,900 in the follow-up; every selected result must remain below $2,000 for both closing and adverse-intrabar drawdown and must not permanently stop trading in base or 2×-cost replay. Price gaps can exceed configured stops in future trading.

The 2024–2025 results are continuous single-account selection-period simulations. The 2026 market period remains consumed by the original frozen test, with no second evaluation here. Long-history, uncertainty and independent-forward confirmation remain separate evidence requirements. No strategy is enabled for live execution.

| Candidate | Max contracts | Stop points | Target multiple | Exit ET | Sizing | Net | Max DD | Intrabar DD | 2× net | 2× DD | Permanent lock | Selection checks |
|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---|---|
| risk_5a1cd3f802 | 2 | 40 | 3 | 11:30 | fixed | $4,451.00 | $1,638.00 | $1,649.00 | $3,274.00 | $1,829.00 | False | True |
| risk_5e10b4f585 | 2 | 40 | 4 | 11:30 | fixed | $4,416.00 | $1,855.00 | $1,855.00 | $3,332.00 | $1,848.00 | True | False |
| risk_a879c48208 | 3 | 50 | 3 | 11:30 | drawdown_taper | $3,298.00 | $1,727.00 | $1,732.50 | $3,064.50 | $1,761.00 | False | True |
| risk_16f1c6a2af | 2 | 40 | 3 | 11:00 | fixed | $3,271.00 | $1,742.00 | $1,753.00 | $1,263.00 | $1,879.00 | False | False |
| risk_209a9ee9ad | 1 | 50 | 3 | 11:30 | fixed | $2,631.50 | $1,095.50 | $1,101.00 | $2,403.50 | $1,143.50 | False | True |
| risk_90b832856e | 2 | 50 | 3 | 11:30 | drawdown_taper | $2,496.00 | $1,345.50 | $1,351.00 | $2,105.00 | $1,410.50 | False | True |
| risk_5c9b11a774 | 3 | 40 | 3 | 11:30 | drawdown_taper | $2,408.50 | $1,558.50 | $1,564.00 | $585.50 | $1,621.00 | False | False |
| risk_074a55dcca | 1 | 40 | 4 | 11:30 | fixed | $2,375.00 | $1,270.00 | $1,284.50 | $2,144.50 | $1,293.50 | False | True |
| risk_696ba20cc4 | 1 | 40 | 3 | 11:30 | fixed | $2,225.50 | $819.00 | $824.50 | $2,010.00 | $866.00 | False | True |
| risk_bdd024f051 | 2 | 40 | 3 | 11:30 | drawdown_taper | $2,012.00 | $1,129.50 | $1,135.00 | $1,305.50 | $1,233.50 | False | True |
| risk_bdd6988902 | 1 | 40 | 3 | 11:00 | fixed | $1,635.50 | $871.00 | $876.50 | $1,412.50 | $932.50 | False | True |
| risk_b9fa12c849 | 3 | 50 | 3 | 11:30 | fixed | $1,402.50 | $1,923.00 | $1,923.00 | $1,234.50 | $1,906.50 | True | False |
| risk_db0d657877 | 3 | 40 | 3 | 11:00 | drawdown_taper | $1,237.00 | $1,341.50 | $1,347.00 | $32.50 | $1,498.00 | False | True |
| risk_2ba5e058cf | 3 | 40 | 3 | 11:30 | fixed | $1,227.00 | $1,921.50 | $1,921.50 | $-1,378.50 | $1,944.00 | True | False |
| risk_4c4b403992 | 3 | 40 | 3 | 11:00 | drawdown_taper | $993.00 | $1,657.00 | $1,662.50 | $324.50 | $1,750.00 | False | True |
| risk_8d5bc2ea43 | 3 | 40 | 3 | 11:00 | drawdown_taper | $918.00 | $1,555.00 | $1,560.50 | $-137.00 | $1,643.00 | False | False |
| risk_609751edd4 | 4 | 40 | 3 | 11:00 | drawdown_taper | $443.00 | $1,476.00 | $1,482.00 | $326.50 | $1,463.00 | False | True |
| risk_316b409c5f | 2 | 50 | 3 | 11:30 | fixed | $288.00 | $1,929.00 | $1,929.00 | $172.00 | $1,922.00 | True | False |
| risk_ed963d22c2 | 4 | 40 | 3 | 11:00 | drawdown_taper | $-186.50 | $1,572.50 | $1,578.50 | $-382.00 | $1,773.00 | False | False |
| risk_93e12b6bed | 4 | 40 | 3 | 11:00 | drawdown_taper | $-1,053.50 | $1,824.50 | $1,824.50 | $-1,074.00 | $1,810.00 | True | False |
| risk_7c90b4adb1 | 4 | 40 | 3 | 11:00 | fixed | $-1,076.00 | $1,818.00 | $1,818.00 | $-1,084.00 | $1,820.00 | True | False |
| risk_3350c2005d | 3 | 40 | 3 | 11:00 | fixed | $-1,285.50 | $1,843.50 | $1,843.50 | $-1,314.00 | $1,867.50 | True | False |

Selected annual P&L: `{"2024": 3640.0, "2025": 811.0}`. Remaining evidence checks: `{"positive_confidence": false, "training_verified": false}`.

| Cost multiplier | Net P&L | Max DD | Intrabar DD | Permanent lock |
|---|---:|---:|---:|---|
| 1.5× | $4,166.00 | $1,700.50 | $1,713.00 | False |
| 2× | $3,274.00 | $1,829.00 | $1,843.00 | False |
| 3× | $2,026.00 | $1,927.00 | $1,927.00 | True |

A higher historical return does not establish a durable edge or guarantee a future $2,000 drawdown cap. Retuning against the same selection years adds overfitting risk. A larger order can receive partial fills, and stressed costs can change risk gates and trade acceptance.

The first stage completed all fourteen cases; a duplicate keyword prevented only final report serialization. Publication was recovered from the archived frozen parameters, matching source hashes and completed result files without rerunning the search.

[Interactive charts](research_charts.html) · [Full machine-readable study](latest_risk_expansion_study.json) · [Published commission schedule](https://support.lucidtrading.com/en/articles/11508978-approved-products-and-commissions)

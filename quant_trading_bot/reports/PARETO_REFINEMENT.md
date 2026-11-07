# MNQ profit and drawdown research

MNQ entry-filter/protective-stop refinement: **160 reference settings screened, 14 selected MNQ replays**. The higher-profit/no-worse-drawdown goal was **not met**. Retained selection: **$4,451.00 net / $1,638.00 closing drawdown / $1,649.00 adverse-intrabar bound**. These are reused 2024–2025 selection results; no 2026 test prices were accessed.

The benchmark is the previously selected two-contract strategy: $4,451 net, $1,638 closing-equity drawdown and $1,649 adverse-intrabar drawdown bound. The fixed grid varies opening-gap bounds, minimum opening momentum, five protective-stop policies, 3:1/4:1 targets and two/three contracts. Stop changes use prior completed closes and never loosen a stop. Execution retains integer fills, volume participation, fees, adverse price adjustments and continuous account risk gates.

Reference screening uses original NQ 2010–2023 history; 2022–2023 supplies internal ranking. The top eight settings plus predeclared protective anchors were frozen before actual MNQ 2024–2025 replays. Independent-trade screens are approximate; selected settings also receive full continuous 2022–2023 reference replay. Older 2010–2021 evidence remains an approximate screen, not a continuous account verification. Every additional selection on these years increases overfitting risk. The consumed 2026 final test is unchanged.

Passing requires net profit above $4,451, closing drawdown at most $1,638, intrabar drawdown at most $1,649, no permanent shutdown, positive results in both selection years, at least 100 trades, and positive 2×-cost profit with both drawdowns below $2,000 and no shutdown. Long-history and confidence evidence are separate checks. No result has independent forward confirmation or deployment eligibility.

| Candidate | Gap range | Min momentum | Protection | Sizing | Contracts | Stop | Target | Exit ET | Net | Close DD | Intrabar DD | Trades | 2× net | Base goal | All checks |
|---|---|---:|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|
| refine_41d93a46b7 | 0.1–0.4 | 0 | entry_075 | fixed | 3 | 40 | 4 | 11:30 | $5,779.50 | $1,920.00 | $1,920.00 | 77 | $-1,366.50 | False | False |
| refine_1ea7bbf061 | 0.1–0.6 | 0.05 | entry_075 | fixed | 2 | 40 | 3 | 11:30 | $5,022.00 | $1,365.00 | $1,398.00 | 109 | $-1,576.00 | False | False |
| refine_5e2c2c3978 | 0.1–0.6 | 0 | entry_075 | fixed | 2 | 40 | 4 | 11:30 | $4,158.00 | $1,575.00 | $1,604.00 | 146 | $-1,568.00 | False | False |
| refine_bdb3c57bb2 | 0.1–0.6 | 0 | entry_075 | fixed | 2 | 40 | 3 | 11:30 | $3,963.00 | $1,341.00 | $1,374.00 | 146 | $-1,568.00 | False | False |
| refine_fa14e1b14d | 0.1–0.4 | 0 | entry_075 | fixed | 2 | 40 | 4 | 11:30 | $3,796.00 | $1,608.00 | $1,629.00 | 98 | $2,679.00 | False | False |
| refine_e9aa78f783 | 0.1–0.6 | 0 | entry_1 | fixed | 2 | 40 | 3 | 11:30 | $3,487.00 | $1,321.00 | $1,348.00 | 146 | $-797.00 | False | False |
| refine_412b74be08 | 0.1–0.6 | 0 | entry_1 | fixed | 2 | 40 | 4 | 11:30 | $3,407.00 | $1,935.00 | $1,935.00 | 142 | $1,991.00 | False | False |
| refine_b3ce96c890 | 0.1–0.6 | 0 | trail_075 | fixed | 3 | 40 | 3 | 11:30 | $2,079.00 | $1,944.00 | $1,944.00 | 124 | $-1,357.50 | False | False |
| refine_6667e0d697 | 0.2–0.4 | 0 | entry_075 | fixed | 2 | 40 | 4 | 11:30 | $1,407.00 | $1,158.00 | $1,191.00 | 55 | $1,177.00 | False | False |
| refine_22962a0c6b | 0.1–0.6 | 0 | trail_1 | fixed | 2 | 40 | 3 | 11:30 | $1,257.00 | $1,546.00 | $1,557.00 | 146 | $-214.00 | False | False |
| refine_3778a859dd | 0.2–0.4 | 0 | entry_1 | fixed | 2 | 40 | 4 | 11:30 | $928.00 | $1,888.00 | $1,888.00 | 55 | $573.00 | False | False |
| refine_b266b88393 | 0.1–0.6 | 0 | trail_1 | fixed | 3 | 40 | 3 | 11:30 | $834.00 | $2,052.00 | $2,052.00 | 133 | $-1,378.50 | False | False |
| refine_f356afa289 | 0.1–0.6 | 0 | trail_075 | fixed | 2 | 40 | 3 | 11:30 | $786.00 | $1,906.00 | $1,906.00 | 133 | $-513.00 | False | False |
| refine_11cb342e22 | 0.1–0.6 | 0 | entry_1 | fixed | 3 | 40 | 3 | 11:30 | $717.00 | $1,945.50 | $1,945.50 | 55 | $-1,353.00 | False | False |

## Selection failures

- `refine_5e2c2c3978` — selection failures: profit_above_4451, stress_2x_profitable, stress_2x_no_lock; unresolved evidence: positive_confidence.
- `refine_412b74be08` — selection failures: profit_above_4451, drawdown_no_worse, intrabar_no_worse, no_permanent_lock, stress_2x_no_lock; unresolved evidence: positive_confidence.
- `refine_41d93a46b7` — selection failures: drawdown_no_worse, intrabar_no_worse, no_permanent_lock, enough_trades, stress_2x_profitable, stress_2x_no_lock; unresolved evidence: positive_confidence.
- `refine_fa14e1b14d` — selection failures: profit_above_4451, enough_trades; unresolved evidence: positive_confidence.
- `refine_6667e0d697` — selection failures: profit_above_4451, enough_trades; unresolved evidence: positive_confidence.
- `refine_bdb3c57bb2` — selection failures: profit_above_4451, stress_2x_profitable, stress_2x_no_lock; unresolved evidence: positive_confidence.
- `refine_3778a859dd` — selection failures: profit_above_4451, drawdown_no_worse, intrabar_no_worse, both_selection_years_positive, enough_trades, stress_2x_no_lock; unresolved evidence: positive_confidence.
- `refine_1ea7bbf061` — selection failures: stress_2x_profitable, stress_2x_no_lock; unresolved evidence: none.
- `refine_e9aa78f783` — selection failures: profit_above_4451, stress_2x_profitable, stress_2x_no_lock; unresolved evidence: positive_confidence.
- `refine_f356afa289` — selection failures: profit_above_4451, drawdown_no_worse, intrabar_no_worse, no_permanent_lock, both_selection_years_positive, stress_2x_profitable, stress_2x_no_lock; unresolved evidence: positive_confidence.
- `refine_22962a0c6b` — selection failures: profit_above_4451, stress_2x_profitable; unresolved evidence: positive_confidence.
- `refine_11cb342e22` — selection failures: profit_above_4451, drawdown_no_worse, intrabar_no_worse, no_permanent_lock, both_selection_years_positive, enough_trades, stress_2x_profitable, stress_2x_no_lock; unresolved evidence: training_verified, positive_confidence.
- `refine_b3ce96c890` — selection failures: profit_above_4451, drawdown_no_worse, intrabar_no_worse, no_permanent_lock, both_selection_years_positive, stress_2x_profitable, stress_2x_no_lock; unresolved evidence: training_verified, positive_confidence.
- `refine_b266b88393` — selection failures: profit_above_4451, drawdown_no_worse, intrabar_no_worse, no_permanent_lock, both_selection_years_positive, stress_2x_profitable, stress_2x_no_lock; unresolved evidence: training_verified, positive_confidence.

## Retained result

Candidate: `risk_5a1cd3f802`. Parameters: `{"contracts": 2, "exit_minute": 690, "name": "regular_gap_continuation", "payoff": 3, "risk_stop": 1900, "sizing": "fixed", "stop_points": 40}`.

Annual net: `{"2024": 3640.0, "2025": 811.0}`. Evidence checks: `{"positive_confidence": false, "training_verified": false}`.

| Cost multiplier | Net | Close DD | Intrabar DD | Permanent shutdown |
|---|---:|---:|---:|---|
| 1.5× | $4,166.00 | $1,700.50 | $1,713.00 | False |
| 2× | $3,274.00 | $1,829.00 | $1,843.00 | False |
| 3× | $2,026.00 | $1,927.00 | $1,927.00 | True |

Run artifacts: `C:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot\runs\pareto_refinement_20261107T005849Z`. The carried benchmark is a prior result and is excluded from new-trial counts.

[Interactive charts](research_charts.html) · [Machine-readable results](latest_pareto_refinement.json)

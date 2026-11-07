# MNQ profit and drawdown research

MNQ profit/drawdown follow-up: **8 continuous reference replays and 8 MNQ replays**. The higher-profit/no-worse-drawdown goal was **met**. Retained selection: **$6,622.00 net / $1,386.00 closing drawdown / $1,419.00 adverse-intrabar bound**. These are reused 2024–2025 selection results; no 2026 test prices were accessed.

The user saved the $5,779.50 net / $1,920 drawdown candidate and accepted drawdown below $2,000. That anchor triggered the original $1,900 risk stop and ceased trading early; its result is retained as observed. The follow-up freezes 8 settings. Eight explicitly reused-validation exit/target settings, frozen after the six sizing follow-ups failed to improve the saved anchor. Fixed two-contract sizing, $1900 risk stop, 30/40/50-point stops, 3/4/5R targets and 11:30/noon exits. Original entry filters and 0.75R completed-close protection retained. The aim is higher profit and lower drawdown than the saved anchor, completing the period without a base-case shutdown. [Saved high-profit candidate](saved_candidates/refine_41d93a46b7/candidate.json) · [Saved lower-drawdown candidate](saved_candidates/refine_1ea7bbf061/candidate.json).

These settings are explicitly selected after examining reused 2024–2025 results. Each receives a continuous NQ 2022–2023 reference replay. Earlier 2010–2021 screens from the parent study are retained as context; new sizing rules do not have complete continuous-account verification over that earlier period. Sizes use only preceding completed equity and peak; existing positions are not resized retroactively. Stops use only prior completed closes and never loosen. Integer fills, costs and risk gates are replayed. No 2026 prices were loaded, and this is not independent confirmation.

The user goal requires profit above $5,779.50, both closing and adverse-intrabar drawdown below $1,920 (and the user's $2,000 ceiling), and no base-case permanent shutdown. Cost/evidence qualification additionally requires positive years, at least 100 trades, positive 2×-cost profit and both 2× drawdowns below $2,000 without shutdown. A base-case improvement can meet the user goal while failing these additional checks.

| Candidate | Gap range | Min momentum | Protection | Sizing | Contracts | Stop | Target | Exit ET | Net | Close DD | Intrabar DD | Trades | 2× net | Base goal | All checks |
|---|---|---:|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|
| follow_cf9f62ca20 | 0.1–0.6 | 0.05 | entry_075 | fixed | 2 | 30 | 4 | 12:00 | $6,622.00 | $1,386.00 | $1,419.00 | 109 | $5,618.00 | True | True |
| follow_0d4c377f32 | 0.1–0.6 | 0.05 | entry_075 | fixed | 2 | 50 | 3 | 12:00 | $6,516.00 | $1,338.00 | $1,348.00 | 109 | $6,072.00 | True | True |
| follow_d79493af79 | 0.1–0.6 | 0.05 | entry_075 | fixed | 2 | 50 | 3 | 11:30 | $6,024.00 | $1,402.00 | $1,435.00 | 109 | $5,574.00 | True | True |
| follow_9f2b7f71a8 | 0.1–0.6 | 0.05 | entry_075 | fixed | 2 | 40 | 3 | 12:00 | $5,820.00 | $1,247.00 | $1,280.00 | 109 | $-1,517.00 | True | False |
| follow_d992d1af8d | 0.1–0.6 | 0.05 | entry_075 | fixed | 2 | 40 | 4 | 12:00 | $5,471.00 | $1,247.00 | $1,280.00 | 109 | $-1,517.00 | False | False |
| follow_6ea8c996a5 | 0.1–0.6 | 0.05 | entry_075 | fixed | 2 | 40 | 5 | 12:00 | $5,156.00 | $1,368.00 | $1,440.00 | 109 | $-1,517.00 | False | False |
| follow_820899eda2 | 0.1–0.6 | 0.05 | entry_075 | fixed | 2 | 40 | 4 | 11:30 | $4,858.00 | $1,365.00 | $1,398.00 | 109 | $-1,576.00 | False | False |
| follow_1f41d697d9 | 0.1–0.4 | 0 | entry_075 | fixed | 2 | 40 | 4 | 12:00 | $4,132.00 | $1,608.00 | $1,629.00 | 98 | $2,983.00 | False | False |

## Selection failures

- `follow_820899eda2` — selection failures: profit_above_saved, stress_2x_profitable, stress_2x_no_lock; unresolved evidence: training_verified, positive_confidence.
- `follow_d992d1af8d` — selection failures: profit_above_saved, stress_2x_profitable, stress_2x_no_lock; unresolved evidence: training_verified, reference_2022_2023_profitable.
- `follow_9f2b7f71a8` — selection failures: stress_2x_profitable, stress_2x_no_lock; unresolved evidence: training_verified.
- `follow_6ea8c996a5` — selection failures: profit_above_saved, stress_2x_profitable, stress_2x_no_lock; unresolved evidence: training_verified, positive_confidence, reference_2022_2023_profitable.
- `follow_0d4c377f32` — selection failures: none; unresolved evidence: training_verified, reference_2022_2023_profitable.
- `follow_d79493af79` — selection failures: none; unresolved evidence: training_verified, reference_2022_2023_profitable.
- `follow_cf9f62ca20` — selection failures: none; unresolved evidence: training_verified.
- `follow_1f41d697d9` — selection failures: profit_above_saved, enough_trades; unresolved evidence: training_verified, positive_confidence.

## Retained result

Candidate: `follow_cf9f62ca20`. Parameters: `{"contracts": 2, "exit_minute": 720, "gap_high": 0.6, "gap_low": 0.1, "momentum_min": 0.05, "name": "gap_continuation_refined", "payoff": 4, "protection": "entry_075", "risk_stop": 1900, "sizing": "fixed", "stop_points": 30}`.

Annual net: `{"2024": 2928.0, "2025": 3694.0}`. Evidence checks: `{"positive_confidence": true, "reference_2022_2023_profitable": true, "training_verified": false}`.

| Cost multiplier | Net | Close DD | Intrabar DD | Permanent shutdown |
|---|---:|---:|---:|---|
| 1.5× | $5,943.00 | $1,412.00 | $1,445.00 | False |
| 2× | $5,618.00 | $1,438.00 | $1,471.00 | False |
| 3× | $5,216.00 | $1,492.00 | $1,525.00 | False |

Run artifacts: `C:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot\runs\profit_drawdown_followup_20261107T010757Z`. The carried benchmark is a prior result and is excluded from new-trial counts.

[Interactive charts](research_charts.html) · [Machine-readable results](latest_profit_drawdown_followup.json)

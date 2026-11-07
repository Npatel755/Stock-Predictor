# Additional strategy research after the frozen final test

Screened 16 new rule families in 128 reference-market/configuration cases using ES/NQ 2010–2023. Selected candidates then received 12 actual MES/MNQ 2024–2025 continuous-account replays with cost stress. No new 2026 prices were loaded. The original final-test reservation remains consumed.

These are reused selection-period results, not independent out-of-sample confirmation. No candidate passes every economic/confidence check or is enabled for live trading.

| Study | Transfer | Candidate | Net | Maximum DD | Trades | 2× costs net | All checks |
|---|---|---|---:|---:|---:|---:|---|
| Gap/structure — post-final exploratory | NQ->MNQ | session_a92f67f57d | $1,635.50 | $871.00 | 146 | $1,412.50 | False |
| Gap/structure — post-final exploratory | ES->MES | session_46bc2bba5c | $593.25 | $1,112.75 | 113 | $77.75 | False |
| Gap/structure — post-final exploratory | NQ->MNQ | session_878d5c165d | $532.00 | $921.50 | 146 | $328.00 | False |
| Gap/structure — post-final exploratory | NQ->MNQ | session_bea8bb611b | $-40.00 | $239.50 | 24 | $-72.00 | False |
| Session/calendar — post-final exploratory | NQ->MNQ | session_e4f488c6cf | $-65.00 | $904.50 | 48 | $-148.00 | False |
| Gap/structure — post-final exploratory | ES->MES | session_bea8bb611b | $-393.00 | $472.00 | 23 | $-523.50 | False |
| Gap/structure — post-final exploratory | ES->MES | session_9a2ff3a9d8 | $-455.50 | $558.75 | 23 | $-513.50 | False |
| Session/calendar — post-final exploratory | ES->MES | session_5a09f3938d | $-1,303.50 | $1,379.75 | 156 | $-1,792.25 | False |
| Session/calendar — post-final exploratory | NQ->MNQ | session_36d0f94cee | $-1,321.00 | $1,587.50 | 198 | $-1,785.50 | False |
| Session/calendar — post-final exploratory | NQ->MNQ | session_fab3be5840 | $-1,427.50 | $1,662.50 | 198 | $-1,796.50 | False |
| Session/calendar — post-final exploratory | ES->MES | session_aa04eca7a7 | $-1,463.50 | $1,539.75 | 156 | $-1,811.50 | False |
| Session/calendar — post-final exploratory | ES->MES | session_b58c0a66b8 | $-1,746.75 | $1,825.00 | 483 | $-1,777.00 | False |

## Leading observed candidate

NQ->MNQ `session_a92f67f57d`: `{"name": "regular_gap_continuation", "payoff": 3, "width": 2}`. Annual selection-period P&L: `{"2024": 1144.5, "2025": 491.0}`. Checks: `{"drawdown_below_2000": true, "enough_trades": true, "intrabar_drawdown_below_2000": true, "positive_at_2x_costs": true, "positive_confidence": false, "profitable": true, "training_verified": false}`.

The opening-gap continuation rule observes the completed 09:30–09:44 ET opening candles and the previous complete 09:30–15:59 regular session of the same contract. A gap between 0.1 and 0.6 of the prior regular-session range, followed by opening momentum in the gap direction, requests one entry at the next 09:45 opening price. The leading MNQ variant has a 40-point protective stop and 120-point target, exits at the 11:00 opening price, and takes at most one entry attempt per session. Risk limits, adverse fills and per-side commissions are applied by the shared event simulator.

Its 2010–2021 NQ screen lost $2,814 using actual mini contract economics, so its long-history training check fails despite positive 2022 and 2023 reference replays. The 2024–2025 block-bootstrap confidence interval spans zero. Historical drawdown below $2,000 does not guarantee a future loss cap. New forward observations are needed for independent confirmation.

An initial gap run was invalidated because its opening-window mask included prior-evening bars; retained artifacts are excluded from valid counts. The correction is covered by a full-session regression test. All original data and research artifacts remain retained.

[Interactive equity, monthly P&L and drawdown charts](research_charts.html) · [Strategy inventory](STRATEGY_COUNTS.md)

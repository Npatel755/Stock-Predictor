# QuantConnect / external research coverage log

Date: 2026-11-08. Purpose: hypothesis generation for MES/MNQ day-session sleeves (15-min bars, funded-account rules:
flat by 15:55 ET, $400/contract daily loss, $2k drawdown). Published results are leads, never evidence.

| Query / surface | Access | Result |
|---|---|---|
| quantconnect.com/docs/v2/writing-algorithms/strategy-library (index) | OK (HTML index, 80 entries) | entry slugs listed; deep pages are JS-rendered and return "Page Not Found" to curl |
| github.com/QuantConnect/Tutorials `04 Strategy Library/*` | OK (raw HTML + source) | 10 index-futures-relevant entries downloaded (see source_registry.jsonl) |
| github.com/QuantConnect/Research `Analysis/` | OK | 5 notebooks: fundamentals, Kalman pairs, mean-variance, VXX EMA cross, cointegration pairs - none intraday index futures |
| github.com/QuantConnect/Documentation tree | OK (14,512 paths) | strategy-library content not in this repo; option-strategy payoff pages only |
| QuantConnect MCP / LEAN CLI / QuantBook | not used | requires paid node / Docker + licensed data; local engine (scripts/mass_execution.py) used instead |
| Gao, Han, Li, Zhou (2018) "Market intraday momentum", JFE 129(2) | abstract via ideas.repec.org | source of the "first half-hour predicts last half-hour" mechanism (QC entry 1026 Intraday ETF Momentum) |

Not searched (declared gap): QuantConnect forum posts, YouTube, SSRN full texts beyond the abstracts above.
Prior in-house coverage (research/strategy_memory/lessons.md): ~370k + 500k + 200k configurations across momentum,
breakout, opening-range, trend, gap, VWAP, volatility, hybrid, auction/profile, CUSUM, entropy, analog mechanisms;
three news rounds (blackouts, post-release continuation, FOMC fade) all negative.

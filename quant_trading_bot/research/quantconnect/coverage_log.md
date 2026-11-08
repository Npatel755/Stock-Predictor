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

## Pass 2 — 2026-11-08 (Nick: "institutional strategies ... research strategies on quant connect")
| Query / surface | Access | Result |
|---|---|---|
| api.github.com QuantConnect/Tutorials "04 Strategy Library" | OK (85 dirs) | full list triaged; intraday-index-relevant: 04, 05, 07, 1023, 1026, 198, 25, 58 — all but 25 (VRP) and 1023 (ETF arb, no data) already tested or duplicated in-house |
| quantconnect.com strategy-library index | HTML 437 kB, no deep links (JS) | unusable via curl; GitHub tree used |
| Jane Street / Citadel public material | not scraped (no primary source for proprietary edges) | framed as market making / latency / ETF arb; only the passive-execution style is transferable — research/qc_1/PROTOCOL.md T1 |

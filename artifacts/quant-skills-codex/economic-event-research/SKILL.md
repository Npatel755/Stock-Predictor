---
name: economic-event-research
description: Conduct point-in-time macro-announcement and trading-session research for intraday index futures without leaking future releases.
---
# Economic event and session-aware research

Use when examining CPI, employment reports, FOMC, PPI, scheduled announcements, news-time slippage, session behavior, and optional trade blackouts for ES/NQ/MES/MNQ. Coordinate with `market-regime-analysis` and `execution-optimization`.

## Source-of-truth calendar
- Fetch dated **official historical release schedules** where possible (BLS, Federal Reserve, exchange). Store publication time with timezone and revision/as-of metadata.
- Distinguish **scheduled announcement time** (known in advance), **actual release timestamp**, **data values** (not available beforehand), and **revised values** (only available after revision).
- In simulations, use only information known at the decision timestamp. No trading decisions may exploit surprise magnitude, revisions, or event outcome before release.
- Convert to exchange-local and US/Eastern times with timezone-aware libraries; verify daylight saving transitions and exchange holiday closures.

## Research protocol
1. Build an event calendar with event type, announced timestamp, source, and confidence/coverage.
2. Join only as-of-available event metadata to historical market bars; forbid future joins on release values.
3. Evaluate a **predeclared** set of behaviors: avoid trading near releases, reduce risk, or model post-release entry **after data is available**.
4. Include realistic volatility and spread/slippage shocks, halts, and bar-resolution uncertainty, particularly around 08:30 and 14:00 ET when relevant to the event.
5. Stratify backtest results by event type, time-to-event, market session and trading costs.
6. Do not mine holdout event windows to choose the best blackout duration. Use training-only selection and frozen holdout evaluation.

## Guardrails
- The existence of an announcement does not establish a profitable event edge.
- If the archive lacks timestamp precision or reliable revisions, label the analysis exploratory and avoid causal claims.
- If event-time intrabar path is unknown, use tick data or conservative assumptions; never assume a stop was filled at the ideal pre-announcement price.

## Deliverables
A versioned, source-cited event calendar; timezone unit tests; leakage assertions; cost-adjusted stratified reports; training-only choice of event policy; holdout evidence and limitations.

## References
- BLS schedule: https://www.bls.gov/schedule/2026/
- BLS CPI schedule: https://www.bls.gov/schedule/news_release/cpi.htm
- Federal Reserve FOMC releases: https://www.federalreserve.gov/newsevents/pressreleases/2026-press-fomc.htm
- CME trading hours: https://www.cmegroup.com/trading-hours.html

The dated links are examples of official source types. Use the historical releases and schedules corresponding to the requested research dates; do not treat a current calendar as evidence of past publication timing.

---
name: intraday-session-clock
description: Build correct exchange-aware futures sessions, holiday calendars, daylight-saving transitions, trade dates and bar boundaries for NQ ES MNQ MES research.
---
# Intraday Session Clock and Calendar Integrity

## Trigger
Use before intraday futures feature construction, when joining events to trades, when resampling bars, when describing overnight vs RTH strategies, and whenever dates differ between providers. Coordinate with `data-integrity`, `futures-contract-lifecycle`, and `economic-event-research`.

## Requirements
- Treat each instrument's **exchange calendar** as configuration, not as `weekday < 5`. Confirm the exact relevant CME product calendar and vendor timezone from authoritative current references.
- Store event timestamps in UTC with explicit original timezone and source; do not silently replace timezone-aware stamps with naive dates. Preserve distinct `calendar_date`, `exchange_trade_date`, `session_id` and `contract_id`.
- Correctly handle DST transitions, ambiguous/repeated local times, spring-forward gaps, holiday closures, unscheduled halts, early closes and exchange maintenance breaks.
- Distinguish U.S. cash equity regular trading hours from futures Globex hours and any firm's funded-account flat-time requirements; never assume they coincide.
- Use exchange trade-date conventions when grouping daily P&L and sessions, especially after-midnight and evening trades.

## Tests required
1. Every bar has a start/end interval and availability timestamp; 5-minute bar signals cannot use the full bar before its end.
2. No artificial zero-volume 'candles' fill closed sessions unless the strategy explicitly expects marked unavailable periods; no forward-filling price into trades.
3. Create fixture rows around spring/fall DST, Friday close, Sunday reopen, holiday early close, daylight time and expiration week.
4. Verify sessions against official CME schedules and compare a sample of raw vendor timestamps; fail closed on unexpected gaps or duplicates.
5. Resampling is deterministic and never crosses a configured trading-session boundary without explicit approval and documentation.
6. News/event timestamps and settlement timestamps are converted using their proper release timezone; attach publication/effective-time separately.

## Outputs
A versioned session-calendar module/config, exchange-calendar source citation and retrieval date, session-parsing QA fixtures, count of gaps/duplicates by reason, and a plot/table of true trading minutes per session. Reject backtest outputs with unresolved session alignment.

## Official references
- CME trading/holiday schedules: https://www.cmegroup.com/trading-hours.html
- CME Time & Sales trade date vs calendar date: https://www.cmegroup.com/trading/about-time-sales.html

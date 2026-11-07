# Added Skills: Research Rationale and References

These instructions are aimed at seven narrowly-defined gaps in the original 36-skill research pack. They do not claim to teach an AI a permanently updated model or guarantee trading profits.

- CME MBO vs MBP: https://www.cmegroup.com/articles/faqs/market-by-order-mbo.html — order-based vs price-level aggregate depth and queue detail; requires appropriate licensed feeds.
- CME official holiday/trading schedules: https://www.cmegroup.com/trading-hours.html — holiday and early-close schedules vary by product and may be updated.
- CME Time & Sales: https://www.cmegroup.com/trading/about-time-sales.html — exchange trade date can differ from calendar date.
- Bailey and López de Prado, Deflated Sharpe Ratio: https://doi.org/10.3905/jpm.2014.40.5.094 — warns about selection bias among many experiments.
- White, A Reality Check for Data Snooping: https://doi.org/10.1111/1468-0262.00152 — multiple-model testing framework.
- Hansen, Test for Superior Predictive Ability: https://doi.org/10.1198/073500105000000063 — alternative superior predictive ability test.
- QuantConnect futures mapping: https://www.quantconnect.com/docs/v2/writing-algorithms/universes/futures — adjusted continuous signals vs executable mapped contracts.

Prioritize correctness and data sufficiency, then statistical evidence, then advanced order-flow alpha research. A 1-minute OHLCV archive is *not* an MBO dataset. Use permitted data only. No live orders, new paid data, cloud charges or secret access without user authorization.

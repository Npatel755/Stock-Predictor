# Devin: align my existing market data with point-in-time news and test improvements

Work inside my existing strategy research repository. Load `news-trading-intelligence` as the lead skill, and coordinate with `economic-event-research`, `point-in-time-feature-engineering`, `data-integrity`, `overfitting-defense`, `trade-edge-attribution`, `execution-optimization`, `risk-management`, `strategy-memory`, and `research-orchestrator`.

**Goal:** Investigate how historical news and economic releases relate to the price/volume behavior in the actual NQ, ES, MNQ, MES and/or equity datasets *already present* in my project. Determine whether information that was actually available at the time improves a tradeable strategy, compared with the price-only strategies already built. Do not assume every price movement has an identifiable news cause.

## Phase 1: Inspect existing data, don't duplicate it
1. Enumerate existing datasets, symbols, contract months, timezone, bar/tick frequency, historical coverage, data vendor, roll adjustments, and relevant existing strategies/backtest logs. Preserve original data and running jobs.
2. Identify the best index/futures history for signal research and the contracts actually traded (MNQ/MES); use historically valid constituents/weights only if evaluating company-specific news spillover into NQ/ES.
3. Inventory currently available historical news feeds, government archives, company releases, SEC EDGAR, original economic-release values, and historical consensus forecasts. Check legal access, licensing, exact publication and delivery timestamp precision before choosing them. Do NOT purchase subscriptions or bypass access controls.

## Phase 2: Build historical news-event records
4. Gather news/events for the **same date range as my existing market data**, starting with CPI, NFP/employment, FOMC decisions/press conferences, PCE, GDP and unexpected market-moving headlines. Add earnings/SEC/sector-specific news for relevant stocks only with a defensible NQ/ES exposure mapping. For crypto datasets, use crypto-specific events separately.
5. For each event store source/link, event category, affected assets, scheduled time if applicable, earliest verified publication timestamp, vendor delivery timestamp (if known), earliest research-system availability (if known), revision/version chain, and timestamp precision. Use UTC internally, handle `America/New_York` exchange sessions and daylight saving time.
6. For scheduled numbers use **initial-release values and the consensus actually published before the event**, not today's revised FRED values. Preserve the data vintage. If precise timestamps or authentic expectations are not obtainable, flag those events as descriptive only, not valid for intraday predictive claims.
7. Deduplicate syndicated articles and subsequent revisions. Do not infer causation just because a headline and price move were near one another.

## Phase 3: Align event and price data correctly
8. Perform a reproducible as-of join: a strategy at time `t` may only see releases with confirmed availability <= t minus realistic processing and network delays; use the correct next executable price after the signal, not the previous candle's close if the release occurred mid-candle.
9. Create both an **event-study table** (price/volume/spread/volatility changes over preregistered pre- and post-event windows for descriptive diagnosis) and a **tradable feature table** (only lagged, predecision news features). Keep these tables distinct so post-event results cannot accidentally enter prediction features.
10. Compare relevant periods with comparable non-event days and time-of-day controls. Include non-news moves and counterexamples. Analyze pre/post-event returns, realized volatility, ATR, volume, drawdown, liquidity, and where available bid-ask spreads and quote updates. If I only have 1-minute candles, use conservative next-bar execution and do not claim sub-minute edge.

## Phase 4: Discover and test limited news features
11. Start with no-trade/size-reduction around important announcements, volatility filtering, and a small set of carefully justified post-release drift/reversal ideas. Consider initial actual-vs-forecast surprise and historical article sentiment/novelty only when authentic point-in-time inputs exist.
12. Compare at least: (A) existing price-only strategy unchanged; (B) price-only + news risk filter; (C) price-only + small set of news features; (D) relevant naive/time-of-day and placebo controls.
13. Use chronological training/validation/final holdout with purge/embargo as needed. Research hypotheses and fit any sentiment models only using training data. Use validation sparingly for predeclared selection, and keep final test truly untouched. When prior strategy research already inspected the proposed holdout, treat it as contaminated and select a later unseen period or begin forward paper observations.
14. Correct for many experiments, use event-level confidence intervals/block bootstrap, and test regimes, changing liquidity/spreads, higher slippage, order delays, market open/close and funder drawdown rules. For NQ/ES signals, size and price actual MNQ/MES positions with correct contract specs/fees.

## Phase 5: Deliver production-quality evidence, not unverified claims
15. Create a deterministic pipeline, tests for timezones/revisions/duplicates/late publications/leakage, a documented event catalog, merged point-in-time features, and notebooks/plots explaining correlations versus tested predictive edges.
16. Report performance by event category and trading session; incremental OOS net P&L, expectancy, Sharpe/Sortino where meaningful, max drawdown, risk-limit failures, event counts, confidence intervals, and fill/cost assumptions. Report losers as well as winners.
17. Rank improvements by reproducible OOS evidence and practical implementability. Only integrate an improvement into an existing strategy as an optional **off-by-default** module, with a reproducible comparison and an easy rollback. Don't activate live orders or a paid news feed without my explicit approval.
18. Save conclusions, caveats, unsuccessful hypotheses and sources into strategy memory. If data or evidence is insufficient, clearly state `NO VERIFIED NEWS EDGE` and specify the minimum missing data needed.

**Deliverables:** `data_inventory.md`, `news_sources.md`, `news_event_catalog` (CSV/Parquet), `news_price_alignment` (Parquet), `news_event_study.md`, `news_feature_backtest.md`, `leakage_audit.md`, reproducible scripts/tests, and a decision memo on whether to add news to the current strategy, use it only as a risk filter, or reject it.

Start by auditing what is already in the repository. Execute the authorized research tasks independently, but do not use unsupported facts, invent data, modify my live trading configuration, spend money, or place live orders.

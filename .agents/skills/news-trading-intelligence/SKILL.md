---
name: news-trading-intelligence
description: Research and rigorously validate news-driven trading ideas for NQ, ES, MNQ, MES, and crypto using point-in-time event/news data, latency-aware simulation, and historical evidence; no live orders.
---
# News-driven trading intelligence

## Mission and trigger
Use this skill whenever researching whether **scheduled economic news, breaking headlines, official announcements, earnings, regulatory actions, central-bank communications, or crypto-specific news** influence future *tradable* returns, volatility, spreads, or risk for NQ/ES signals and MNQ/MES execution, or for ETH/BNB research.

Your objective is **testable and reproducible news research**, not the assumption that a headline predicts price. A sound outcome may be a **no-trade rule**, an execution/risk adjustment, or a well-supported strategy hypothesis. Do not deploy live orders or authorize paid feeds without explicit user consent.

Coordinate with these existing skills rather than replacing them:
`economic-event-research` (official calendar and release times), `point-in-time-feature-engineering`, `data-integrity`, `intraday-session-clock`, `strategy-memory`, `cross-source-triangulation`, `evidence-provenance`, `overfitting-defense`, `walk-forward-validation`, `execution-optimization`, `risk-management`, `statistical-evidence-auditor`, `simulator-verification`, and `research-orchestrator`.

## 1. Source hierarchy and access
1. **Official primary:** Federal Reserve FOMC statements, calendars, minutes and speeches; BLS CPI/PPI/Employment Situation; BEA GDP and Personal Income/Outlays (PCE); Treasury notices; SEC EDGAR for equity-related announcements; CME exchange notices. Record exact document URL, named publisher, document identity, and first-publication time.
2. **Licensable timestamped commercial/news feeds:** Research paid or permitted vendor feeds (e.g., QuantConnect-integrated Tiingo and Benzinga equity news) and check coverage, timestamp definitions, latency, entitlements, rights, historical depth, corrections, and asset mapping. **Do not assume an equity feed covers index-futures or crypto events.**
3. **Supplementary coverage:** Reputable journalism, permitted RSS/news APIs, exchange status pages, company releases and blockchain/protocol announcements. Treat social media, YouTube, forums, influencer commentary and unverifiable rumors as **unconfirmed** until corroborated.
4. No unauthorized scraping, bypassing paywalls, redistributing copyrighted full articles, using material nonpublic information, or pretending unavailable feeds/API credentials exist. Never fabricate headlines, release values, consensus estimates, timestamps, historical fills, or missing datasets.

## 2. Four-clock rule — absolutely mandatory
Every event/news record distinguishes, as independently verified and with timezone-aware UTC timestamps:
- `scheduled_time_utc`: time a release was supposed to occur, if preannounced (this alone can be known in advance)
- `first_publication_time_utc`: first confirmed time source made *this content/version* public (not necessarily the story's displayed date)
- `vendor_available_time_utc`: when the licensed feed first delivered it, if known
- `local_ingest_time_utc`: when our research/live system actually received it

Also record processing end, `signal_ready_time_utc`, and realistic `order_arrival_time_utc`. **A news-dependent signal cannot act before the information was both public and accessible to the chosen strategy, processed, and delivered.** A date-only timestamp is NOT adequate for intraday or latency studies. Record uncertainty instead of inventing microsecond precision. Use immutable as-of snapshots of revised data and changing headlines.

If the only historical timestamps are corrected, delayed, or ambiguous, label research exploratory and disallow any claim of executable news-alpha. Preserve the original feed records and corrections.

## 3. Build an auditable news and event dataset
- Record `event_id`, `source_id`, `url`, `publisher`, `category`, `symbols_affected`, relevance rationale, expected vs unexpected flag, original text/hash or permitted excerpt, headline version, timestamps above, source confidence, update/correction lineage, and asset exchange calendar.
- For scheduled macro data, record **consensus forecast with when it became known**, first actual release, vintage, revision time and `surprise = first_actual - contemporaneous_consensus`; normalize surprise only using past training-period distributions. Never compare modern revised values against stale old forecasts.
- For unexpected events, deduplicate syndicated copies, maintain an initial report vs confirmation/correction chain, and separately tag event credibility and propagation lag.
- Do not mix publication date, event date, and information availability. Validate holidays, DST, early closes, cash vs futures hours and contract roll dates; map NQ/ES lead instruments to executable MNQ/MES contracts appropriately.
- Dataset must identify whether raw input is delayed, post-processed, survivorship-biased or restricted by licensing. A backtest must use the *availability clock*, not the article's retrospectively assigned headline timestamp.

## 4. Research distinct classes of hypotheses
Pre-register a bounded candidate list with a mechanism and measurable trade outcome before testing. Examples:
A. **Risk avoidance / blackout windows** around CPI, PPI, employment, FOMC statement/press conference, GDP/PCE; test drawdown, spread and slippage, not just foregone wins.
B. **Post-announcement drift or reversal** after the actual release is available; use realistic reaction delay and event-conditioned volatility.
C. **Surprise-sensitive moves** using true pre-release consensus and original-vintage numbers, not hindsight-revised figures.
D. **Headline sentiment and novelty**, measured with fixed pretrained/frozen model, trained only on past articles; compare to keyword and no-news baselines.
E. **Cross-asset transmission** (e.g., rates/index response; crypto-specific regulatory or exchange news), only after verifying signal availability on each venue.
F. **Execution-only news controls**: reduce size, avoid market orders, widen expected slippage, pause during data uncertainty. Distinguish improved risk containment from positive predictive edge.

Never optimize many blackout windows, event labels, model prompts, thresholds, or reaction times against the same holdout until a winner emerges.

## 5. Causality and backtesting constraints
- Use strict chronological train / validation / **untouched final test** periods. Purge overlaps where positions span adjacent splits; use walk-forward evaluation across different monetary, volatility and market regimes.
- Set event-study windows and candidate signal horizons *in training*. Use placebo/pseudo-event controls matched by session, volatility and weekday; compare to time-of-day-only, price-only and news-avoidance baselines.
- For NLP/sentiment, record model/version/prompt, labels and training cutoff. Guard against articles summarizing *subsequent market moves*, which leak outcomes. Use only first-available versions, and classify publisher corrections separately.
- For news timing, no zero-latency fills. At release, model gaps, spread widening, order-book depletion, partial/missed fills, stop slips, exchange protection mechanisms, and infrastructure delays. If only 1-minute OHLCV exists, do **not** claim profits from reactions within that minute; require tick/quote data or a conservative next-bar design.
- Use the **tradable** MNQ/MES contract for costs/contract sizing; do not assume that ES/NQ continuous-history synthetic prices are executable. Verify any actual funded-account limits independently and preserve a configurable $2,000 research drawdown stress threshold.
- Correct for multiple hypothesis testing and event sample size; calculate confidence intervals grouped by event (not merely individual correlated trades). Report negative results and uncertainty.

## 6. Practical discovery workflow
1. **Inventory** available data and API rights. Produce a timestamp-precision and coverage gap report; do not buy services automatically.
2. **Catalog sources** and build a verified release-calendar/event schema with version history and timezones.
3. **Prioritize** high-impact NQ/ES topics first (FOMC, CPI, employment, PCE/GDP, surprise rate-related news); add crypto topics separately only when source coverage is credible.
4. **Audit source clocks** by sampling archived records; demonstrate no signal before actionable availability. Unit test late articles, vendor delays, revisions, duplicate syndication, DST changes and same-minute publication/fill ambiguity.
5. **Pre-register** up to five distinct hypotheses per research cycle plus placebo and existing-strategy controls.
6. **Run training-only studies** with per-event decomposition and cost/worse-fill sensitivity; select at most a small number of finalists using predeclared validation criteria.
7. **Freeze** code/data mappings/model and run untouched test once; record whether the test has been consumed, then proceed to prospective paper observations without using the same test to tune.
8. **Report** incremental improvement versus identical price-only strategy and no-trade baselines. Save findings to strategy memory with citations and rejected hypotheses.

## 7. Required outputs and go/no-go gates
Create:
- `news_sources.md` — URLs, legal access, costs, first-available timestamp semantics, coverage, source limitations
- `news_event_catalog.csv` or Parquet — point-in-time versioned records; missing fields explicit
- `news_hypotheses.md` — mechanisms, pre-registered features, holding horizons and status
- `news_event_study.md` — event counts, realized net expectancy, confidence intervals, drawdown, per-event analysis, costs, failure modes, and comparisons
- `news_execution_audit.md` — observed/simulated delivery lag, bid/ask spread, fill assumptions, headline revisions, and blackout sensitivity
- deterministic unit tests — timing leakage, vintage integrity, duplicate removal, trading session, late feed, and futures roll

Acceptance requires a meaningful out-of-sample improvement **after** commissions, spread, slippage and realistic access latency; stability across event samples; believable capacity; satisfactory funded-account risk; and forward paper observations. Otherwise mark `NO VERIFIED NEWS EDGE` and recommend only risk control or further data collection. Never assert news-derived profitability from correlation or headlines alone.

## Source reference map
- BLS release calendar: https://www.bls.gov/schedule/2026/
- Federal Reserve monetary policy and FOMC releases: https://www.federalreserve.gov/monetarypolicy.htm
- BEA release schedule: https://www.bea.gov/news/schedule/
- SEC EDGAR API docs: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- QuantConnect Tiingo news (equities): https://www.quantconnect.com/docs/v2/writing-algorithms/datasets/tiingo/tiingo-news-feed
- QuantConnect Benzinga news (equities): https://www.quantconnect.com/docs/v2/writing-algorithms/datasets/benzinga/benzinga-news-feed
- QuantConnect alternative-data delivery constraints: https://www.quantconnect.com/docs/v2/cloud-platform/datasets/quantconnect/alternative-data

These are research entry points, not endorsements, subscriptions, proof of tradeable edge, or guarantees of access.

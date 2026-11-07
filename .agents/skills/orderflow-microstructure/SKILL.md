---
name: orderflow-microstructure
description: Test executable intraday futures hypotheses from bid-ask quotes, trades and order-book data without pretending OHLCV reveals queue position or true buying pressure.
---
# Order-flow Microstructure Research

## Trigger
Invoke when researching ES/NQ/MES/MNQ strategies based on liquidity, order-book imbalance, bid/ask behavior, spread, order flow, volume delta, market impact or limit-order execution. Coordinate with `execution-optimization`, `data-integrity`, `cross-contract-transfer`, and `overfitting-defense`.

## First classify the available data
- **OHLCV bars**: prices and aggregate volume; cannot reconstruct historical bid/ask, queue priority, aggressive order side or individual order modifications accurately.
- **Trades/ticks only**: time and sales; aggressor classification may be direct if provided or otherwise uncertain; do not market a heuristic as observed fact.
- **MBP/L2**: aggregated price-level depth; does not identify individual queue position.
- **MBO/L3**: individual displayed orders and order updates may support more detailed queue estimates, but feeds have missing/hidden liquidity and specific semantics.
- Capture venue, event timestamps vs received timestamps, sequence numbers, coverage, price precision, time zone, rollover periods and subscription/usage rights. Classify each hypothesis as supported, proxy-only or impossible with available data.

## Research protocol
1. Select an economic mechanism and a falsifiable statement: e.g., transient imbalance forecasts a short-term move net of taking-spread costs; or a liquidity shock predicts mean reversion. Avoid post-hoc narratives.
2. Construct past-only features: spread, depth imbalance, order-flow imbalance, signed trade volume (only when defensible), realized quote updates, cancellation intensity, microprice, and trade-through rates. Normalize by volatility, spread and time of day when appropriate.
3. Build baseline comparisons: price-only, time-of-day, simple momentum, and randomized/placebo labels. Match frequency and eligible observations.
4. Lag all signals to their actual information availability; simulate reaction delay. A bar-close value cannot execute at the same bar's earlier price.
5. Model passive queue fills conservatively; without sufficient queue data report an interval or refrain from assuming fills. Test aggressive marketable orders including spread, fees, slippage and partial fills.
6. Evaluate separately by market, session, liquidity regime and shock periods, with sample counts and dependence-aware uncertainty. Penalize searching many thresholds.
7. Transfer ES->MES and NQ->MNQ hypotheses only after independently estimating micro-contract spreads, depth, fees and fills.

## Anti-leakage and data ethics
Never infer a historical order-book state from future snapshots; avoid rebuilding missing updates using later state. Follow data provider licensing and never instruct scraping restricted feeds. When only 1-minute OHLCV exists, produce a **data sufficiency verdict** and OHLCV-compatible hypotheses instead of fabricated MBO analytics.

## Deliverables
A feature dictionary (field, formula, event availability, lag), input dataset report, execution-model assumptions, independent baseline comparison, per-regime after-cost result with uncertainty, rejected hypotheses, and a verdict `SUPPORTED / PROXY-ONLY / NOT TESTABLE`.

## Source
CME Group MBO vs MBP explainer: https://www.cmegroup.com/articles/faqs/market-by-order-mbo.html

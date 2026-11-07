---
name: execution-optimization
description: Evaluate market microstructure, fill uncertainty, spreads, fees and strategy sensitivity to execution; use when researching intraday MNQ/MES strategies and order types.
---

# Execution Optimization

## Objective
Separate market alpha from favorable but unrealistic fill assumptions.

## Procedure
1. Define venue, contract, order type, submission time, quote availability, regular vs extended sessions and whether tick/level-1/level-2 data are available.
2. Include commissions and per-contract exchange/regulatory charges, spread crossing, variable slippage and tick rounding. Model latency and volume participation when relevant.
3. Market orders incur crossing costs; limit orders fill only with a defensible queue/price-crossing model, not automatically whenever bar low/high touches limit; stop-market gaps can fill worse than trigger.
4. For 1-minute OHLC only, run conservative fill scenarios and classify ambiguities; do not claim precise intrabar execution or queue position.
5. Compare micro execution assumptions against directly observed MES/MNQ data, rather than copying ES/NQ liquidity estimates. Test regular hours versus thin sessions.
6. Perturb fills: +1/+2/+4 ticks and higher fees; inspect whether expected edge is smaller than friction. Exclude strategies whose profit depends on near-free fills.
7. Estimate tradability and capacity without claiming historical order book replay when quotes/depth are unavailable.

## Deliverable
Gross/net decomposition, cost per trade, slippage sensitivity, fill-assumption matrix, trade-size capacity notes and execution uncertainty warning.

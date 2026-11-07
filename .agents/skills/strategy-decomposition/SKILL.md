---
name: strategy-decomposition
description: Decompose an existing strategy into its signal, filter, exit, sizing and execution components to isolate their contribution.
---

# Strategy Decomposition

## Steps
1. Convert the original strategy into a minimal documented pipeline: data -> features -> signal -> filters -> entry -> position sizing -> exits -> fills -> risk overlay.
2. Pin the baseline run and all experimental controls: data snapshot, date split, costs, seed, code commit, and market.
3. Measure the baseline *on training data* with stable evaluation metrics and event-level logs.
4. Run controlled removals and swaps: signal only, filters only, exits vs fixed horizon, static vs dynamic sizing, with and without execution assumptions. Use fixed trade notional when comparing edge to avoid confusing sizing with alpha.
5. Examine dependence and interactions (e.g., a filter helps only with one exit); prefer factorial tests on a small predetermined grid to massive uncontrolled searches.
6. Test nearby parameters, signal delays and higher fees. Reject components whose improvement is fragile, statistically unconvincing or heavily dependent on a few trades.
7. Store each component's marginal effect, run IDs, and failure modes. Keep the original intact and treat every variant as a counted hypothesis.

## Output
Component map, baseline-vs-ablated table, effect on risk and turnover, experiment count, and list of unnecessary complexity.

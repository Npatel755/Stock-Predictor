---
name: hypothesis-transfer
description: Transfer plausible trading mechanisms across assets or timeframes while testing market-specific costs and invalid assumptions.
---

# Hypothesis Transfer Across Markets

## Guiding question
*What economic mechanism might survive a change of instrument or timeframe?* Copy ideas, not historical P&L.

## Procedure
1. Formalize source hypothesis (why it should work; prerequisites for liquidity, volatility, session behavior and available features).
2. Build a transferability matrix: source vs target contract multipliers, tick values, sessions, roll rules, quote quality, spreads, fees, volatility, and time zones.
3. Map signals in normalized terms (returns, volatility units, notional exposure) **without assuming** source and target are execution-equivalent.
4. When NQ/ES are used for research but MNQ/MES for trades, use target-specific quotes, fee schedules, tick specs, and fill assumptions; invoke `cross-contract-transfer`.
5. State which original conditions break (24/7 crypto vs market-hours futures; equity borrow constraints; index reconstitution).
6. Evaluate transfer hypotheses on the new market's **training** partition; pre-register validation selection, freeze, and preserve its test holdout.
7. Compare to simple target-market baselines and record negative transfers.

## Output
Transfer hypothesis, invariant vs changed assumptions, feasibility audit, precise transformed rules, and stop criteria.

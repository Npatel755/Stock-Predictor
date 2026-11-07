---
name: trade-edge-attribution
description: Decompose futures-strategy P&L into explainable sources such as session, holding period, direction, fees and market conditions without mining the holdout.
---
# Trade Edge Attribution

## Trigger
Invoke after any serious train-period strategy backtest and during a predefined validation report. Coordinate with `strategy-decomposition`, `signal-ablation`, `market-regime-analysis`, `strategy-memory` and `statistical-evidence-auditor`.

## Procedure
1. Materialize a canonical trade/fill ledger with order timestamps, available signal timestamps, instrument/contract, side, quantity, entry/exit price, fee, slippage, risk budget, exit reason, session and P&L. Reconcile aggregate equity to the ledger. If the records cannot reconcile, block attribution.
2. Decompose P&L into gross signal contribution, explicit commission/fees, spread crossing, modelled slippage and financing/carry where applicable. Avoid crediting signal alpha for synthetic continuous-roll adjustments.
3. Produce **descriptive** cuts by time of day, day of week, session, volatility/liquidity, long vs short, hold time, stop/target/timeout, spread regime and contract month. Record sample sizes and exposure for every bucket.
4. Investigate concentration: top trade contribution, top five sessions, worst losing streaks, gain-to-pain, wins from rare news moves, and regimes with no trades. Show weighted as well as typical outcomes; compare expected edge in ticks against actual round-trip friction.
5. Separate hypothesis generation from evidence. If a training-slice filter looks promising, register it as a **new** strategy/trial, test using training-only research, and apply predeclared validation. Never opportunistically remove losing test months or retroactively label sessions after observing outcomes.
6. Distinguish changes due to fewer trades/risk exposure from predictive improvement using a matched-exposure benchmark.
7. When transferring NQ/ES research to micro contracts, recompute fees, tick conversion, contract quantities and participation constraints on the actual instrument.

## Report
Create a source-linked P&L waterfall, gross-to-net tick chart/table, per-slice outcome counts and confidence, concentration diagnostics, feature/entry/exit attribution, and a list of plausible causal hypotheses vs observational correlations. Conclude `EDGE DIVERSIFIED`, `EDGE CONCENTRATED`, or `INCONCLUSIVE` with evidence.

## Guardrails
A positive conditional subset discovered using holdout results is not independent proof. Small-sample subgroup plots can be misleading; do not add countless filters in pursuit of a prettier curve.

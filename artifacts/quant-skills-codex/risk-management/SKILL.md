---
name: risk-management
description: Model strict futures and funded-account risk restrictions; use when sizing MNQ/MES, computing trailing drawdown, evaluating LucidFlex-style rules or controlling losses.
---

# Risk Management

## Objective
Keep accounting and breach detection realistic; account compliance is a separate test from profitability.

## Procedure
1. Verify the current official rules for the specific account before coding: initial balance, drawdown amount, drawdown basis (intraday unrealized high-water vs end-of-day), trailing/floor-lock rule, daily loss limits and reset timezone, contract cap, consistency rule, prohibited trading conditions, and evaluation-to-funded changes. Record link, retrieval date and uncertainty. Unknown rules must be configurable and reported as unknown, never fabricated.
2. Research baseline: initial balance $50,000 and a provisional $2,000 risk budget only; this is NOT confirmation of LucidFlex live rules. Configure 50% consistency only if contract terms confirm its calculation and stage.
3. Maintain intraday mark-to-market equity, realized balance, trailing high-water, lockout floor, daily realized+unrealized P&L, open-order exposure, and breach flags in event time. A threshold touch may cause immediate failure even when a bar closes recovered.
4. Contract specifications: ES $50/point; MES $5/point; NQ $20/point; MNQ $2/point. All have a 0.25 point minimum tick for these outrights: ES $12.50, MES $1.25, NQ $5.00, MNQ $0.50. Verify exchange specs if changed.
5. Position sizing from stop distance must use tick rounding, multiplier, fees and gap/slippage buffers; use max-risk constraints across correlated positions; never size from assumed guaranteed stops.
6. Simulate conservative stress scenarios (gap losses, slippage spikes, correlated drawdowns, high-volatility sessions, fee drag) and hard-stop behavior. Do not imply that passing historical checks guarantees a prop account payout.

## Deliverables
Config with provenance, per-event risk ledger, explicit breach timestamps/reasons, parameterized daily-loss on/off scenarios and survival statistics.

The specification values above are reference arithmetic, not a current verification receipt. Verify current official contract/account specifications before relying on them for financial decisions; retain user-confirmed settings and unresolved fields separately.

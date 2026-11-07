# Forensic Audit Protocol — QuantConnect strategies

## Audit must answer ALL questions

### Research source and chain of evidence
- What is the primary URL and evidence date? Is this a team tutorial, community post, original paper, open notebook, or a copied summary?
- Are source code and exact project version actually accessible? What license applies? Record SHA or archive date.
- Which data and market periods were used to discover the idea? Which published periods could already have influenced design?
- If screenshots/quoted metrics are the only evidence, label `AUTHOR_CLAIM_ONLY`.

### Strategy math
- What exactly are the raw inputs and signal equations? `indicator_t` may only use bars available at `t`.
- What are the threshold, parameter range, warm-up bar count, market hours, signal sampling, and decision timing?
- What is the exact state machine (flat/long/short/cancel/partial fill)? Is opposite-entry also an exit?
- What happens when bars are missing or simultaneous stop and take-profit are reached?

### Implementation details in LEAN
- Is the Python/C# code complete enough to execute with stated package and LEAN version?
- What is the difference between indicator subscription series, history results, and actual order security?
- Is a continuous future merely the adjusted indicator input and `Mapped` the traded contract?
- Does mapping change when the security rolls? Who closes/opens old/new contracts, at what time and price?
- Which fill, fee, slippage, margin/buying-power and brokerage model are used? Defaults may be optimistic.
- Does a data slice trigger on close or when bar becomes available? Does code place next-bar orders or same-callback orders? Never assume a free same-close fill.

### Reproduction evidence hierarchy
1. Exact original code + licensed same dataset + same settings + matched trade-by-trade ledger.
2. Approximate original code/data with explainable differences and matched directional behavior.
3. Independent equivalent with unknown source details; not a faithful reproduction.
4. Article screenshot/backtest claim only; NOT VERIFIED.

### Independent robustness
- Compare no-skill baseline, time-of-day baseline, and randomized or delayed signals.
- Apply +1 tick / +2 ticks / spread-sensitive stress as instrument-appropriate; avoid treating fixed values as universal.
- Vary parameters around the claimed sweet spot; prefer stable plateaus.
- Check multiple years, both trend and range regimes, news/non-news days and session windows.
- Account for multiple hypotheses examined and guard against holdout mining.
- Separate gross P&L, commissions, fees, slippage, roll cost, and daily funded-account rule compliance.

### Verdict categories
- `REPRODUCED`: core source behavior is faithfully reproduced, not necessarily profitable.
- `PARTIAL`: important source behavior recreated, with listed differences.
- `NOT_RUN`: static analysis only; no runnable test.
- `FAILED`: replication conflicts with source claim under comparable assumptions; explain differences.
- Research verdict separately: `APPROVED_FOR_RESEARCH`, `NEEDS_DATA`, `REJECTED`, `UNVERIFIED`.

## Example of a careful hypothesis (not an endorsed trading rule)
A Dual Thrust-like breakout could be evaluated by computing thresholds from previously completed days, conditioning on market regime inferred from prior data, then placing orders only after the required information is known. Research the original source formula; do not silently substitute a generic breakout. Test original asset first when feasible, then propose NQ/MNQ adaptation on TRAINING data only.

## Critical evidence statement
QuantConnect Strategy Library tutorials and public notebooks are instructional resources, not a guarantee of independently verified, live-profitable strategies. A reproduced curve on the originally published period is an implementation test, not independent proof of generalization.

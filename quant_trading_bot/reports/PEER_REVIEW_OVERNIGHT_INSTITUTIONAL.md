# Peer review: `overnight_institutional_master.py` run of 2026-11-08 (Codex/Antigravity, Nick's PC, uncommitted)

Source: `runs/overnight_institutional_research/` + `runs/saved_portfolio_F_multi_strategy_ensemble/summary.json` on Nick's PC
(scripts `scripts/overnight_*.py`, `scripts/research_*.py`, written 02:27-03:13 EST, not committed). Reviewed read-only.

## What it did
Training-only (2020-23) grids on MNQ morning breakout mechanics (dynamic vol sizing $100-250, breakeven ratchet 0.75-1.75R,
MES-agreement filter 0-1.0, RVOL 1.0-2.0x), an afternoon 13:00-15:45 MNQ momentum sleeve (27 variants), MES->MNQ lead-lag
(18 variants), then assembled a 4-sleeve "pod" and ran it on train / validation / **test (2026)**. Separate "Portfolio F"
(= Ensemble Beta + an MNQ afternoon sleeve) was also evaluated on all three splits. Portfolio E adversarial friction stress.

## Findings worth keeping
- Portfolio E friction stress (useful, reproducible): validation intrabar DD $1,744 at baseline -> $1,913 at 2-tick slip +
  $0.75 fee -> $1,946 at 2-tick + $1.00. Validation net falls $3,142 -> $1,426. E sits within ~$60-250 of the $2k rule in
  2024-25 under realistic adverse friction. Consistent with RISK_OF_RUIN_CANDIDATES.md: Beta is the only candidate sized for $2k.
- Portfolio F: validation intrabar DD $2,244 (> $2k, breach), train DD $2,240 (also > $2k). Not promotable. Adding a 4th MNQ
  sleeve to Beta raised DD past the rule; sleeve 4 (afternoon) validation PF 1.18 on 40 trades.
- 4-sleeve pod: train Calmar 5.96 -> validation 1.19, validation DD $9,894 (5x the rule), 2026 DD $6,427. Fails.
  The log line "Worst Historical DD $9,894.50 (Strictly < $2,000 threshold with $-7,894.50 buffer!)" is a sign error; the
  claim is false.
- MES-agreement filter on MNQ AM breakout (train PF 1.325, DD $1,012) and afternoon sleeve (train PF 1.757) did not survive:
  in the pod, s2 (AM breakout + filter) validation DD $2,896 and s4 (afternoon) validation DD $1,709 / 2026 net -$714.
  Treat both as tested-negative; no need to re-run in the mass engine.
- Lead-lag (MES lagged 0-2 bars as MNQ entry confirm) best train PF 1.25 with DD $1,972-2,609 at 2 contracts: DD alone
  disqualifies under the $2k rule, before validation.

## Process issues (for the shared lessons file)
1. 2026 test split was evaluated and reported for strategies that had already failed validation; the test window is now
   consumed for Portfolio F and the pod, as it was for E/Epsilon/Beta. Any future candidate from this family has no clean
   test year left.
2. Selection by max profit factor over 5-27 variants on training with no placebo / no per-year consistency gate; our gate
   (>=60% positive years, worst annual DD < $1k, beats placebo) would have rejected the pod sleeves before validation.
3. "Monte Carlo 0.46% breach" for Portfolio F is a naive bootstrap on training trades; the same portfolio shows an actual
   $2,244 validation DD. Model-conditional numbers must be reported with the realized OOS DD next to them.
4. The daemon loops the same five computations every 45 s (243+ cycles, 1,710 identical heartbeat ledger lines by 11:20
   EST) and produces no new information; it should be stopped.

## Decision
Paper set unchanged (Portfolio E, Ensemble Epsilon, Ensemble Beta). Nothing from this run is promotable.

# Research memo — 2026-11-09 (evening), rounds after RESEARCH_MEMO_2026-11-09.md

All rounds below: 2010–23 training only, pre-registered protocols (research/<round>/PROTOCOL.md), 200 placebos where applicable, micro costs
($0.61/side, 1.75/1.0-tick spread, 1 tick slip), $2,000 funded floor. 2024–25 and 2026 were not loaded by any of them. Paper = simulated, no routing.

## Learned
- **Overnight reopen-dip** (overnight_3–7): erratum fixed (Sunday gap vs Friday close). v2 = hold MNQ 18:05 → 09:45 when MNQ *and* MES reopen
  ≤ −0.5σ: +$11,797 / 490 nights / 12 of 14 years / DD $1,646 / 200 of 200 placebos; threshold re-chosen yearly from past data lands on −0.5σ
  9 of 10 years (walk-forward). Calendar gates (releases, FOMC, TOM, month-end, OPEX, pre-holiday: overnight_5/6, calendar_2) add nothing.
  Paper: `overnight_dip` v1.0.1, `overnight_dip_v2`, `overnight_dip_mes`. Runner parity with research: exact (reports/PARITY_OVERNIGHT_V2.md).
- **Architecture C** (Antigravity) replicates (+$16,070, 11/14, DD $1,596) but is at its own optimum (archc_1: 0 of 18 changes help); Crabel
  leg does not transfer to MES (crabel_1); Enhanced C = same strategy. Paper: `ag_arch_c`, `ag_arch_c_lite`.
- **Backwardation stand-aside** (prior CBOE close VIX > VIX3M): morning sleeves lose $18–23/trade on those days, afternoon trend sleeve gains;
  filtered versions on paper as `ag_arch_c_v2`, `ag_all_weather_v2`, `ag_quad_v2`. Removed days worse than 19 of 20 random same-count day sets
  in every case.
- **Sizing** (sizing_1/2): the $150 stop-risk budget blocks $150–250-risk trades that are 4–7× better than average, but they cluster in
  2020/2022 and lift DD; only All-Weather passes unbounded (`ag_all_weather_v2_1c`). $250 budget = no budget for DD. >$250-risk trades are rare and
  negative — nothing supports trading today's $425+ stops. Closed.
- **Portfolios**: overnight v2 + Arch C v2 (DD $2,315) and + Quad v2 ($2,396) exceed the floor in March 2020; **overnight v2 + All-Weather v2 1c
  fits** (closed DD $1,633, marked/intraday-trailing DD $2,043 once, 1-y breach 1.9 %, corr 0.09, 0 overlaps). Staging: one leg until ≈$500
  banked for that pair, ≈$3k for the others.
- **Withdrawn / rejected**: Champion 2 and NQ-leader (one-bar look-ahead), Daily-200-SMA gate, crude-as-MCL transfer, calendar effects
  intraday and overnight, Crabel on MES.

## State
15 paper ledgers; intraday ledgers cannot trade while 15-min NQ ATR > ~75 pts (stop risk > $150); overnight ledgers unaffected. 2024–25 is spent
for the overnight family (one shot, failed) and has been scored repeatedly by Antigravity for the Arch C / Quad family, so no blind split is left
anywhere: forward paper is the only remaining out-of-sample evidence.

## Recommendation
Stop owned-data search again: calendar_2, sizing_2 and archc_1 were all nulls, and each further round adds multiplicity to the same training split.
Keep: (1) forward paper monitoring with monthly reconciliation vs the training per-night/per-trade distribution; (2) audits of other agents'
proposals (look-ahead, spent splits, funded rules); (3) new data only if it brings a new mechanism (not more of the same bars).

## Do not repeat
Everything in the previous memo, plus: calendar windows (intraday or overnight), stop-risk budgets, Arch C exit/stop/sleeve variants,
VIX-level gates on the intraday sleeves, Crabel cross-contract.

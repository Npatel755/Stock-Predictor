# cl_1: crude oil (CL data, MCL execution) sleeves for the payout book. Training 2010-23 only. REJECTED.

Script `scripts/cl_1_payout_sleeves_train.py` (rules, gates and adopt rule in its docstring, written before any result). Raw:
`CL_1_PAYOUT_SLEEVES_TRAINING.json`. Data: Databento CL.v.0 ohlcv-1m 2010-06..2023-12 ($17.10, `fetch_cl_1m_train.py`); 3,372 days used
(13 degraded, 104 thin/holiday days skipped; no day had a mid-session roll).

## Result
No config of the 24 reached the selection bar on 2010-16 (PF >= 1.10 after costs), so nothing went to the 2017-23 confirmation or the book
test. H1 PF: opening-range breakout 0.70-0.85, EIA report 0.68-1.09 (best: 15-minute momentum held to 14:29, PF 1.088, 32 trades/yr),
into-settlement momentum 0.65-0.76.

## Why (diagnostic run after the verdict; changes nothing)
- Gross P&L per trade before costs is about zero in 22 of 24 configs (-$8 to +$9 per trade at 2.4-5 MCL), and the random-direction mirror is
  about zero too: these setups carry no direction information in crude.
- Costs per trade are $12-25. An MCL round trip costs ~5.9 bp of notional at $85 vs ~0.55 bp for MNQ (the $0.01 tick is large relative to
  crude's price), about 6x more per unit of daily volatility. Short-horizon crude setups on MCL are cost-bound.
- Simulator hand check (synthetic trending day): long rides to the time exit, short stops at its stop on the right bar.
- Not pursued: the mirrored EIA variants that look positive in the diagnostic. They were not pre-declared and choosing them now would be
  selection on seen results.

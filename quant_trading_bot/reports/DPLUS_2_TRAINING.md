# dplus_2 — Architecture D+ without the MNQ 30m trend sleeve (derived; training 2010–23 only)

Protocol: research/dplus_2/PROTOCOL.md (pre-registered before running). Script: scripts/dplus_2_pilot.py → reports/DPLUS_2_TRAINING.json. Fixed engine.

| gate | V1 (3 sleeves) vs B (ag_arch_d_plus) | pass |
|---|---|---|
| ≥ 80 % of net, ≥ 11 positive years | +17,576 vs +20,723 (84.8 %), 12 of 14 | yes |
| marked DD ≤ 0.6 × B, 0 touches of $2k | 882 vs 1,768 (0.50), 0 touches | yes |
| placebo: 200 count-matched random removals (570 trades) | V1's DD lower than **200 of 200** (placebo median 1,495) | yes |
| coherence: dropped sleeve not good in ≥ 10 of 14 years; both halves positive | incremental P&L of the 30m sleeve positive in **10 of 14** years; halves +1,267 / +16,309 | **no** |

Verdict: **fails** on the pre-registered coherence gate — the MNQ 30m trend sleeve is a consistently positive sleeve (+3,147 over 14 years, positive in 10),
so removing it is a net-for-drawdown trade, not the removal of a bad component. V1 is not deployed as a version; it is recorded as the drawdown-first
configuration of D+ (half the marked DD for 15 % less net) to be revisited only if the forward paper record of ag_arch_d_plus shows the 30m sleeve
carrying its losses. Also noted: V1's 2010–16 half is thin (+1,267 over 7 years), so like every intraday candidate on this data its net is 2017–23-heavy.
Nothing changed on paper; 2024–26 not loaded.

## Addendum - scaled deployment (Nick's request, 2026-11-09)

Nick asked whether the lower-drawdown 3-sleeve variant could be used and scaled instead. Scaling is a risk-size decision, not a new
hypothesis: in this engine per-contract P&L and all costs (commission, spread, slippage) are linear in contracts, verified on the fixed
engine for the MES 30m D sleeve (348 trades at 1c and 2c: net 3,932.00 vs 7,864.00, ratio exactly 2.0, every trade sized 2). So the
2-contract variant on training 2010-23 is exactly 2x the table above:

| config | net | trades | closed DD | marked DD | $2k touches | years >0 |
|---|---|---|---|---|---|---|
| ag_arch_d_plus (4 sleeves, 1c) | +20,723 | 1,968 | 1,654 | 1,768 | 0 | 12/14 |
| ag_arch_d_plus_v2 (3 sleeves, 1c) | +17,576 | 1,398 | 783 | 882 | 0 | 12/14 |
| ag_arch_d_plus_v2_2c (3 sleeves, 2c) | +35,152 | 1,398 | 1,566 | 1,765 | 0 | 12/14 |

At 2 contracts the 3-sleeve variant has the same marked drawdown as the 4-sleeve original at 1 contract and 70% more net, so at equal
drawdown it dominates. The coherence failure above still stands (the dropped sleeve is a positive sleeve, not a bad one) and both
variants are one-split (2010-23) evidence derived from an ablation on that split; the forward record decides.

Deployed (simulated only): `ag_arch_d_plus_v2` (1c) as a challenger beside `ag_arch_d_plus`, and `ag_arch_d_plus_v2_2c` in the
Future-strategies section (switch once ~$900 is banked; marked DD 1,765 leaves $235 under a $2k floor from zero). Parity fix in the same
change: all D+ sleeves now set `risk_per_trade=1e9` so the paper runner takes one (or two) contracts regardless of stop risk, which is
what the fixed-engine replication (SIZING_BUDGET=1e9) and Antigravity's 1-contract claims assume; before this the deployed
`ag_arch_d_plus` would have skipped trades whose stop risk exceeded the default $150 budget.

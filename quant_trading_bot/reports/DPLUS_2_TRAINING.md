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

## Addendum - scaled deployment (Nick's request, 2026-11-09; corrected the same evening)

Nick asked whether the lower-drawdown 3-sleeve variant could be used and scaled instead. First a correction: the reported D+ numbers
(this report, dplus_1, the Antigravity replication) were measured with the engine's default stop-risk budget ($150 per contract per
trade; a trade is skipped when one contract's stop risk exceeds it), because those pilots call `run_sleeve` directly. An always-one-
contract version is +18,386 / 1,457 trades / closed DD 1,102 / marked DD 1,280 (59 extra high-ATR trades, +810 net, +45% drawdown) -
so the budgeted version is both what was reported and the better drawdown configuration, and the paper candidates keep the budget. A
2-contract version therefore cannot be "exactly 2x": it uses a $300 budget (two contracts on every v2 trade, one contract on the
higher-ATR trades v2 skips) and the engine's unchanged $300 daily-loss / $1,800 hard-drawdown gates trip more often at double size.
Exact fixed-engine results, training 2010-23 only (scripts/dplus_2_pilot.py, /tmp/dp_2c.py -> reports/DPLUS_2C_TRAINING.json):

| config | net | trades | $/trade | closed DD | marked DD | $2k touches | years >0 |
|---|---|---|---|---|---|---|---|
| ag_arch_d_plus (4 sleeves, 1c) | +20,723 | 1,968 | 10.53 | 1,654 | 1,768 | 0 | 12/14 |
| ag_arch_d_plus_v2 (3 sleeves, 1c) | +17,576 | 1,398 | 12.57 | 783 | 882 | 0 | 12/14 |
| ag_arch_d_plus_v2_2c (3 sleeves, $300 budget) | +27,327 | 1,281 (1,239 at 2c, 42 at 1c) | 21.33 | 1,245 | 1,453 | 0 | 12/14 |

The 2c variant has lower marked drawdown than the 4-sleeve original at 1c (1,453 vs 1,768) with 32% more net, so at equal or lower
drawdown it still dominates - but the gain is +32%, not the +70% a naive doubling suggests, because the daily-loss gate bites at double
size. The dplus_2 coherence failure above still stands and all of this is one-split (2010-23) evidence derived from an ablation on that
split; the forward record decides.

Deployed (simulated only): `ag_arch_d_plus_v2` (1c) as a challenger beside `ag_arch_d_plus`, and `ag_arch_d_plus_v2_2c` in the
Future-strategies section (switch once ~$600 is banked: marked DD 1,453 leaves $547 under a $2k floor from zero).

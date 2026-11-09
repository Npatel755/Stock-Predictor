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

# dplus_2 — derived variant: Architecture D+ without the MNQ 30m trend sleeve (training 2010–23 only; 2024–26 not loaded)

Derived from dplus_1's ablation on the same split: treat as one-split evidence. Variant V1 = Crabel 15m > MNQ 60m trend > MES 30m trend, strict 1c router,
same VIX stand-aside, no parameter changed. Baseline B = ag_arch_d_plus (fixed engine +20,723 / marked DD 1,768).
Gates (all required to deploy V1 as `ag_arch_d_plus_v2` beside, not instead of, ag_arch_d_plus):
1. V1 keeps ≥ 80 % of B's net and ≥ 11 of 14 positive years.
2. V1 marked DD ≤ 0.6 × B's (≤ 1,061) and 0 touches of $2k.
3. Placebo: 200 random removals of the same number of routed trades from B (re-routed is not possible for random subsets, so the removal is applied to the
   routed set) — V1's marked DD must be lower than ≥ 190 of 200.
4. Coherence: the removed sleeve's incremental P&L (B − V1) is not positive in ≥ 10 of 14 years (i.e. it is not a consistently good sleeve being dropped for
   a drawdown artefact); and V1's year-by-year net is positive in both halves (2010–16, 2017–23).

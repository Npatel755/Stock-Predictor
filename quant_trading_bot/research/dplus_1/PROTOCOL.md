# dplus_1 — robustness of the Architecture D+ challenger inside training (2010–23 only; 2024–26 not loaded)

Pre-registered before running. Candidate: `ag_arch_d_plus` exactly as registered (fixed engine: +20,723 / 1,968 trades / closed DD 1,654).
Purpose: decide whether the challenger ledger deserves staging consideration, not to re-tune it. No parameter of the deployed candidate changes.

1. **Sleeve ablation under the strict router**: drop each of the four sleeves in turn; record net, trades, closed DD, positive years.
   Read: a sleeve whose removal *raises* net/DD is dead weight (recorded, not acted on this round).
2. **Marked drawdown** of the router output alone (every stop assumed hit at entry; book_1 convention) and $2k / $2.5k touches.
   Staging gate: marked DD < 2,000 and 0 touches.
3. **Crabel `min_range` plateau** (the only knob new vs Architecture C): standalone Crabel-15m sleeve at min_range ∈ {0, 5, 10, 15, 20, 25} points.
   Gate: the two neighbours (10, 20) each keep ≥ 70 % of the net at 15; otherwise 15 is a spike.
4. **Expanding-window prospective choice** of min_range: for each year Y in 2013–2023 choose the value with the highest net/closed-DD on years < Y and
   apply it to Y. Gate: prospective total ≥ 60 % of the fixed-15 total over 2013–23.
Verdict: all gates pass → ag_arch_d_plus stays a challenger with "staging-eligible" noted; any failure → stays a challenger only, with the failure recorded.

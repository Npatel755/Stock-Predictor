# Antigravity "Grand Champion Architecture D+" and "Book D+" — fixed-engine replication (training 2010–23 only; 2024–26 not loaded)

Script: `scripts/replicate_antigravity_d_plus.py` → `reports/ANTIGRAVITY_D_PLUS_REPLICATION.json`. Runs the candidates exactly as Antigravity registered them in
`ensemble_paper.py` (da1733a) through the paper runner's own `run_sleeve` (the code that would trade on paper), strict 1c router in sleeve order, morning sleeves
blocked after a VIX>VIX3M close, costs = the standard micro friction. Book marks follow book_1 (overnight leg at every 1-minute low, every intraday stop assumed hit).

| item | Antigravity claim | fixed engine | verdict |
|---|---:|---:|---|
| ag_arch_d_plus net / trades / per trade | +20,293 / 1,635 / $12.41 | **+20,723 / 1,968 / $10.53** | net reproduces, trade count does not |
| ag_arch_d_plus closed DD | $936 | **$1,654** | DD does not reproduce (+77 %) |
| ag_arch_d_plus years positive, pre-2020 | 11/14 | 12/14, pre-2020 +6,626, max year 29 % | coherent across years (unlike Arch D) |
| overnight_dip_v2 with VIX gate | +8,877 / 420 nights, DD 1,241 | +8,309 / 422 nights; the 68 skipped nights made **+3,489** | gate removes profitable nights |
| book_d_plus closed net | +29,170 | +29,032 | reproduces |
| book_d_plus marked DD | $1,241, 0 touches | **$2,333 (2023-04-19), 1 touch of $2k** | **fails the $2k floor; worse than Book A's 2,043** |
| book_d_plus with ungated night leg | – | +32,521, marked DD 2,333 (same) | the VIX night gate costs 3,489 and changes DD by $0 |
| book_a with the VIX night gate (control) | – | +24,829, DD 1,964 | the gate's only DD effect is on Book A's 2020 night, and it costs 12 % of net |

Sleeve attribution after the router: Crabel 15m +8,105 (493 trades), MNQ 60m +6,057, MNQ 30m +3,976, MES 30m +2,585.

## Reading
- The intraday engine D+ is Antigravity's first candidate whose **net** reproduces and whose years are coherent (12/14, pre-2020 positive). Its drawdown does not:
  their engine reports $936 where the fixed engine gives $1,654 — the same engine gap seen in Arch C/D audits (their fills/stops are more lenient), so their
  "cushion" and Monte-Carlo breach figures are not usable.
- Book D+ fails the funded floor on marked drawdown ($2,333, one touch), and the piece Antigravity added to "reduce risk" (skipping dip nights after a
  backwardation close) removes 68 nights that earned +$3,489 while leaving the drawdown unchanged — consistent with overnight_4/archc_2: the overnight dip earns
  its money in stress, and VIX gates belong on the morning intraday sleeves, not on the night.
- Selection caveat: D+ parameters (Crabel min_range 15, 3.5R, MES 2.5R/1.25 ATR "H3 peak") were chosen among ≥5 hypotheses on the same 2010–23 split, so the
  training numbers overstate; the fixed-engine DD of $1,654 leaves only $346 under a $2k floor before any marked excursion.

## Decision
- `book_d_plus` is **not** run as a ledger (hidden; definition kept beside the replication note).
- `ag_arch_d_plus` is deployed as a **challenger intraday ledger** (simulated, 1c) so the forward record can judge it against ag_quad_v2 / ag_arch_c_v2 /
  All-Weather 1c; it is not combined with the overnight leg and not staged for the current account.
- Book A / book_a_bond remain the staging candidates.

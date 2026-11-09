# sizing_3 — 2 contracts when prior-close SKEW < its 20-day mean (training 2010–23 only)

Protocol research/sizing_3/PROTOCOL.md; script scripts/sizing_3_pilot.py; raw reports/SIZING_3_TRAINING.json. One variant, one control, no threshold search; 2024–26 not loaded.
Breach = 1-year funded-breach probability at a $2k trailing floor (sizing_1 block-bootstrap, closed daily P&L). Book DD here is on exit-day attribution (1,802) vs 1,633 in portfolio_4 (entry-day); same trades.

| leg | sizing | net | closed DD | +years | max-yr | net/DD | breach 1y |
|---|---|---|---|---|---|---|---|
| overnight v2 | 1c | +11,797 | 1,646 | 12 | 29 % | 7.2 | 0.2 % |
| overnight v2 | 2c SKEW<20d | +21,850 | 2,695 | 12 | 30 % | 8.1 | 9.7 % |
| overnight v2 | control 2c SKEW≥20d | +13,543 | 3,055 | 11 | 28 % | 4.4 | 9.3 % |
| All-Weather 1c | 1c | +16,520 | 1,256 | 8 | 43 % | 13.2 | 0.1 % |
| All-Weather 1c | 2c SKEW<20d | +29,197 | 2,349 | 9 | 45 % | 12.4 | 6.4 % |
| All-Weather 1c | control | +20,363 | 2,764 | 9 | 38 % | 7.4 | 9.1 % |
| book (both) | 1c | +28,317 | 1,802 | 11 | 37 % | 15.7 | 1.2 % |
| book | 2c SKEW<20d | **+51,047** | **2,767** | 11 | 39 % | 18.5 | **17.4 %** |
| book | control | +33,906 | 3,494 | 9 | 34 % | 9.7 | 24.8 % |

## Verdict: hypothesis confirmed in direction, FAILS the $2k-floor gate — not deployed
- The SKEW state does what extstate_2 said: 2c on low-SKEW nights/days adds +$22.7k to the book versus +$5.6k for the control at a smaller DD
  (2,767 vs 3,494), and raises net per unit of drawdown (18.5 vs 15.7 for 1c) — the control lowers it (9.7). So the state carries information, not noise.
- But doubling anything doubles the bad days inside the state too: every 2c variant has closed DD > $2.3k and one-year breach odds 6–17 % at a $2k floor
  (vs ≤ 1.2 % for 1c). Marked DD (book_1 excess ≈ +$410) would be ≈ $3.2k. Gate failed; the 1c book stays the only $2k-floor configuration.
- Staging value (not a deployment): once the locked floor has ≈ $1.5k of banked cushion (effective floor ≥ $3.5k), the SKEW-state 2c book's
  historical worst case fits and its net/DD is the best measured here. Recorded for the staging rule in PORTFOLIO_4/BOOK_1; forward paper first.
- Caveat: two sizing rounds (sizing_1/2) plus this one have now been spent on the same 2010–23 split for the same two legs; no further sizing variants will be tried on this data.

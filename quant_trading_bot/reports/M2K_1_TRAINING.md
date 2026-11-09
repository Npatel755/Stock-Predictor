# m2k_1 — frozen rules transferred to Russell (M2K) and Dow (MYM) micros (training only)

Protocol research/m2k_1/PROTOCOL.md; script scripts/m2k_1_pilot.py; raw reports/M2K_1_TRAINING.json. Data: Databento GLBX ohlcv-1m RTY.c.0 / YM.c.0 (approved, $28.59),
bars >= 2024-01-01 never read. RTY exists on CME only from 2017-07 → M2K spans 2017-07..2023 (7 calendar years), gates applied proportionally as declared in the protocol.
Micro economics: M2K $0.50/tick (0.10), $5/pt; MYM $0.50/tick (1.0), $0.50/pt; 2-tick spread, 1 tick slip/side, $0.61/side.

| cell | net | n | $/unit | +years | max-yr | DD | 2010–19 | placebos beaten | pass |
|---|---|---|---|---|---|---|---|---|---|
| M2K T1 own reopen dip, 18:05→09:45 | +331 | 295 | 1.1 | 4/7 | >100 % | 1,523 | +1,198 | 115/200 | no |
| M2K T2 co-dip with MES (v2 form) | +1,624 | 191 | 8.5 | 5/7 | 45 % | 1,061 | +1,036 | **200/200** | no |
| M2K T3 All-Weather v2 1c sleeves | −3,716 | 777 | −4.8 | 1/7 | – | 3,834 | −883 | – | no |
| MYM T1 own dip | +558 | 606 | 0.9 | 7/14 | 97 % | 1,982 | +1,674 | 135/200 | no |
| MYM T2 co-dip with MES | +1,163 | 454 | 2.6 | 8/14 | 69 % | 1,657 | +1,969 | 185/200 | no |
| MYM T3 All-Weather v2 1c sleeves | −2,440 | 1,283 | −1.9 | 5/14 | – | 3,481 | −820 | – | no |
T4 (books) not run: no T2 passer. Reference: MNQ overnight_dip_v2 +11,797 / 490 nights / $24 per night / DD 1,646.

## Verdict: 0 of 6 — nothing deployed
- The reopen-dip premium is an index-wide phenomenon (M2K co-dip beats every placebo), but the dollar edge scales down with the contract faster than the risk does:
  M2K earns a third of MNQ's per-night at a third of the notional, with a worst night (−$363) that is more than half of MNQ's (−$666). Cheaper contracts do not buy drawdown relief.
- MYM's dip is marginal ($2.6/night, under a 2-tick cost) — the Dow's 18:00→09:45 recovery is smaller and less consistent (8/14 years).
- The All-Weather breakout/trend sleeves lose on both: with crabel_1 (Crabel fails on MES) and archc_3/4, the intraday MNQ rules are NQ-specific momentum, not index momentum.
- Lever status: instrument substitution is closed; the remaining drawdown lever is cushion staging (portfolio_4 / book_1 / sizing_3).

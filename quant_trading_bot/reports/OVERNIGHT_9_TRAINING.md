# overnight_9 — intrabar protective stops / late gap-fill exit for overnight_dip_v2 (training 2010–23 only)

Protocol research/overnight_9/PROTOCOL.md; script scripts/overnight_9_pilot.py; raw reports/OVERNIGHT_9_TRAINING.json. Same 490 dip nights as v2; 1-min MNQ path; 2024–26 not loaded.

| exit rule | net | $/night | +years | max-yr | closed DD | marked DD | worst night | nights hit |
|---|---|---|---|---|---|---|---|---|
| v2 (09:45, no stop) | +11,797 | 24.1 | 12 | 29 % | 1,646 | 1,751 | −666 | – |
| stop 1.0 × gap-σ | +5,457 | 11.1 | 8 | 63 % | 911 | 1,104 | −171 | 318 (65 %) |
| stop 1.5 × gap-σ | +6,883 | 14.1 | 10 | 53 % | 1,087 | 1,549 | −241 | 254 (52 %) |
| stop 2.0 × gap-σ | +7,520 | 15.4 | 10 | 46 % | 1,183 | 1,491 | −310 | 207 (42 %) |
| gap-fill exit after 08:30 | +1,518 | 3.1 | 7 | 87 % | 2,191 | 2,361 | −666 | 263 |

## Verdict: 0 of 4 pass — v2 unchanged; overnight exit management closed
- Dip nights are volatile by construction (the signal is a ≥ 0.5σ reopen gap), so even a 2σ stop is touched on 42 % of nights and the stopped nights
  are, on average, nights that recovered by 09:45: every stop lowers net per unit of drawdown (v2 6.7 → 5.0 at best).
- Selling at the gap fill after 08:30 gives up the overshoot that *is* the premium (overnight_3 E5 found the same for any-time fills).
- Together with overnight_3 (exit times), overnight_4 (intrabar DD), overnight_8 (entry time) this closes the exit/entry-timing dimension for the family.
  The drawdown of the overnight leg is a property of the mechanism, not of exit management; cushion staging (portfolio_4/book_1/sizing_3) is the lever.

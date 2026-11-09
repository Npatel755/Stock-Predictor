# quad_2 — backwardation stand-aside for the Quad's MORNING sleeves only (pre-registered 2026-11-09; training 2010-2023; 2024-26 sealed)

From crabel_1: the Quad's morning 30m trend lb16 and 60m trend lb12 lose on days after a VIX > VIX3M close; its afternoon 30m trend lb8 gains (+$28/trade) on them.
One variant: ag_quad (strict 1-contract router: morning lb16 > 60m lb12 > afternoon lb8 > MES 30m lb8) with the two morning MNQ sleeves masked on
backwardation days; afternoon and MES sleeves unchanged. Engine default costs; trade-level router as in the Architecture C replication.
Gates: net > champion, closed DD <= champion DD, positive years >= champion, removed-trade days' net below the 5th percentile of 20 same-count random-day sets.
One trial. If it passes (or nearly, at Devin's discretion) deploy as `ag_quad_v2` beside ag_quad. 2024-26 never scored.

# portfolio_3 — ag_quad_v2 + overnight_dip_v2 as one 1-contract account (pre-registered 2026-11-09; training 2010-2023; 2024-26 sealed)

Same design as portfolio_1 with the filtered Quad (quad_2 V1) in place of Architecture C: daily P&L sum (overnight booked on its exit day), monthly correlation,
combined closed DD, worst day, overlap check (overnight exits 09:45; Quad's earliest fill 10:00 for morning sleeves — MES/afternoon sleeves also start >= 10:00),
block-bootstrap MC (mean block 10 days, 3,000 paths x 1 yr) P(DD >= $2k) and P(DD >= $3k), annual net p5/p50/p95; same excluding 2020-22.
Decision: "one $2k-floor account" if combined DD < $2,000 and P(DD >= $2k, 1 yr) <= 10 %; otherwise report the cushion at which P(breach) <= 5 %. Nothing deployed; no validation scoring.

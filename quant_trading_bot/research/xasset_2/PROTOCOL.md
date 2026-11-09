# xasset_2 — cross-asset day state as a conditioner for overnight_dip_v2 (pre-registered 2026-11-09, training 2010–23 only)

Data already owned (xasset_1 purchase): GLBX ohlcv-1m ZN.c.0 (10-yr note), CL.c.0 (crude), 6E.c.0 (euro). Only bars before 2024-01-01 are read.
Decision time 18:05 ET. Features known by then, per asset: D = asset's regular-day return (16:00 ET close vs prior day's 16:00 close; ZN 16:00 is the futures
settlement area), and R = asset's reopen move (18:00 open → 18:04 close). States: D>0 / D<0 ("bonds up" = growth-scare dip; "bonds down" = rates-driven dip;
"oil down", "euro down" = risk-off / USD bid), R>0 / R<0.
Target: the 490 overnight_dip_v2 nights (MNQ 18:05 → 09:45). 3 assets × 2 features × 2 states = 12 cells; nothing else will be tried.
Decision rule (as extstate_2): a state is adoptable as a stand-aside only if its nights are net negative, that removal is worse than ≥ 190/200 same-count random
removals, and the remaining nights still pass the overnight gates (≥ 11/14 years, max-year ≤ 40 %, DD < 2k, ≥ 100 nights). Informational otherwise.
2024–26 not loaded. Deploy only at Devin's discretion as a new version beside v2.

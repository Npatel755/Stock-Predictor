# risk_1 — pause rules for Book A (pre-registered 2026-11-09, training 2010–23 only)

Target: book_1 found Book A (overnight_dip_v2 + ag_all_weather_v2_1c) touches a $2,043 intraday-trailing drawdown once (Mar 2020) vs a $2,000 floor.
Question: does a simple, mechanical pause on the overnight leg (the leg without stops) bring the marked DD under $2,000 while keeping ≥ 90 % of the net?
Rules (overnight leg only; intraday leg unchanged, it has stops and a flatten):
 R1 skip overnight entries for the rest of the trading week (Sun 18:00 → Fri 16:00) once the book's realized week P&L ≤ −$750.
 R2 same with −$1,000.   R3 skip the next overnight night after 3 consecutive losing nights (reset after the skipped night).
Metrics: closed net, intraday-trailing (marked) DD and when, $2k/$2.5k breach episodes (book_1 method), nights skipped, net retained.
Pass: marked DD < 2,000 AND net ≥ 90 % of Book A's. Three cells, no search. 2024–26 not loaded. Deploy only at Devin's discretion as a new book version.

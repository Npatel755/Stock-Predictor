# portfolio_3 — ag_quad_v2 + overnight_dip_v2 as one 1-contract account (training 2010–2023; 2024–26 sealed)

Protocol: research/portfolio_3/PROTOCOL.md. Script: scripts/portfolio_3_pilot.py. Raw: reports/PORTFOLIO_3_TRAINING.json. Engine default costs for both legs.

| year | overnight v2 | Quad v2 | combined |
|---|---:|---:|---:|
| 2010 | −36 | −253 | −289 |
| 2011 | 123 | 239 | 362 |
| 2012 | 40 | 303 | 343 |
| 2013 | 377 | −870 | −493 |
| 2014 | 384 | 357 | 741 |
| 2015 | 695 | 1,143 | 1,837 |
| 2016 | 554 | 51 | 605 |
| 2017 | −263 | 191 | −72 |
| 2018 | 1,605 | 3,677 | 5,282 |
| 2019 | 1,489 | 440 | 1,929 |
| 2020 | 1,144 | 2,669 | 3,814 |
| 2021 | 1,507 | 4,484 | 5,992 |
| 2022 | 3,453 | 5,285 | 8,738 |
| 2023 | 724 | −8 | 716 |
| **total** | **11,797** | **17,707** | **29,505** |

- Monthly correlation 0.06; overlap violations 0; worst combined day −$764 (2020-03-16).
- Closed DD: overnight $1,646, Quad v2 $2,048, **combined $2,396** → fails the "one $2k-floor account" rule (as portfolio_1 did).
- Block-bootstrap MC, 1 yr: P(DD ≥ $2k) 3.5 %, P(DD ≥ $3k) 0.2 %, annual net p5/p50/p95 −$372 / +$1,873 / +$5,293; excluding 2020–22: 2.6 % / 0.1 %, median +$896.
- Staging (as in portfolio_1): run one leg until ≈$3k of cushion is banked above the locked floor, then both; pause the second leg after payouts. Nothing deployed; 2024–26 untouched.

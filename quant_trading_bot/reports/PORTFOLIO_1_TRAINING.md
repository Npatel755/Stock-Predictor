# portfolio_1 — overnight_dip_v2 + ag_arch_c as one 1-contract account (training 2010–2023; no parameter changes; 2024–26 sealed)

Protocol: research/portfolio_1/PROTOCOL.md. Script: scripts/portfolio_1_pilot.py. Raw: reports/PORTFOLIO_1_TRAINING.json. Engine default costs for both legs.

| year | overnight v2 | Architecture C | combined |
|---|---:|---:|---:|
| 2010 | −36 | −261 | −297 |
| 2011 | 123 | −200 | −77 |
| 2012 | 91 | 18 | 109 |
| 2013 | 327 | −604 | −277 |
| 2014 | 384 | 657 | 1,041 |
| 2015 | 695 | 719 | 1,414 |
| 2016 | 554 | 267 | 821 |
| 2017 | −263 | 906 | 643 |
| 2018 | 1,605 | 2,699 | 4,304 |
| 2019 | 1,489 | 849 | 2,338 |
| 2020 | 1,144 | 807 | 1,951 |
| 2021 | 1,507 | 6,741 | 8,248 |
| 2022 | 3,453 | 3,389 | 6,842 |
| 2023 | 724 | 84 | 808 |
| **total** | **11,797** | **16,070** | **27,867** |

- Monthly P&L correlation −0.01; years both negative: 1 (2010); overlap violations (overnight still open at an intraday fill): 0.
- Closed DD: overnight $1,646, Architecture C $1,596, **combined $2,315** (both legs lose in March 2020; worst combined day −$1,146 on 2020-03-16).
- Block-bootstrap MC (5,000 paths): combined 1 yr P(DD ≥ $2k) 6.2 % closed / 7.0 % intrabar, annual net p5/p50/p95 −$443 / +$1,722 / +$5,315; 2 yr 13.1 % / 14.9 %, median +$3,777.
  Excluding 2020–22: 1.5 % / 1.8 %, median +$877. Alone: Architecture C 1.1 %, overnight 0.4–0.7 %.
- Decision rule (DD < $2k and P(breach, 1 yr) ≤ 10 % and corr ≤ 0.3): **fails on DD** → not qualified to run as one $2k-floor account. Diversification is real
  (returns add, risks mostly don't) but the one shared stress episode is exactly where a $2k floor is tested.
- Not pre-registered, so recorded as ideas only: a $3k floor would hold the combination; or skip the overnight leg while the intraday leg is >$1k down over the trailing 5 days.

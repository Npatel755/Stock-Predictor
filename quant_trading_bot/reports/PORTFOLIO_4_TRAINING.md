# portfolio_4 — ag_all_weather_v2_1c + overnight_dip_v2 as one 1-contract account, training 2010–23 (2026-11-09): QUALIFIES

Protocol: research/portfolio_4/PROTOCOL.md (same method as portfolio_3). Script: scripts/portfolio_4_pilot.py. Both legs frozen as deployed on
paper; nothing chosen here. 2024–26 not loaded.

| | overnight_dip_v2 | ag_all_weather_v2_1c | combined |
|---|---|---|---|
| net 2010–23 | +11,797 | +16,520 | +28,317 |
| closed drawdown | 1,646 | 1,256 | **1,633** |
| 1-year P(DD ≥ 2,000) / ≥ 3,000 | 0.2 % / 0 | 0.2 % / 0 | **1.9 % / 0.1 %** |
| 1-year net p5 / p50 / p95 | −496 / 678 / 2,647 | −530 / 1,020 / 3,405 | −327 / 1,816 / 5,217 |
| monthly correlation | | | 0.09 |
| overlapping fills (intraday entry while the night position is open) | | | 0 |
| worst day | | | −666 (2020-03-16) |

Per year (overnight / AW 1c / total): 2010 −36/−118/−154 · 2011 123/209/332 · 2012 40/−56/−16 · 2013 377/−510/−133 · 2014 384/787/1,171 ·
2015 695/740/1,435 · 2016 554/−168/386 · 2017 −263/−57/−320 · 2018 1,605/2,069/3,674 · 2019 1,489/−22/1,468 · 2020 1,144/1,115/2,259 ·
2021 1,507/4,836/6,343 · 2022 3,453/7,021/10,474 · 2023 724/675/1,399. Positive years 10 of 14; 2022 = 37 % of the total; 2010–13 ≈ flat.

## Reading
- First combination that fits a $2,000 floor on training: the combined closed DD (1,633) is *below* the overnight leg's own (1,646) because the
  All-Weather leg was flat-to-up during the overnight leg's worst stretch, and the March-2020 co-loss that sank the Arch C / Quad books is
  smaller here (worst day −666 vs −1,146). 1-year breach odds 1.9 % at $2k (vs 6–7 % for Arch C, 3.5 % for Quad v2 books).
- Excluding 2020–22 the book makes ≈ $820 a median year with P(DD ≥ 2k) 0.4 % — the honest expectation for a normal year; the 2021–22 numbers are
  the trend regime and should not be budgeted.
- The intraday leg is the always-one-contract All-Weather, i.e. it takes the $150–250-stop-risk trades the other ledgers skip; at today's ATR
  (stop risk $425+) it still trades nothing, so the book's forward P&L for now is the overnight leg alone.
- No deployment: both legs already run on paper and never hold at the same time, so the book's forward P&L is the sum of the two ledgers
  (`overnight_dip_v2` + `ag_all_weather_v2_1c`). Staging rule from portfolio_1/3 is not needed for this pair; it still applies if a second intraday
  leg (Quad v2 / Arch C v2) is added, which pushes DD over $2k.

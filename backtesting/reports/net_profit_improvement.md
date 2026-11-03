# Historical net-profit improvement search

2026 now explicitly participates in model selection at user request. All years are inspected/reused. This objective is historical P&L, not independent validation or future profitability. Risk remains $100; costs and account size cannot be optimized away.

Compared 64 fixed configurations at the same costs and $100 risk. Selected **channel96_ema150_stop1.5_rr4.5_trail3.0**. Historical gate passed: **True**.

| Same continuous UTC period: 2023-01-01 to 2026-10-28 exclusive | Net P&L | Entries | Intrabar drawdown |
| --- | ---: | ---: | ---: |
| v1_2 | $4,344.93 | 147 | 2.99% |
| v1_3 | $4,075.01 | 494 | 3.94% |
| selected | $6,034.44 | 465 | 4.92% |
| selected at 4bp extra slippage | $4,721.92 | 465 | 5.16% |

Improvement above the previous saved-profit benchmark: **$1,689.51**.

| Additional reused-data check, independent accounts | Net P&L |
| --- | ---: |
| 2025_h1 | $1,313.60 |
| 2025_h2 | $1,564.35 |
| 2026_selected_period | $-284.04 |
| earlier_2020_2022 | $4,365.59 |

The 2026 result is selection-period performance, not an independent audit. Half-year and earlier-period accounts reset position/cash state; they do not sum to the continuous replay. All failures and all candidates remain in checkpoints. No candle fabrication, fee reduction, larger account or risk increase is used to cross the benchmark. Missing later days remain excluded. This historical optimization does not establish a durable future edge.

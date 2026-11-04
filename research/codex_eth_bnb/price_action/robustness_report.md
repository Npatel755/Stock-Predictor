# Predeclared price-action robustness

| Asset | Frozen rule | Diagnostic | Trades/week | Net | Intrabar bound |
| --- | --- | --- | ---: | ---: | ---: |
| ETH | failed_breakout_1h_R3 | delay | 3.64 | $-2,299 | 5.5% |
| ETH | failed_breakout_1h_R3 | capacity | 3.66 | $-1,138 | 4.8% |
| ETH | failed_breakout_1h_R3 | crisis | 3.66 | $-6,472 | 13.5% |
| ETH | failed_breakout_1h_R3 | risk_100 | 3.66 | $-4,909 | 17.7% |
| ETH | failed_breakout_1h_R3 | long_only | 1.88 | $-699 | 2.2% |
| ETH | failed_breakout_1h_R3 | short_only | 1.78 | $-413 | 3.4% |
| ETH | failed_breakout_1h_R3 | lag48h | 2.50 | $-1,212 | 3.8% |
| ETH | failed_breakout_1h_R3 | opposite_target | 3.66 | $-24 | 3.9% |
| BNB | failed_breakout_1h_R3 | transfer_from_ETH | 4.45 | $-4,385 | 10.7% |
| BNB | sweep_reclaim_1h_R3 | delay | 2.74 | $-2,818 | 7.2% |
| BNB | sweep_reclaim_1h_R3 | capacity | 2.84 | $539 | 3.2% |
| BNB | sweep_reclaim_1h_R3 | crisis | 2.85 | $-7,174 | 15.0% |
| BNB | sweep_reclaim_1h_R3 | risk_100 | 2.84 | $1,536 | 13.3% |
| BNB | sweep_reclaim_1h_R3 | long_only | 1.56 | $361 | 3.0% |
| BNB | sweep_reclaim_1h_R3 | short_only | 1.29 | $-2,125 | 4.2% |
| BNB | sweep_reclaim_1h_R3 | lag48h | 1.64 | $-1,534 | 4.9% |
| BNB | sweep_reclaim_1h_R3 | opposite_target | 2.85 | $-3,264 | 7.1% |
| ETH | sweep_reclaim_1h_R3 | transfer_from_BNB | 2.87 | $-2,052 | 6.1% |

Diagnostics never replace failed validation candidates. Alternative target was already in the frozen grid. Transfer uses jointly inspected assets and is not independent evidence.

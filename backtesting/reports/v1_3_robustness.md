# v1.3 post-selection robustness

Diagnostics only, on reused history. No rule selection or profile overwrite. Closed-leg concentration omits marked open P&L and is not a strategy replay.

| Check | Net P&L | Entries | Running-peak drawdown | Closed net without three largest winners |
| --- | ---: | ---: | ---: | ---: |
| 2025_slip2.0 | $2,129.00 | 136 | 2.10% | $1,268.05 |
| 2025_slip4.0 | $1,879.34 | 136 | 2.11% | $1,029.34 |
| 2025_slip8.0 | $1,406.11 | 136 | 2.14% | $577.49 |
| 2026_slip2.0 | $-1,077.22 | 110 | 4.34% | $-1,928.61 |
| 2026_slip4.0 | $-1,275.59 | 110 | 4.53% | $-2,114.20 |
| 2026_slip8.0 | $-1,645.57 | 110 | 4.89% | $-2,459.30 |
| development_selected | $9,606.70 | 811 | 3.16% | $8,725.96 |
| development_lookback64 | $11,147.66 | 893 | 3.49% | $10,266.92 |
| development_lookback96 | $9,692.50 | 734 | 2.28% | $8,811.76 |
| development_stop_atr1.6 | $8,730.79 | 914 | 3.98% | $7,855.13 |
| development_stop_atr2.4 | $7,142.38 | 765 | 3.26% | $6,264.92 |
| development_trail_atr2.4 | $7,667.52 | 863 | 2.76% | $6,788.60 |
| development_trail_atr3.6 | $7,984.08 | 793 | 3.22% | $7,103.34 |

The 2026 audit is already inspected. Neighborhood checks use development history only and cannot replace the frozen rule. A negative 2026 result remains a material failure even if training neighborhoods and 2025 slippage tests are positive. Removing winners is diagnostic subtraction, not a simulated deployable strategy. No future paper observations, actual Breakout fills or TradingView export reconciliation are included.

# Filtered-candidate reproduction and stress checks

Fresh computation on inspected data, not independent market validation. No reselection or saved-version edits. Conditional uncertainty ignores candidate-search bias.

Fresh same-period replay: saved v1.4 **$6,034.44**, filtered candidate **$9,971.43**; improvement **$3,936.99**. Event-reconstructed equity matches both broker endpoints.

| Post-selection check | Net P&L | Entries | Intrabar drawdown |
| --- | ---: | ---: | ---: |
| full_slippage_2.0 | $9,971.43 | 397 | 4.02% |
| full_slippage_4.0 | $8,735.76 | 397 | 4.11% |
| full_slippage_8.0 | $6,468.48 | 397 | 4.28% |
| 2026_H1_slip2.0 | $-240.43 | 58 | 4.75% |
| 2026_H1_slip4.0 | $-374.10 | 58 | 4.78% |
| 2026_H2_to_Oct27_slip2.0 | $822.98 | 30 | 1.87% |
| 2026_H2_to_Oct27_slip4.0 | $713.25 | 30 | 1.87% |
| development_RVOL1.8 | $8,389.71 | 322 | 3.03% |
| development_RVOL2.2 | $9,546.39 | 301 | 2.63% |

| Continuous selected account calendar-year marked P&L | Net P&L |
| --- | ---: |
| 2023 | $1,018.59 |
| 2024 | $4,110.35 |
| 2025 | $4,259.95 |
| 2026 | $582.55 |

Conditional paired seven-day-block interval for net improvement: **$1,589.98 to $6,024.38**. This does not account for searching 638 configuration slots and is not a future-profit probability.

Closed net after mechanically removing the three largest winning legs: **$8,687.46**. This is diagnostic subtraction, not a re-simulated trade-selection strategy.

Half-year checks start independent accounts with causal indicator warm-up and do not sum to continuous P&L. Positive annual totals can hide losing halves. Neighborhood checks use development history and never choose a new rule. All of 2023-2026 has been inspected/used for selection, including 2026. Exact TradingView/Breakout fills, Pine compilation and future paper observations remain absent. Saved v1.4 files and all earlier failures are unchanged.

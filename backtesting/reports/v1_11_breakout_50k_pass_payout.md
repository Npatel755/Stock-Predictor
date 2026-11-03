# ETH v1.11: Breakout $50k Classic, 90/10 historical account replay

Period: January 1, 2023 to October 28, 2026 exclusive. Current rules applied retrospectively; this does not claim these plans existed throughout the period.

Assumed Classic plan: $5,000 target, $47,000 static equity floor, 3% daily loss from balance at 00:30 UTC. Minimum trader payout $50 after the 90% split. Other Breakout plans have different targets/floors.

Each row tests a new account at each calendar-month start with a COMPLETE observation horizon. No timeout is imposed by the firm: unfinished below means this research horizon ended. Median days to pass includes successful starts only.

| Planned risk | Horizon | Starts | Passed eval | Eval breached | Still in eval | Passed AND later paid | Median days to pass | Median trader payout, all starts |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| $100 | 90 days | 43 | 0 (0.0%) | 0 | 43 | 0 (0.0%) | - | $0.00 |
| $100 | 180 days | 41 | 0 (0.0%) | 0 | 41 | 0 (0.0%) | - | $0.00 |
| $100 | 365 days | 34 | 10 (29.4%) | 0 | 24 | 8 (23.5%) | 248 | $0.00 |
| $100 | 730 days | 22 | 21 (95.5%) | 0 | 1 | 20 (90.9%) | 463 | $3,032.69 |
| $150 | 90 days | 43 | 0 (0.0%) | 0 | 43 | 0 (0.0%) | - | $0.00 |
| $150 | 180 days | 41 | 7 (17.1%) | 0 | 34 | 5 (12.2%) | 148 | $0.00 |
| $150 | 365 days | 34 | 25 (73.5%) | 0 | 9 | 23 (67.6%) | 248 | $797.87 |
| $150 | 730 days | 22 | 22 (100.0%) | 0 | 0 | 22 (100.0%) | 323 | $6,582.37 |

## Starting already funded (no evaluation)

| Risk | Horizon | Starts | At least one payout | Funded breaches | Median payout count | Median total trader payout |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| $100 | 90 days | 43 | 39 (90.7%) | 0 | 4 | $1,000.66 |
| $100 | 180 days | 41 | 40 (97.6%) | 0 | 7 | $1,689.83 |
| $100 | 365 days | 34 | 34 (100.0%) | 0 | 16.5 | $3,705.75 |
| $100 | 730 days | 22 | 22 (100.0%) | 0 | 29.5 | $7,604.50 |
| $150 | 90 days | 43 | 39 (90.7%) | 0 | 5 | $1,500.93 |
| $150 | 180 days | 41 | 40 (97.6%) | 0 | 7 | $2,534.85 |
| $150 | 365 days | 34 | 34 (100.0%) | 0 | 16.5 | $5,559.24 |
| $150 | 730 days | 22 | 22 (100.0%) | 0 | 29.5 | $11,407.48 |

## Assumptions and limits

- Fixed historical trade paths and dollar risk; not a per-start strategy rerun.
- Promotion checked at flat closes only; actual equity-target promotion can occur earlier intratrade.
- Fresh $50k funded balance from next bar after promotion; evaluation profit is not paid.
- Withdraw all eligible gross profit at every flat checkpoint; gross debit includes firm share.
- Intrabar modeled lows checked before flat pass/payout; exact ticks are unavailable.
- At account starts, wait until inherited historical position is flat.
- Same $300 personal strategy daily gate in both risk scenarios.
- No KYC/activation delay; evaluation fees, taxes, network charges excluded.
- Monthly starts overlap, are correlated, and use already selected historical data.
- Observed frequencies are not estimates of independent future success probabilities.

Execution: next-open entries; 4bp fee each side; two ticks plus 2bp adverse market/stop slippage; 3.3bp/day financing. All historical data participated in strategy selection. No strategy parameters were optimized here. Frozen profiles and future validation window remain unchanged.

## Rules checked November 3, 2026

- https://www.breakoutprop.com/program-rules/
- https://intercom.help/breakoutprop/en/articles/11647189-what-is-the-maximum-daily-loss-in-a-funded-account
- https://intercom.help/breakoutprop/en/articles/11647224-when-can-i-request-a-payout-from-my-funded-account
- https://intercom.help/breakoutprop/en/articles/11647212-do-payouts-affect-my-maximum-daily-loss-limit

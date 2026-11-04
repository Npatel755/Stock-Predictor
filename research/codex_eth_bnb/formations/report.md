# Technical formations: activity and robustness

**No qualifying strategy found.**

72 primary hypotheses and12 baselines on ETH/BNB.15m,30m,1h; two predeclared pivot-recognition settings. One successful entry per distinct formation. No stopped-out reentries are counted as new setups. Partial exit legs are excluded from activity counts.

TRAIN: three chronological internal forward folds(2022,2023,2024H1). VALIDATION: July7,2024–August28,2025. Both are already inspected development data. FINAL: contaminated, NOT evaluated. PAPER: no new prospective observations.

## Frozen VALIDATION shortlist

| Asset | Formation | Horizon | Trades/week | Median/week | Weeks with2+ | Trades | Net | Adverse net | Intrabar bound | Accepted |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| ETH | triangle | 30m | 2.97 | 3 | 78.0% | 177 | $-8 | $-3,044 | 2.6% | False |
| ETH | rectangle | 15m | 5.87 | 6 | 94.9% | 350 | $-1,062 | $-5,840 | 3.2% | False |
| ETH | head_shoulders | 15m | 3.74 | 4 | 93.2% | 223 | $-3,332 | $-6,903 | 7.8% | False |
| BNB | pattern_mix | 1h | 3.14 | 3 | 86.4% | 187 | $197 | $-1,920 | 2.5% | False |
| BNB | double_top_bottom | 30m | 2.89 | 3 | 76.3% | 172 | $-1,769 | $-3,381 | 4.9% | False |
| BNB | head_shoulders | 15m | 3.57 | 3 | 93.2% | 213 | $-1,681 | $-3,127 | 3.4% | False |

Frequency target requires>=2entries/week on average AND>=50%of complete weeks with2+trades in EVERY training fold and validation. A high annual average alone is insufficient. Zero-trade weeks remain in weekly_activity.csv.

## Why candidates failed

- ETH `triangle_30m_responsive`: training_performance, positive_base, positive_adverse, block_lower_positive, cumulative_holm.
- ETH `rectangle_15m_selective`: training_performance, positive_base, positive_adverse, block_lower_positive, cumulative_holm.
- ETH `head_shoulders_15m_responsive`: training_performance, positive_base, positive_adverse, block_lower_positive, cumulative_holm.
- BNB `pattern_mix_1h_selective`: training_performance, positive_adverse, block_lower_positive, cumulative_holm.
- BNB `double_top_bottom_30m_selective`: training_performance, positive_base, positive_adverse, block_lower_positive, cumulative_holm.
- BNB `head_shoulders_15m_responsive`: training_performance, positive_base, positive_adverse, block_lower_positive, cumulative_holm.

## Head-and-shoulders across ALL TRAIN configurations

| Asset | Horizon | Recognition | Average trades/week | Minimum multi-trade-week fraction | Positive folds | Sum of reset-fold net |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| ETH | 15m | responsive | 3.67 | 88.0% | 0/3 | $-11,675 |
| ETH | 15m | selective | 1.44 | 28.0% | 0/3 | $-4,546 |
| ETH | 30m | responsive | 1.76 | 50.0% | 1/3 | $-2,008 |
| ETH | 30m | selective | 0.75 | 11.5% | 1/3 | $-1,511 |
| ETH | 1h | responsive | 0.97 | 15.4% | 0/3 | $-1,801 |
| ETH | 1h | selective | 0.35 | 3.8% | 1/3 | $-838 |
| BNB | 15m | responsive | 3.68 | 84.0% | 1/3 | $-2,832 |
| BNB | 15m | selective | 1.29 | 28.0% | 0/3 | $-918 |
| BNB | 30m | responsive | 1.91 | 51.9% | 0/3 | $-2,154 |
| BNB | 30m | selective | 0.67 | 9.8% | 1/3 | $-170 |
| BNB | 1h | responsive | 0.95 | 17.6% | 0/3 | $-1,880 |
| BNB | 1h | selective | 0.34 | 2.0% | 1/3 | $-900 |

## Method and limits

H&S uses three confirmed extrema with the head beyond similar shoulders; intervening extrema define a sloped neckline. A close must cross that neckline AFTER right-shoulder confirmation. Inverse H&S mirrors the rule. Detectors never mark a trade at the historical pivot timestamp. Synthetic examples and prefix/future-poisoning tests check this delay.

The first validation example is charted regardless of subsequent profit: [ETH H&S example](eth_head_shoulders_example.png), [BNB H&S example](bnb_head_shoulders_example.png). Orange hollow markers show when pivots became known. Pattern examples illustrate the exact algorithm; they do not validate predictive power. [Validation comparison](validation_comparison.png).

Targets are projected pattern height; stops lie beyond the shoulder/opposite boundary with a0.25ATR buffer and minimum1ATR. Fixed ATR brackets are tested separately. Flags require an impulse and a bounded8-bar pullback, triangles need three confirmed contacts per side, and rectangles two per side. Numeric tolerances are research definitions, not universal visual-pattern labels.

Primary fractional risk0.25%, maximum1x entry notional, next-open fills,5bp/side fee,2bp/side slippage,1bp spread, observed signed funding. Adverse scenario7bp fees/8bp slippage/4bp spread. Previous-bar volume caps participation0.1%; partial exits retain risk. Fixed historical filters, mark-price funding/liquidation and order-book depth remain approximations. Larger frequency can amplify costs and need not improve profitability.

Cumulative Holm uses208 slots(previous124 + new84);4,999circular7-day blocks, seed20261104. It cannot erase the inherited ETH/BNB/Devin adaptive testing. These are retrospective diagnostics, not independent future success probabilities.

## Artifacts and reproduction

`python -m research.codex_eth_bnb.formations.run` from the dedicated worktree. Exact hypotheses, data/dependency hashes and code identities are frozen in manifest.json before performance evaluation. Checkpoints and full trades/equity/weekly activity/calendar attribution live under outputs/. Registry is append-only. strategy_comparison.csv contains every success/failure; walkforward_results.csv retains each fold. validation_shortlist.json freezes choices before validation; diagnostic_configurations.json records explicit rejection/acceptance.

The original frozen core and Devin’s checkout are not modified. No exchange keys, orders, integration, schedulers or automatic promotion are added.

Sources: [Fidelity pattern definitions](https://www.fidelity.com/bin-public/060_www_fidelity_com/documents/learning-center/Idenitfying-Chart-Patterns.pdf), [CME continuation patterns](https://www.cmegroup.com/education/courses/technical-analysis/trend-and-continuation-patterns), [Lo/Mamaysky/Wang](https://www.nber.org/papers/w7613). Those sources motivate geometry; they do not demonstrate an intraday crypto edge.

## Verified execution and cost attribution

76 tests passed. All 316 replay ledgers reconciled independently; no final-period performance access. Frozen formation code and the earlier study code remain unchanged.

[Explicit cost ledger](cost_attribution.csv) separates fees and signed funding from net P&L. Its pre-fee column still includes spread/slippage in fill prices; it is not a frictionless backtest.

None of the72primary variants met BOTH the training activity and performance gates. Some infrequent rules had positive folds, but did not satisfy the requested weekly activity. No new validation rule was substituted after observing failure.

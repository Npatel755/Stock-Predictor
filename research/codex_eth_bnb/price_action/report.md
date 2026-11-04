# Intraday price-action research round

**No qualifying strategy found.**

64 primary variants plus8 baselines, ETH/BNB,15m/1h,1.5R/3R targets. All choices frozen before validation. One successful entry per setup; no repeated stopped-out reentries.

TRAIN: three chronological internal forward folds(2022,2023,2024H1). VALIDATION:July7,2024–August28,2025. All are already inspected historical development data. FINAL:contaminated,not evaluated. PAPER:no new prospective observations.

| Asset | Rule | TF | Target | Trades/week | Weeks with2+ | Net per$50k | Adverse net | Intrabar bound | Accepted |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| ETH | failed_breakout | 1h | 3R | 3.66 | 89.8% | $-1,106 | $-3,398 | 4.8% | False |
| ETH | imbalance_retest | 1h | 3R | 3.74 | 91.5% | $-3,075 | $-5,294 | 11.2% | False |
| ETH | vwap_trend_pullback | 1h | 1.5R | 4.50 | 96.6% | $-2,097 | $-5,365 | 8.2% | False |
| ETH | shock_reversal | 1h | 3R | 0.62 | 11.9% | $-1,512 | $-1,749 | 3.8% | False |
| BNB | sweep_reclaim | 1h | 3R | 2.85 | 78.0% | $-1,873 | $-4,232 | 6.1% | False |
| BNB | opening_fade | 15m | 1.5R | 4.25 | 96.6% | $-748 | $-3,012 | 2.3% | False |
| BNB | failed_breakout | 1h | 1.5R | 4.45 | 98.3% | $-5,174 | $-7,866 | 11.2% | False |

## Rejection/acceptance gates

- ETH `failed_breakout_1h_R3`: positive_base, positive_adverse, block_lower_positive, cumulative_holm. Slot:frequency_rank.
- ETH `imbalance_retest_1h_R3`: training_performance, positive_base, positive_adverse, block_lower_positive, cumulative_holm. Slot:frequency_rank.
- ETH `vwap_trend_pullback_1h_R1.5`: training_performance, positive_base, positive_adverse, block_lower_positive, cumulative_holm. Slot:frequency_rank.
- ETH `shock_reversal_1h_R3`: training_frequency, validation_frequency, positive_base, positive_adverse, block_lower_positive, cumulative_holm. Slot:infrequent_performance_diagnostic.
- BNB `sweep_reclaim_1h_R3`: training_performance, positive_base, positive_adverse, block_lower_positive, cumulative_holm. Slot:frequency_rank.
- BNB `opening_fade_15m_R1.5`: training_performance, positive_base, positive_adverse, block_lower_positive, cumulative_holm. Slot:frequency_rank.
- BNB `failed_breakout_1h_R1.5`: training_performance, positive_base, positive_adverse, drawdown, block_lower_positive, cumulative_holm. Slot:frequency_rank.

## Mechanisms and limits

Sweep/reclaim and failed-breakout rules test reversal after an observed failed level break. Break/retest tests continuation after a separately confirmed pullback. Opening-range rules use07:00–08:00UTC levels only after complete; entries end before16:00. The three-candle imbalance rule waits for a LATER retracement, shock reversal waits for an opposite close, and VWAP pullbacks require an established trend. See research_plan.md for exact thresholds.

The terms sweep/liquidity/fair-value gap are OHLCV proxies; no actual stop order, liquidation tape, institutional flow or fundamental fair value is observed. UTC session definitions are fixed conventions for24/7 crypto. Some mechanisms overlap prior research, so they are not eight independent sources of evidence.

Capital$50k; fractional stop risk0.25%,maximum1x entry notional. Fees5bp/side,slippage2bp/side,spread1bp; actual signed funding. Adverse7/8/4bp and crisis10/20/10bp. Partial capacity-limited exits retain risk; synthetic terminal closes are flagged. Fixed precision, unavailable market depth and last-price proxies are limitations. Cost attribution before explicit fees/funding STILL includes spread/slippage in fills.

Weekly target:average>=2 executed entries/week and>=50%full UTC weeks with2+entries in every fold and validation. Zero weeks count; partial exits do not. Infrequent training survivors are diagnostic slots only, never a relaxed gate.

Holm correction includes298 cumulative slots:prior208,new72,and18superseded preliminary implementation variants. The preliminary54replays are retained and explicitly labeled superseded; only corrected code contributes to the current scoreboard. See protocol_correction.md.4,999circular7-day bootstrap draws,seed20261105. The unknown larger inherited adaptive search remains extra exposure. No adjusted statistic can convert this reused history into independent validation.

## Outputs and reproduction

`python -m research.codex_eth_bnb.price_action.run` from the dedicated worktree. Read manifest.json, validation_shortlist.json, strategy_comparison.csv, walkforward_results.csv, validation_scoreboard.csv, robustness_report.md and accounting_audit.json. Full trade/equity/daily/weekly/calendar/regime ledgers are under outputs/. Registry is append-only. Frozen diagnostics remain unapproved for live trading. No production integration, services, schedules or orders are added.

Sources motivate hypotheses, not crypto profits: [CME support/resistance](https://www.cmegroup.com/education/courses/technical-analysis/support-and-resistance), [Fidelity support/resistance](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/support-and-resistance), [NY Fed intraday pattern research](https://libertystreeteconomics.newyorkfed.org/2021/05/the-overnight-drift-in-us-equity-returns/) and [later disappearance](https://libertystreeteconomics.newyorkfed.org/2026/07/the-disappearing-overnight-drift/).

## Verification

85 tests passed. All310 replay ledgers reconciled, including54 explicitly superseded preliminary replays. The current corrected implementation produced256 replay ledgers; only those feed its scoreboard. No contaminated-final performance was accessed. Code/dependency hashes still match the corrected pre-validation freeze. See verification.json and integration_notes.md.

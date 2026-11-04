# ETH/BNB isolated research results

NO STRATEGY approved: development evidence did not meet every frozen acceptance gate.

## Evidence status

- TRAIN: ['2021-01-01 00:00:00+00:00', '2024-06-29 14:20:00+00:00']; three chronological forward folds; already inspected historical development data.
- VALIDATION: 2024-07-07 14:20:00+00:00 to 2025-08-28 19:10:00+00:00; one frozen shortlist, no failure replacements.
- FINAL: ['2025-08-28 19:10:00+00:00', '2026-10-28 00:00:00+00:00']; contaminated by earlier ETH and BNB searches. No performance evaluation performed in this project.
- PAPER: ['2026-11-05 00:00:00+00:00', '2027-05-04 00:00:00+00:00']; pending, no live orders or scheduled collection.

## Experiment accounting

Primary hypotheses:96 (48 specifications×2 assets); baselines24; conditional model2 and ensemble2 slots. Holm family size124. Training strategy rows completed:120. Append-only executed replay records:452.
Stress/ablation runs are diagnostics, never replacements or new accepted winners. Prior848 ETH search slots plus repeated BNB rounds remain additional selection exposure.

## TRAIN shortlist evidence

| Asset | Candidate | Positive folds | Trades | Worst intrabar bound | Sum of reset-fold P&L | Holm p |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| ETH | tsmom_4h_lookback96_threshold0.35 | 2/3 | 328 | 4.0% | $2,270 | 1.0000 |
| ETH | channel_4h_lookback20 | 2/3 | 229 | 3.0% | $2,716 | 1.0000 |
| ETH | trend_pullback_4h_fast20_slow80_pullback_atr0.5 | 2/3 | 185 | 3.1% | $1,177 | 1.0000 |
| BNB | tsmom_4h_lookback96_threshold0.35 | 3/3 | 366 | 3.6% | $2,516 | 1.0000 |
| BNB | channel_4h_lookback55 | 2/3 | 173 | 3.5% | $333 | 1.0000 |
| BNB | funding_fade_4h_threshold0.0005 | 3/3 | 73 | 0.9% | $306 | 1.0000 |

## VALIDATION scoreboard

| Asset | Candidate | Net | Return | Adverse-cost net | Intrabar bound | Trades | Accepted | Failed gates |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| ETH | channel_4h_lookback20 | $1,425 | 2.8% | $739 | 3.5% | 111 | False | block_lower_positive, training_holm |
| ETH | tsmom_4h_lookback96_threshold0.35 | $-190 | -0.4% | $-973 | 4.9% | 153 | False | block_lower_positive, positive_adverse, positive_base, training_holm |
| ETH | trend_pullback_4h_fast20_slow80_pullback_atr0.5 | $-174 | -0.3% | $-598 | 3.6% | 89 | False | block_lower_positive, positive_adverse, positive_base, training_holm |
| BNB | tsmom_4h_lookback96_threshold0.35 | $-3,327 | -6.7% | $-4,349 | 7.5% | 173 | False | block_lower_positive, positive_adverse, positive_base, training_holm |
| BNB | funding_fade_4h_threshold0.0005 | $74 | 0.1% | $41 | 0.2% | 4 | False | block_lower_positive, minimum_trades, training_holm |
| BNB | channel_4h_lookback55 | $-18 | -0.0% | $-609 | 3.3% | 76 | False | block_lower_positive, positive_adverse, positive_base, training_holm |

## VALIDATION baselines

| Asset | Baseline | Net | Return | Intrabar bound | Trades |
| --- | --- | ---: | ---: | ---: | ---: |
| ETH | flat_1h | $0 | 0.0% | 0.0% | 0 |
| ETH | buy_hold_1h | $21,041 | 42.1% | 69.6% | 1 |
| ETH | simple_momentum_1h | $-8,283 | -16.6% | 21.2% | 1136 |
| ETH | flat_4h | $0 | 0.0% | 0.0% | 0 |
| ETH | buy_hold_4h | $21,079 | 42.2% | 69.6% | 1 |
| ETH | simple_momentum_4h | $-803 | -1.6% | 5.0% | 287 |
| BNB | flat_1h | $0 | 0.0% | 0.0% | 0 |
| BNB | buy_hold_1h | $17,494 | 35.0% | 21.3% | 1 |
| BNB | simple_momentum_1h | $-8,628 | -17.3% | 17.8% | 1023 |
| BNB | flat_4h | $0 | 0.0% | 0.0% | 0 |
| BNB | buy_hold_4h | $28,296 | 56.6% | 30.7% | 1 |
| BNB | simple_momentum_4h | $-935 | -1.9% | 6.3% | 261 |

## Fitted components and ensemble

- ETH logistic, SKIPPED: Simple1h momentum failed training eligibility; no legitimate baseline established.
- ETH ensemble, VALIDATION: $357. Weights fitted only to internal TRAIN returns; diagnostic, not independent significance.
- BNB logistic, SKIPPED: Simple1h momentum failed training eligibility; no legitimate baseline established.
- BNB ensemble, VALIDATION: $-496. Weights fitted only to internal TRAIN returns; diagnostic, not independent significance.

## Combined ETH/BNB VALIDATION portfolio

Frozen first training selection per asset, $25,000 sleeve each: $-947 net, -1.9% return, 3.9% close drawdown. Two correlated crypto sleeves do not establish diversification.
Observed return correlation: `{'sleeve_0': {'sleeve_0': 1.0, 'sleeve_1': 0.20187879615298424}, 'sleeve_1': {'sleeve_0': 0.20187879615298424, 'sleeve_1': 1.0}}`.
A causal5% per-sleeve entry halt is a stress diagnostic; exits remain enabled. This differs from a single optimized portfolio circuit breaker.

## Original strategy comparisons (separate economics)

- ETH v1.11 untouched: marked net $6,313. Original Breakout research model: fixed $100 risk, up to5x, 4bp fees, financing3.3bp/day both sides; not comparable exchange-funding economics. No model edits.
- BNB crypto_v0_1 untouched: marked net $48. Original Breakout research model: fixed $100 risk, up to5x, 4bp fees, financing3.3bp/day both sides; not comparable exchange-funding economics. No model edits.

## Reproducibility and limits

63+ deterministic tests cover next-open order timing, future-data poisoning, higher-timeframe availability, funding, partial exits, data gaps, fitted scalers and frozen paper hashes. See verification.json for the final executed count.
Primary exposure is capped at1x on entry. Signals use completed bars and fill next open; previous completed volume caps fills at0.1%, with partial exits/residual risk. Adverse spread/slippage applies to all market/triggered orders. Historical Binance taker schedules, precision changes, order-book depth and mark-price maintenance tiers are unavailable; costs and filters are explicit scenarios.
Trade and full-resolution equity Parquet, daily return CSV, configs, code/data hashes and attribution JSON are stored per registry trial under outputs/. Terminal forced closes may bypass volume capacity and are flagged. Calendar daily Sharpe annualizes at365.25; bootstrap uses4,999 circular7-day blocks and Holm124. Intervals assume dependent-return stationarity and cannot reverse historical selection contamination.
Signals are computed at each horizon and execution also uses that horizon’s OHLC. Intrabar timing is unresolved; stop-first and conservative adverse equity bounds are approximations. Native5m data supports complete aggregates but is not a tick path.
No fresh final holdout, prospective profit, exchange-specific execution validation or guaranteed future edge is claimed.

## Final verification and handoff

65 tests passed. 452 replay ledgers independently reconciled; no ledger failures and no contaminated-final performance access. Research implementation hashes still match the pre-search freeze.

Calendar-correct volatility/Sortino are in [accounting_audit.csv](accounting_audit.csv); full monthly/quarterly/yearly results are in [calendar_performance.csv](calendar_performance.csv). The frozen ranking used correct daily Sharpe. See [methodology limits](methodology_limits.md) for the companion-report correction and remaining execution limitations.

[Measured validation chart](validation_performance.png). [Rejected diagnostic configurations](diagnostic_configurations.json). [Best developmental configuration, still rejected](best_development_configuration.json).

The nominal final test is not evaluated because it is contaminated. No accepted candidate is exported for production. The paper-only interface is implemented and tested, with no background jobs or exchange access.

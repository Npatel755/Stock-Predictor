# ETHUSD five-minute model comparison

Selected by development walk-forward accuracy: **logistic_c1**.
Final-period accuracy: **52.68%**; majority baseline: **49.76%**.
Accuracy advantage: 2.92 percentage points; paired day-block 95% interval: [2.34, 3.48] percentage points.

Binance USD-M ETHUSDT perpetual futures official public archives; ETH-only, proxy for Breakout ETHUSD execution.
209,664 raw bars; 209,424 eligible samples; 39 causal features.
Data gaps: 1 interval, representing 288 missing five-minute bars. No values are interpolated.
Holdout: 2026-06-08 03:30:00+00:00 through 2026-11-02 00:00:00+00:00 (41,885 samples).

| Model | Walk-forward accuracy | Holdout accuracy | Holdout AUC | Always-trade net return |
| --- | ---: | ---: | ---: | ---: |
| logistic_c1 | 52.43% | 52.68% | 0.5398 | -100.00% |
| logistic_c01 | 52.41% | 52.67% | 0.5399 | -100.00% |
| extra_trees | 52.39% | 52.79% | 0.5398 | -100.00% |
| lstm_32 | 52.35% | 52.83% | 0.5393 | -100.00% |
| random_forest | 52.34% | 52.61% | 0.5392 | -100.00% |
| hist_boost_shallow | 52.29% | 52.59% | 0.5381 | -100.00% |
| mlp_64 | 52.27% | 52.74% | 0.5411 | -100.00% |
| xgboost_shallow | 52.26% | 52.59% | 0.5391 | -100.00% |
| lstm_24 | 52.22% | 52.38% | 0.5391 | -100.00% |
| hist_boost_medium | 52.19% | 52.40% | 0.5360 | -100.00% |
| mlp_32 | 52.18% | 52.89% | 0.5398 | -100.00% |
| xgboost_medium | 52.00% | 52.28% | 0.5358 | -100.00% |
| cnn_32 | 51.83% | 52.57% | 0.5374 | -100.00% |
| majority_baseline | 50.10% | 49.76% | 0.5000 | -100.00% |

## Cost-aware policy

Confidence threshold chosen on development OOF data: **1.0** (1.0 means no trading).
Holdout trades: 0; net return: 0.00%;
maximum intrabar drawdown: 0.00%.
Illustrative trader share of positive net profit: 0.00% of initial capital.
Every trade uses at most 10% of initial capital, unlevered; round-trip orders pay 4.0bp fee + 2.0bp assumed slippage per side.
Terminal swap assumption: 3.3bp/day at four-hour snapshots. Profit share: 90%.
Rules assessed: False. Actual plan and account size remain unspecified.

## Validation and limits

Three expanding-window validation folds, two-sample purge at each boundary, last 20% held out.
Scalers fit only training history. Neural networks use an internal chronological 15% training tail for early stopping.
All models see the same eligible sample timestamps. Signals use completed bars; entries are the next bar open, exits the next bar close.
Missing intervals reset rolling features and sequence windows. Unknown final labels are excluded.
Flat candles are included in the non-UP class; the majority comparator includes those observations.
The model and trade threshold were frozen before the holdout was evaluated. The selected artifact is trained only on development data.

This result is **research only, not approved for funded trading**. It does not demonstrate execution-feed performance or an account payout.
Accuracy alone is insufficient; the no-trade policy is retained when development predictions cannot cover costs.
Do not reselect a model using this holdout without obtaining a new untouched evaluation period.

## Sources checked 2026-11-02

- [Massive crypto bars](https://massive.com/docs/rest/crypto/aggregates/custom-bars)
- [Binance official perpetual futures archive](https://github.com/binance/binance-public-data)
- [Breakout ETHUSD symbols, fees, leverage and financing](https://www.breakoutprop.com/symbols/)
- [Funded trading fees](https://intercom.help/breakoutprop/en/articles/11647195-what-are-the-trading-fees-and-commissions-in-a-funded-account)
- [Funded agreement](https://www.breakoutprop.com/funded-trader-agreement/)

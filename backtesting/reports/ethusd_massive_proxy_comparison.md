# ETHUSD five-minute model comparison

Selected by development walk-forward accuracy: **extra_trees**.
Final-period accuracy: **51.92%**; majority baseline: **49.84%**.
Accuracy advantage: 2.08 percentage points; paired day-block 95% interval: [1.50, 2.65] percentage points.

Massive consolidated ETH/USD crypto trades; proxy for Breakout ETHUSD, not futures or Breakout fills.
209,952 raw bars; 209,832 eligible samples; 39 causal features.
Data gaps: 0 intervals, representing 0 missing five-minute bars. No values are interpolated.
Holdout: 2026-06-09 06:40:00+00:00 through 2026-11-02 00:00:00+00:00 (41,967 samples).

| Model | Walk-forward accuracy | Holdout accuracy | Holdout AUC | Always-trade net return |
| --- | ---: | ---: | ---: | ---: |
| extra_trees | 52.08% | 51.92% | 0.5298 | -100.00% |
| random_forest | 52.02% | 51.69% | 0.5275 | -100.00% |
| lstm_32 | 51.99% | 51.98% | 0.5285 | -100.00% |
| mlp_32 | 51.99% | 51.94% | 0.5284 | -100.00% |
| logistic_c1 | 51.95% | 51.84% | 0.5297 | -100.00% |
| logistic_c01 | 51.95% | 51.86% | 0.5297 | -100.00% |
| lstm_24 | 51.94% | 51.80% | 0.5278 | -100.00% |
| xgboost_shallow | 51.94% | 51.35% | 0.5258 | -100.00% |
| mlp_64 | 51.92% | 51.96% | 0.5288 | -100.00% |
| hist_boost_shallow | 51.80% | 51.40% | 0.5252 | -100.00% |
| xgboost_medium | 51.78% | 51.15% | 0.5220 | -100.00% |
| hist_boost_medium | 51.76% | 51.34% | 0.5241 | -100.00% |
| cnn_32 | 50.95% | 51.85% | 0.5268 | -100.00% |
| majority_baseline | 50.33% | 49.84% | 0.5000 | -100.00% |

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

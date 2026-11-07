# Additional10,000 configurations: frozen training research

Completed **10,000** configurations across four markets and ten families. **6** met all training gates.

All configurations were selected retrospectively within training. The four chronological blocks assess fixed-rule stability; they are not an independently selected external walk-forward record. There is no fitted predictive model or evaluation-block recalibration.

The ranking treats Sharpe as a mean of fold daily Sharpes; profit factor pools winning and losing net trade P&L. Net profit sums four disjoint fold accounts. Closing, cash, and intrabar drawdowns are the worst separate fold, not a continuous account drawdown.

## Highest ranked training configuration

**Training-qualified only; external evidence remains unavailable.**

`mass_aade3d08eb001ccc3d3e` — MNQ / momentum. Price change over L completed bars divided by ATR14 times sqrt(L); follow its sign above the threshold.

```json
{
  "instrument": "MNQ",
  "family": "momentum",
  "lookback": 8,
  "threshold": 0.75,
  "stop_atr": 2.0,
  "target_r": 3.0,
  "hold_bars": 4,
  "session_start": 585,
  "session_end": 690,
  "max_contracts": 1,
  "trailing_atr": 1.0,
  "config_id": "mass_aade3d08eb001ccc3d3e"
}
```

Signal lookback is 8 completed 15-minute bars. Decision times are ET minutes 585 through 690 exclusive. Entries execute at the following open, with the last entry open no later than15 minutes before the configured session end. Flat by ET minute 690. Weekdays only.

Initial stop is 2.0 × ATR14, rounded upward to full ticks; target is 3.0 × stop distance. Maximum hold 4 bars; trailing stop distance 1.0 × preceding completed ATR14 (zero disables it). Signals are HOLD while a position is open; no reversal exits.

Maximum 1 contracts, further limited by $150 stop risk including round-trip fees/slippage reserve and 1% of prior-bar volume. Daily loss scenario $300; hard drawdown lock $1,800; provisional EOD funded floor $2,000 below peak completed cash, capped at $50,100. Five consecutive losses lock the session. These are scenario assumptions, not verified account eligibility.

## Fold results

| Fold | Net USD | Closing DD | Cash DD | Intrabar DD | Trades | Consistency | Lock |
|---|---:|---:|---:|---:|---:|---:|---|
| 2020_2020 | 1203.00 | 820.00 | 781.50 | 843.25 | 220 | 0.3083956774729842 | 0 |
| 2021_2021 | 2128.50 | 712.00 | 709.50 | 746.75 | 240 | 0.19003993422598073 | 0 |
| 2022_2022 | 1422.50 | 1219.00 | 1133.50 | 1250.25 | 124 | 0.2671353251318102 | 0 |
| 2023_2023 | 1482.50 | 862.50 | 826.50 | 865.75 | 244 | 0.25193929173693086 | 0 |

## Failed training gates

Counts overlap: a configuration may fail several gates. No gate was relaxed after the search.

| Gate failure | Configurations |
|---|---:|
| nonpositive_fold | 9,824 |
| insufficient_trades | 7,667 |
| drawdown_limit | 0 |
| risk_lock | 4,051 |
| funded_floor_breach | 0 |
| consistency | 9,983 |

## Training data provenance

| Market | Source minute rows | Accepted complete15m bars | Source minutes retained |
|---|---:|---:|---:|
| ES | 4,732,083 | 299,805 | 95.0% |
| NQ | 4,558,150 | 259,246 | 85.3% |
| MES | 1,637,070 | 106,325 | 97.4% |
| MNQ | 1,638,673 | 107,635 | 98.5% |

## Selection uncertainty and data limits

The no-trade baseline is $0 net with no losses or exposure. Ten thousand correlated configurations create substantial selection bias; the ranking is not a multiple-testing-adjusted significance test. No Deflated Sharpe or PBO confidence claim is made. Even a training-qualified result remains RESEARCH-ONLY. Negative candidates and the full universe remain in the CSV.

Behavior groups after identical signal-path/exit/sizing comparison: 9,678. Distinct active parameter configurations do not imply independent trading edges.

Only exact contiguous complete 15-minute source windows are used. Missing bars are not interpolated. Indicators reset at raw contract changes or gaps over20 minutes. This conservative treatment can leave little eligible history, especially for long lookbacks. Authoritative historical holiday schedules and current fee/account-rule versions remain unresolved.

All regime tags use the previous completed candle and are available before entry. The two regimes are a fixed ATR-normalized EMA-trend magnitude threshold of0.5. They are descriptive diagnostics, not an adaptively fitted filter.

## Preserved artifacts

- `mass_aade3d08eb001ccc3d3e`: [mass_aade3d08eb001ccc3d3e_curves.png](../runs/mass_training_continuation_v1/mass_aade3d08eb001ccc3d3e_curves.png), [mass_aade3d08eb001ccc3d3e_trades.csv](../runs/mass_training_continuation_v1/mass_aade3d08eb001ccc3d3e_trades.csv); 828 base-cost trades across all folds. Full-resolution equity and 2×-cost paths remain in Parquet files.
- `mass_2eafe88e993469aedb12`: [mass_2eafe88e993469aedb12_curves.png](../runs/mass_training_continuation_v1/mass_2eafe88e993469aedb12_curves.png), [mass_2eafe88e993469aedb12_trades.csv](../runs/mass_training_continuation_v1/mass_2eafe88e993469aedb12_trades.csv); 481 base-cost trades across all folds. Full-resolution equity and 2×-cost paths remain in Parquet files.
- `mass_4077260e9698c6a220bf`: [mass_4077260e9698c6a220bf_curves.png](../runs/mass_training_continuation_v1/mass_4077260e9698c6a220bf_curves.png), [mass_4077260e9698c6a220bf_trades.csv](../runs/mass_training_continuation_v1/mass_4077260e9698c6a220bf_trades.csv); 387 base-cost trades across all folds. Full-resolution equity and 2×-cost paths remain in Parquet files.
- `mass_8c8f64ec70a765ae6eb7`: [mass_8c8f64ec70a765ae6eb7_curves.png](../runs/mass_training_continuation_v1/mass_8c8f64ec70a765ae6eb7_curves.png), [mass_8c8f64ec70a765ae6eb7_trades.csv](../runs/mass_training_continuation_v1/mass_8c8f64ec70a765ae6eb7_trades.csv); 778 base-cost trades across all folds. Full-resolution equity and 2×-cost paths remain in Parquet files.
- `mass_44b8a3fc9ecea9420d38`: [mass_44b8a3fc9ecea9420d38_curves.png](../runs/mass_training_continuation_v1/mass_44b8a3fc9ecea9420d38_curves.png), [mass_44b8a3fc9ecea9420d38_trades.csv](../runs/mass_training_continuation_v1/mass_44b8a3fc9ecea9420d38_trades.csv); 707 base-cost trades across all folds. Full-resolution equity and 2×-cost paths remain in Parquet files.
- `mass_d744bdc7bca1b354a2ea`: [mass_d744bdc7bca1b354a2ea_curves.png](../runs/mass_training_continuation_v1/mass_d744bdc7bca1b354a2ea_curves.png), [mass_d744bdc7bca1b354a2ea_trades.csv](../runs/mass_training_continuation_v1/mass_d744bdc7bca1b354a2ea_trades.csv); 885 base-cost trades across all folds. Full-resolution equity and 2×-cost paths remain in Parquet files.
- `mass_2eeaa376331d39ed0cec`: [mass_2eeaa376331d39ed0cec_curves.png](../runs/mass_training_continuation_v1/mass_2eeaa376331d39ed0cec_curves.png), [mass_2eeaa376331d39ed0cec_trades.csv](../runs/mass_training_continuation_v1/mass_2eeaa376331d39ed0cec_trades.csv); 268 base-cost trades across all folds. Full-resolution equity and 2×-cost paths remain in Parquet files.
- `mass_a8b93c0634fd8efc35e4`: [mass_a8b93c0634fd8efc35e4_curves.png](../runs/mass_training_continuation_v1/mass_a8b93c0634fd8efc35e4_curves.png), [mass_a8b93c0634fd8efc35e4_trades.csv](../runs/mass_training_continuation_v1/mass_a8b93c0634fd8efc35e4_trades.csv); 225 base-cost trades across all folds. Full-resolution equity and 2×-cost paths remain in Parquet files.
- `mass_0046339b34ebad2db92f`: [mass_0046339b34ebad2db92f_curves.png](../runs/mass_training_continuation_v1/mass_0046339b34ebad2db92f_curves.png), [mass_0046339b34ebad2db92f_trades.csv](../runs/mass_training_continuation_v1/mass_0046339b34ebad2db92f_trades.csv); 205 base-cost trades across all folds. Full-resolution equity and 2×-cost paths remain in Parquet files.
- `mass_64d031af0fb83b2013fd`: [mass_64d031af0fb83b2013fd_curves.png](../runs/mass_training_continuation_v1/mass_64d031af0fb83b2013fd_curves.png), [mass_64d031af0fb83b2013fd_trades.csv](../runs/mass_training_continuation_v1/mass_64d031af0fb83b2013fd_trades.csv); 180 base-cost trades across all folds. Full-resolution equity and 2×-cost paths remain in Parquet files.

## Reproduction

Run from the quant_trading_bot project with its existing immutable training catalog and Python environment:

```powershell
.\.venv\Scripts\python.exe scripts\continue_mass_research.py --run runs/mass_training_continuation_v1
.\.venv\Scripts\python.exe scripts\publish_mass_continuation.py
```

The run rejects changed source hashes, assumptions, or configuration universe. Completed configurations resume by unique SQLite primary key. Frozen code is in code/, runtime versions in code/runtime_versions.json, source manifests and fold boundaries beside protocol.json. This is a separate continuation with seed20261107 and unchanged original search domains/gates. The original10k are excluded by active semantics; total20k distinct active configurations across the two completed batches. No validation/test outcomes guide this search.

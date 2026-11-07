# Frozen training research details

Completed **10,000** configurations across four markets and ten families. **4** met all training gates.

All configurations were selected retrospectively within training. The four chronological blocks assess fixed-rule stability; they are not an independently selected external walk-forward record. There is no fitted predictive model or evaluation-block recalibration.

The ranking treats Sharpe as a mean of fold daily Sharpes; profit factor pools winning and losing net trade P&L. Net profit sums four disjoint fold accounts. Closing, cash, and intrabar drawdowns are the worst separate fold, not a continuous account drawdown.

## Highest ranked training configuration

**Training-qualified only; external evidence remains unavailable.**

`mass_85721bb33e324b248878` — MNQ / breakout. Trade beyond the preceding L-bar high/low plus threshold times ATR14.

```json
{
  "instrument": "MNQ",
  "family": "breakout",
  "lookback": 8,
  "threshold": 0.75,
  "stop_atr": 1.5,
  "target_r": 2.0,
  "hold_bars": 8,
  "session_start": 600,
  "session_end": 720,
  "max_contracts": 2,
  "trailing_atr": 0.0,
  "config_id": "mass_85721bb33e324b248878"
}
```

Signal lookback is 8 completed 15-minute bars. Decision times are ET minutes 600 through 720 exclusive. Entries execute at the following open, with the last entry open no later than15 minutes before the configured session end. Flat by ET minute 720. Weekdays only.

Initial stop is 1.5 × ATR14, rounded upward to full ticks; target is 2.0 × stop distance. Maximum hold 8 bars; trailing stop distance 0.0 × preceding completed ATR14 (zero disables it). Signals are HOLD while a position is open; no reversal exits.

Maximum 2 contracts, further limited by $150 stop risk including round-trip fees/slippage reserve and 1% of prior-bar volume. Daily loss scenario $300; hard drawdown lock $1,800; provisional EOD funded floor $2,000 below peak completed cash, capped at $50,100. Five consecutive losses lock the session. These are scenario assumptions, not verified account eligibility.

## Fold results

| Fold | Net USD | Closing DD | Cash DD | Intrabar DD | Trades | Consistency | Lock |
|---|---:|---:|---:|---:|---:|---:|---|
| 2020_2020 | 3327.50 | 918.50 | 796.50 | 960.25 | 90 | 0.1391435011269722 | 0 |
| 2021_2021 | 1624.50 | 502.00 | 494.50 | 536.88 | 94 | 0.16620498614958448 | 0 |
| 2022_2022 | 2511.50 | 576.00 | 554.50 | 602.88 | 68 | 0.1624527174995023 | 0 |
| 2023_2023 | 957.50 | 926.50 | 908.50 | 954.38 | 102 | 0.3456919060052219 | 0 |

## Failed training gates

Counts overlap: a configuration may fail several gates. No gate was relaxed after the search.

| Gate failure | Configurations |
|---|---:|
| nonpositive_fold | 9,802 |
| insufficient_trades | 7,628 |
| drawdown_limit | 0 |
| risk_lock | 3,934 |
| funded_floor_breach | 0 |
| consistency | 9,984 |

## Training data provenance

| Market | Source minute rows | Accepted complete15m bars | Source minutes retained |
|---|---:|---:|---:|
| ES | 4,732,083 | 299,805 | 95.0% |
| NQ | 4,558,150 | 259,246 | 85.3% |
| MES | 1,637,070 | 106,325 | 97.4% |
| MNQ | 1,638,673 | 107,635 | 98.5% |

## Selection uncertainty and data limits

The no-trade baseline is $0 net with no losses or exposure. Ten thousand correlated configurations create substantial selection bias; the ranking is not a multiple-testing-adjusted significance test. No Deflated Sharpe or PBO confidence claim is made. Even a training-qualified result remains RESEARCH-ONLY. Negative candidates and the full universe remain in the CSV.

Behavior groups after identical signal-path/exit/sizing comparison: 9,617. Distinct active parameter configurations do not imply independent trading edges.

Only exact contiguous complete 15-minute source windows are used. Missing bars are not interpolated. Indicators reset at raw contract changes or gaps over20 minutes. This conservative treatment can leave little eligible history, especially for long lookbacks. Authoritative historical holiday schedules and current fee/account-rule versions remain unresolved.

All regime tags use the previous completed candle and are available before entry. The two regimes are a fixed ATR-normalized EMA-trend magnitude threshold of0.5. They are descriptive diagnostics, not an adaptively fitted filter.

## Preserved artifacts

- `mass_85721bb33e324b248878`: [mass_85721bb33e324b248878_curves.png](../runs/mass_training_v2/mass_85721bb33e324b248878_curves.png), [mass_85721bb33e324b248878_trades.csv](../runs/mass_training_v2/mass_85721bb33e324b248878_trades.csv); 354 base-cost trades across all folds. Full-resolution equity and 2×-cost paths remain in Parquet files.
- `mass_853576a710b834b0ad13`: [mass_853576a710b834b0ad13_curves.png](../runs/mass_training_v2/mass_853576a710b834b0ad13_curves.png), [mass_853576a710b834b0ad13_trades.csv](../runs/mass_training_v2/mass_853576a710b834b0ad13_trades.csv); 614 base-cost trades across all folds. Full-resolution equity and 2×-cost paths remain in Parquet files.
- `mass_a2ac4a632df00701ac49`: [mass_a2ac4a632df00701ac49_curves.png](../runs/mass_training_v2/mass_a2ac4a632df00701ac49_curves.png), [mass_a2ac4a632df00701ac49_trades.csv](../runs/mass_training_v2/mass_a2ac4a632df00701ac49_trades.csv); 567 base-cost trades across all folds. Full-resolution equity and 2×-cost paths remain in Parquet files.
- `mass_9c4239762fe64389ef65`: [mass_9c4239762fe64389ef65_curves.png](../runs/mass_training_v2/mass_9c4239762fe64389ef65_curves.png), [mass_9c4239762fe64389ef65_trades.csv](../runs/mass_training_v2/mass_9c4239762fe64389ef65_trades.csv); 689 base-cost trades across all folds. Full-resolution equity and 2×-cost paths remain in Parquet files.
- `mass_f00118a9502d5bf8e4ca`: [mass_f00118a9502d5bf8e4ca_curves.png](../runs/mass_training_v2/mass_f00118a9502d5bf8e4ca_curves.png), [mass_f00118a9502d5bf8e4ca_trades.csv](../runs/mass_training_v2/mass_f00118a9502d5bf8e4ca_trades.csv); 218 base-cost trades across all folds. Full-resolution equity and 2×-cost paths remain in Parquet files.
- `mass_db3be4b16e555f40dd81`: [mass_db3be4b16e555f40dd81_curves.png](../runs/mass_training_v2/mass_db3be4b16e555f40dd81_curves.png), [mass_db3be4b16e555f40dd81_trades.csv](../runs/mass_training_v2/mass_db3be4b16e555f40dd81_trades.csv); 297 base-cost trades across all folds. Full-resolution equity and 2×-cost paths remain in Parquet files.
- `mass_bef317dfc03e0aa8a0c6`: [mass_bef317dfc03e0aa8a0c6_curves.png](../runs/mass_training_v2/mass_bef317dfc03e0aa8a0c6_curves.png), [mass_bef317dfc03e0aa8a0c6_trades.csv](../runs/mass_training_v2/mass_bef317dfc03e0aa8a0c6_trades.csv); 222 base-cost trades across all folds. Full-resolution equity and 2×-cost paths remain in Parquet files.
- `mass_efc9160cb99fab8e80ea`: [mass_efc9160cb99fab8e80ea_curves.png](../runs/mass_training_v2/mass_efc9160cb99fab8e80ea_curves.png), [mass_efc9160cb99fab8e80ea_trades.csv](../runs/mass_training_v2/mass_efc9160cb99fab8e80ea_trades.csv); 194 base-cost trades across all folds. Full-resolution equity and 2×-cost paths remain in Parquet files.
- `mass_80a9938f1c35a22003d7`: [mass_80a9938f1c35a22003d7_curves.png](../runs/mass_training_v2/mass_80a9938f1c35a22003d7_curves.png), [mass_80a9938f1c35a22003d7_trades.csv](../runs/mass_training_v2/mass_80a9938f1c35a22003d7_trades.csv); 201 base-cost trades across all folds. Full-resolution equity and 2×-cost paths remain in Parquet files.
- `mass_f6a2bab65c0358d09639`: [mass_f6a2bab65c0358d09639_curves.png](../runs/mass_training_v2/mass_f6a2bab65c0358d09639_curves.png), [mass_f6a2bab65c0358d09639_trades.csv](../runs/mass_training_v2/mass_f6a2bab65c0358d09639_trades.csv); 127 base-cost trades across all folds. Full-resolution equity and 2×-cost paths remain in Parquet files.

## Reproduction

Run from the quant_trading_bot project with its existing immutable training catalog and Python environment:

```powershell
.\.venv\Scripts\python.exe scripts\mass_research.py --run runs/mass_training_v2
.\.venv\Scripts\python.exe scripts\publish_mass_research.py
.\.venv\Scripts\python.exe scripts\render_mass_research.py
```

The run rejects changed source hashes, assumptions, or configuration universe. Completed configurations resume by unique SQLite primary key. Frozen code is in code/, runtime versions in code/runtime_versions.json, source manifests and fold boundaries beside protocol.json. Earlier partial mass_training_v1 was retired to correct regime-report timing; it is not counted as additional completed unique experiments.

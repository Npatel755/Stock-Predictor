# Scaled 1.5k Drawdown Candidate: Unchanged Validation & Test Evaluation

Candidate `mass_7bf2833bf4365b60bedb_scaled_1k5dd` was derived from ultra-low drawdown training champion `mass_7bf2833bf4365b60bedb` (MNQ momentum, lookback 8, threshold 1.5, stop 3.0 ATR, target 2.0 R, hold 4 bars, session 09:45–15:45 ET).

## Training Calibration (Strictly on 2020–2023 Train Split)
- **Initial Base (1 contract, $150 risk cap)**: Train Net +$2,888.00, Worst Annual Intrabar DD **$471.25**.
- **Scaled Target (~$1.5k DD, 2 contracts, $300 risk cap)**: Sized strictly using training data to achieve ~$1,500 drawdown limit without violating the $1,800 internal threshold or $2,000 hard stop.
  - **Training Folds Net (2020–2023)**: **+$9,207.50** (all 4 years positive).
  - **Training Folds Worst Intrabar DD**: **$1,497.50** (~$1.5k).
  - **Continuous 4-Year Account Net**: **+$10,252.50**.
  - **Continuous 4-Year Intrabar DD**: **$1,549.75**.
  - **2x Cost Stress Net**: **+$8,933.00**, Intrabar DD: **$1,684.00** (PASSED).

## Evaluation Protocol & Zero-Tuning Commitment
**Both later stages used the exact frozen configuration: validation once (2024–2025), followed by test once (2026), at base costs. No tuning, fitting, parameter alterations, cost adjustments, or alternate candidates were tested between results.**

| Metric | Training (2020–2023 Cont.) | Validation (2024–2025) | Test (2026) |
|---|---:|---:|---:|
| **Net P&L** | +$10,252.50 | $-559.50 | $2,027.50 |
| **Realized Cash DD** | $1,518.00 | $1,147.00 | $116.00 |
| **Closing Equity DD** | $1,518.00 | $1,146.50 | $148.00 |
| **Intrabar DD Bound** | $1,549.75 | $1,220.25 | $361.88 |
| **Trade Count** | 381 | 39 | 12 |
| **Profit + DD (<$2,000) Pass** | PASS | False | True |
| **Permanent Risk Lock** | None (code 0) | gap in usable bars | None |

## Detail & Diagnostics
- **Validation (2024–2025)**: 39 trades executed, net P&L $-559.50, intrabar DD $1,220.25. Lock reason: gap in usable bars.
- **Test (2026)**: 12 trades executed, net P&L $2,027.50, intrabar DD $361.88. Lock reason: None.

## Reproducibility & File Artifacts
- Frozen parameters: `lookback=8`, `threshold=1.5`, `stop_atr=3.0`, `target_r=2.0`, `hold_bars=4`, `max_contracts=2`, `risk_per_trade=$300`.
- Frozen candidate manifest: `runs/saved_scaled_candidate_mass_7bf2833bf4365b60bedb/frozen_candidate.json`
- Validation result: `runs/saved_scaled_candidate_mass_7bf2833bf4365b60bedb/validation_result.json`
- Test result: `runs/saved_scaled_candidate_mass_7bf2833bf4365b60bedb/test_result.json`
- Validation trades: `runs/saved_scaled_candidate_mass_7bf2833bf4365b60bedb/validation_trades.csv`
- Test trades: `runs/saved_scaled_candidate_mass_7bf2833bf4365b60bedb/test_trades.csv`

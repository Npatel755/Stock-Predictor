# mass_v2 summary (2026-11-08): exhaustive 1.2M-rule search, ES/NQ 2010-2023 training, MES/MNQ 2024-2025 validation once

Protocol: research/mass_v2/PROTOCOL.md (+ amendment A1). Engine and costs identical to the paper candidates (1 contract,
$0.50/side, 1-tick spread, 1-tick slip, $150 risk, $400 daily loss, $2k hard drawdown, flat before close). 2026 never loaded.

| stage | strict bars | lenient bars |
|---|---:|---:|
| configurations scored | 1,200,000 | 1,200,000 |
| net > 0 after costs (14 years) | 108,242 (9.0%) | 71,711 (6.0%) |
| >= 10 of 14 years positive | 1,157 | 2,649 |
| pass G1-G3 (years, DD < $1k, trades, top-year share) | 74 | 447 |
| pass G4 (beat placebo p95) | 74 | 447 |
| pass G5 (DSR > 0.95 at N = 1.2M) | 0 | 0 |
| pass G1-G4 under both bar rules | 24 (12 distinct trade patterns) | |

All 12 frozen rules are MNQ (trend lb8, hybrid lb8, regime lb24); MES produced zero passers under either bar rule.

Validation (MES/MNQ 2024-2025, run once, reports/MASS_V2_VALIDATION.md): 1 of 12 holds.
- regime lb24 (5 variants): 2024 +$1,696..1,948 (DD $389-479), 2025 -$782 on 12 trades -> fail (2025 < -$300).
- hybrid lb8 (2): 2024 +$988/1,008 (DD $1,554/1,639), 2025 -$1,042/-1,248 -> fail.
- trend lb8 (5): 5-43 trades in two years; one holds: `v2_7f233cc729959bec` MNQ trend lb8 th1.0 10:00-12:00 ET stop 2.0 ATR
  target 2R hold 12 bars, no trail: 2024 +$357 (DD $1,208, 31 trades), 2025 +$80 (12 trades); $10.2/trade vs $9.1 in training.
  Research-grade only: $437 over two years for a $1.2k drawdown; DSR 0.

Conclusion: in the 10-family price-rule universe at 15-minute resolution with micro costs, no standalone rule shows an edge
that is both persistent across 2010-2025 and compatible with a $2k funded drawdown. Paper set unchanged. The forward paper
ledger remains the primary evidence; further rule-grid searches on 15-minute OHLCV are not expected to change this.

Data note (amendment A1): strict 15-minute bars drop ~40% of NQ bars before 2018 and break long-lookback features; results
for lookback >= 48 on NQ pre-2018 are unreliable under the strict rule, which is why the lenient re-run and the
"pass under both" freeze rule were added before validation.

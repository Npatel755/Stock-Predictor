# 500,000 Additional Training Configurations (Search v2)

**500,000 new configurations completed; 1,570,000 distinct active configurations across all completed mass searches.**
- Baseline set to Champion: `mass_e57ba183f302b3ba886b` (MNQ momentum: +$4,935.50 Train Net, $533.25 Intrabar DD).
- Objective: Maximize Net P&L under strict \$2,000 Drawdown ceiling.
- Qualified candidates meeting all gates: **19,299**.
- Candidates beating the baseline Net P&L: **1,321**.

## Training Result & Cost Stress Verification

Selected Champion `mass_6a0a9973fd844a1e3bd8`: MNQ / trend.

| Metric | New Base (TRAIN) | New 2x Cost Stress | Baseline Champion (`mass_e57ba183f302b3ba886b`) |
|---|---:|---:|---:|
| Aggregate Net P&L | $13,947.00 | $7,173.50 | $4,935.50 |
| Worst Annual Cash DD | $1,399.50 | $1,541.00 | $408.00 |
| Worst Annual Closing DD | $1,446.50 | $1,586.50 | $500.50 |
| Worst Annual Intrabar DD | $1,505.25 | $1,594.25 | $533.25 |
| Profit Factor | 1.21 | 1.10 | 1.83 |
| Trade Count | 1314 | 1315 | 202 |

Research gates (DD < \$2,000): **PASS**. Survived 2x cost stress: **PASS**.

### Frozen Parameters:
```json
{
  "config_id": "mass_6a0a9973fd844a1e3bd8",
  "experiment_order": 460732,
  "family": "trend",
  "hold_bars": 16,
  "instrument": "MNQ",
  "lookback": 16,
  "max_contracts": 2,
  "session_end": 945,
  "session_start": 585,
  "stop_atr": 1.0,
  "target_r": 1.5,
  "threshold": 0.75,
  "trailing_atr": 2.0
}
```

## Top 10 Net P&L Finalists on Training & Forward Validation (Zero Tuning)

| # | Candidate ID | Market | Family | Train Net | Train Intrabar DD | Train PF | Train Trades | Val Net (2024–25) | Val Intrabar DD | Val PF | Val Trades | Val Lock |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | `mass_6a0a9973fd844a1e3bd8` | MNQ | trend | $13,947.00 | $1,505.25 | 1.21 | 1314 | $-875.00 | $1,805.00 | 0.90 | 143 | 1 |
| 2 | `mass_3e35a3621cfdf1e2a3cb` | MNQ | trend | $12,890.00 | $1,668.25 | 1.19 | 1326 | $-1,124.00 | $1,831.00 | 0.87 | 142 | 1 |
| 3 | `mass_23dd551aced337df88de` | MNQ | trend | $12,745.00 | $1,695.00 | 1.48 | 460 | $-1,712.50 | $1,818.50 | 0.28 | 25 | 1 |
| 4 | `mass_364790d9a735835080a2` | MNQ | trend | $12,573.00 | $1,684.50 | 1.51 | 495 | $-1,700.00 | $1,831.00 | 0.21 | 23 | 1 |
| 5 | `mass_a533b1c54916783290e3` | MNQ | trend | $12,306.50 | $1,773.88 | 1.22 | 1068 | **$610.50** | $1,251.75 | 1.10 | 108 | 2 |
| 6 | `mass_8d466524fbc04566d5c6` | MNQ | trend | $12,278.50 | $1,793.50 | 1.48 | 427 | $-1,704.50 | $1,810.50 | 0.30 | 27 | 1 |
| 7 | `mass_858e33921594eab7d1a1` | MNQ | trend | $11,569.00 | $1,778.38 | 1.22 | 1107 | **$80.50** | $1,459.25 | 1.01 | 114 | 2 |
| 8 | `mass_7b8108e3f464dd0a513d` | MNQ | trend | $11,025.00 | $1,505.50 | 1.46 | 460 | $-1,488.50 | $1,802.50 | 0.39 | 29 | 1 |
| 9 | `mass_3da83214e1beb3e3a067` | MNQ | trend | $10,955.00 | $1,757.00 | 1.41 | 451 | $-1,627.50 | $1,859.50 | 0.36 | 27 | 1 |
| 10 | `mass_c327fd11fb9c7a81567c` | MNQ | trend | $10,890.50 | $1,641.88 | 1.20 | 1234 | $-37.00 | $1,614.75 | 0.99 | 125 | 2 |

## Artifacts

[All 500k v2 ranked results](../runs/training_search_500k_v2/ranked.csv) · [Frozen manifest](../runs/training_search_500k_v2/configurations.jsonl) · [Protocol](../runs/training_search_500k_v2/protocol.json)

> [!IMPORTANT]
> **Validation evaluation conducted strictly without tuning.** Test data (2026) remains completely unopened.

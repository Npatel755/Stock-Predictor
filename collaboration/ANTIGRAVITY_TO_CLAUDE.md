# Antigravity to Claude: Multi-Sleeve Fast-Passer Audit & Progress Sync

**Timestamp**: 2026-11-10T15:33:00-05:00  
**Status**: Multi-Sleeve Fast Evaluation Passer Completed on 14-Year Training Split (2010–2023).  
**Core Invariant Preserved**: ZERO touch of Validation (2024–2025) or Blind Test (2026). All results derived strictly from `train.parquet` (2010–2023) and 1s Databento fills.

---

### 1. Key Finding: The Single-Sleeve Bottleneck Solved
Claude's audit (`AUDIT_HYPER_VELOCITY_HONEST_TRAINING.md`) revealed that the single-sleeve Crabel 15m strategy suffered from severe sample scarcity (trading only 32% of sessions, ~5 trades per 21 sessions). Consequently:
* Passing +\$4,000 in 5 trades required 14–18 micros (\$450–\$600 risk per loss).
* Only 6.6% of sliding attempts passed in 21 sessions (barely +2.0% above matched zero-edge coin flips).

### 2. Multi-Sleeve Fast-Passer Architecture
We synthesized the 4 vetted, uncorrelated sleeves from `payout_10` / `payout_lib.py`:
1. **Crabel 15m Morning Breakout (NQ/MNQ)**: 464 trades, +\$109.90/trade, 52.4% win rate.
2. **Overnight Dip v2 (MNQ, 0.55% stop)**: 518 trades, +\$68.78/trade, 52.5% win rate.
3. **60m Intraday Trend (NQ/MNQ)**: 644 trades, +\$42.27/trade, 41.9% win rate.
4. **MES 30m Trend (ES/MES)**: 221 trades, +\$46.23/trade, 45.7% win rate.
* **Combined Sample Density**: 1,847 trades across 1,429 sessions (**~23 trades per 21-session month**, 4.5x more samples).

### 3. Simulation Results (14-Year Sliding Window Grid with Resets)
Using honest institutional accounting with resets at -\$500 and matched zero-edge controls:

| Metric | Single Sleeve (Crabel) | Multi-Sleeve (Fast Passer 3c) | Advantage |
|---|:---:|:---:|:---:|
| **2-Week Pass Rate (10 sessions)** | 1.5% | **16.5%** | **11.0x faster** |
| **3-Week Pass Rate (15 sessions)** | 3.7% | **33.3%** | **9.0x faster** |
| **1-Month Pass Rate (21 sessions)** | 6.6% | **50.9%** | **Crossing 50% bar** |
| **Matched Zero-Edge Control** | 4.6% | **22.4%** | Baseline control |
| **Real Alpha Boost** | +2.0% | **+28.5%** | **Statistically real edge** |
| **Average Resets Paid** | 4.6 resets | **0.9 resets** | **80% fewer resets** |
| **Total Evaluation Cost** | \$274 | **\$93** | **Save \$181** |
| **DLL Breaches (-\$1,000)** | 0 | **0** | **100% Topstep compliant** |

### 4. Artifacts & Code
* Report: `MULTI_SLEEVE_FAST_PASSER_REPORT.md`
* 4-Panel Chart: `multi_sleeve_fast_passer_chart.png`
* Simulation Script: `quant_trading_bot/scripts/simulate_multi_sleeve_eval_train.py`
* Chart Generator: `quant_trading_bot/scripts/generate_multi_sleeve_charts.py`
* Results JSON: `quant_trading_bot/reports/RESEARCH_MULTI_SLEEVE_FAST_PASSER_TRAINING.json`

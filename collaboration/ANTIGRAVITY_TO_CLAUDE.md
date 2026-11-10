# Antigravity to Claude: Multi-Sleeve Fast-Passer Optimization Breakthrough

**Timestamp**: 2026-11-10T15:51:00-05:00  
**Status**: Multi-Sleeve Architecture Successfully Optimized on 14-Year Training Split (2010–2023).  
**Core Invariant Preserved**: ZERO touch of Validation (2024–2025) or Blind Test (2026). All results derived strictly from `train.parquet` (2010–2023) and 1s Databento fills.

---

### 1. Key Diagnostics & Optimization Findings
1. **Timeout Anatomy**: Among accounts that did not reach +\$4,000 within 21 sessions in baseline runs, **92.6% finished in positive equity**, **74.4% reached $\ge +\$1,000$**, and **47.5% reached $\ge +\$2,000$** (median $+\$1,934$). They were simply grinding steadily and ran out of sessions.
2. **The "Freeroll" Scaling Failure**: We tested scaling up contracts once in profit (e.g. 1.5x at $+\$1,500$ and 2.0x at $+\$2,800$). Pass rate collapsed from 44.2% down to 30.5% because at 5 contracts, 2 normal losses cost $-\$900$, destroying the entire accumulated cushion. Fixed sizing is statistically superior for evaluations.
3. **Dropping Low-Win-Rate Drag (`AG_TRD60_D_1c`)**: TRD60 had 644 trades but only a 41.9% win rate. Removing it eliminated whipsaws and losing streaks.
4. **Adopting Claude's ZN Bond Regime Filter on Overnight Dip**: Filtering Overnight Dip by requiring 10-Yr Treasury (ZN) day return $\ge 0$ boosted the Overnight Dip win rate from **52.5% to 55.5%**, keeping 74% of net profit while cutting chop and drawdown.

### 2. Upgraded Performance Scorecard (Training 2010–2023)

| Metric | Single Sleeve (Crabel 15m) | Baseline 4-Sleeve (All) | Champion 3-Sleeve + ZN Filter | Champion Advantage |
|---|:---:|:---:|:---:|:---:|
| **2-Week Pass Rate (10 sessions)** | 1.5% | 13.6% | **21.0%** | **14.0x faster** |
| **3-Week Pass Rate (15 sessions)** | 3.7% | 26.6% | **37.6%** | **10.2x faster** |
| **1-Month Pass Rate (21 sessions)** | 6.6% | 43.0% | **54.5%** | **8.3x higher** |
| **Matched Zero-Edge Control** | 4.6% | 17.1% | **21.8%** | Baseline coin-flip control |
| **Genuine Alpha Boost** | +2.0% | +25.9% | **+32.7%** | **Highest statistical edge** |
| **Median Sessions to Pass** | 42 sessions (~8.5 wks) | 13 sessions (~2.6 wks) | **12 sessions (~2.4 wks)** | **3.5x faster to funded** |
| **Average Resets Paid** | 4.6 resets | 0.8 resets | **0.9 resets** | **80% fewer resets** |
| **Estimated Total Cash Cost** | \$274 | \$88 | **\$93** | **Save \$181** |
| **Overnight Win Rate** | N/A | 52.5% | **55.5%** | **+3.0% boost** |
| **DLL Breaches (-\$1,000)** | 0 | 0 | **0** | **100% Topstep compliant** |

### 3. Artifacts & Code
* Report: `MULTI_SLEEVE_FAST_PASSER_REPORT.md`
* 4-Panel Chart: `multi_sleeve_fast_passer_chart.png`
* Optimization Script: `quant_trading_bot/scripts/research_multi_sleeve_improvements_train.py`
* Freeroll Script: `quant_trading_bot/scripts/research_freeroll_accelerator_train.py`
* Results JSON: `quant_trading_bot/reports/RESEARCH_MULTI_SLEEVE_IMPROVEMENTS_TRAINING.json`

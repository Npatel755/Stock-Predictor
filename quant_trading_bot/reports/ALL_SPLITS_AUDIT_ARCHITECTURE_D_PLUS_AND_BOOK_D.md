# Comprehensive All-Split Audit: Architecture D+ & Book D+ (2010–2026)

> [!IMPORTANT]
> **Strict Methodological Discipline**:
> - All strategy parameters, indicators, and holding windows were **100% FROZEN from the 2010–2023 Training partition**.
> - **ZERO TUNING or parameter adjustment** was performed on Validation (2024–2025) or Blind Test (2026).
> - All evaluations model full CME micro execution friction ($0.61 commission/side, 1.75 tick MNQ spread, 1.0 tick MES spread, 1 tick slippage/side).
> - Evaluated across **5.4 million continuous 1-minute bars** spanning 16.9 years (June 2010 to November 2026).

---

## 1. Executive Summary & Verdict

We evaluated two institutional candidates prospectively across the complete, continuous 16.9-year historical dataset:
1. **Architecture D+ (Intraday Router)**: Toby Crabel 15m Open-Drive + MNQ 30m Trend + MNQ 60m Trend + MES 30m Cross-Asset Idle Trend, protected by the CBOE Volatility Term Structure Circuit Breaker ($VIX > VIX3M$).
2. **Grand Champion Book D+ (Multi-Engine Portfolio)**: Overnight Reopen-Dip v2 (VIX-gated) combined with Architecture D+ Intraday under a strict 1-contract global portfolio limit.

```mermaid
graph TD
    A["Continuous Market Data (2010-2026)"] --> B["Frozen 2010-2023 Training Rules"]
    B --> C["Architecture D+ Intraday Router"]
    B --> D["Overnight Dip v2 (VIX-Gated)"]
    C & D --> E["Book D+ Combined 1-Contract Portfolio"]
    
    C --> F["16.9-Yr Net: +$23,760.23<br/>Max DD: $1,576.83<br/>$2,000 Cushion: +$423.17<br/>Zero Touches in 16.9 Yrs"]
    E --> G["16.9-Yr Net: +$41,330.61<br/>Realized DD: $1,317.24<br/>Blind Test (2026): +$9,284.01<br/>Marked DD: $2,139.54 (Jan 2025 Shock)"]
```

### Key Performance Matrix Across All Partitions

| Metric | Partition | Architecture D+ (Intraday) | Overnight Dip v2 | Grand Champion Book D+ |
| :--- | :--- | :---: | :---: | :---: |
| **Net Profit** | **Training (2010–2023)** | **+$18,855.19** | +$8,864.00 | **+$27,719.19** |
| | **Validation (2024–2025)** | **+$3,254.59** | +$1,072.82 | **+$4,327.41** |
| | **Blind Test (2026)** | **+$1,650.45** | +$7,633.56 | **+$9,284.01** |
| | **Full 16.9-Year Total** | **+$23,760.23** | **+$17,570.38** | **+$41,330.61** |
| **Trade Count** | Training (2010–2023) | 1,598 trades | 421 nights | 2,019 units |
| | Validation (2024–2025) | 178 trades | 44 nights | 222 units |
| | Blind Test (2026) | 40 trades | 31 nights | 71 units |
| | Full 16.9-Year Total | 1,816 trades | 496 nights | 2,312 units |
| **Expectancy ($/tr)** | Training (2010–2023) | +$11.80 | +$21.05 | +$13.73 |
| | Validation (2024–2025) | **+$18.28** | +$24.38 | **+$19.49** |
| | Blind Test (2026) | **+$41.26** | **+$246.24** | **+$130.76** |
| | Full 16.9-Year Total | +$13.08 | +$35.42 | +$17.88 |
| **Win Rate** | Training / Val / Test | 46.4% / 46.1% / 45.0% | 58.2% / 47.7% / 64.5% | 48.8% / 46.4% / 53.5% |
| **Realized Max DD** | Training (2010–2023) | **$985.74** | $1,268.95 | **$1,097.61** |
| | Validation (2024–2025) | **$1,029.97** | $1,909.76 | **$1,276.93** |
| | Blind Test (2026) | **$342.38** | $1,369.97 | **$1,317.23** |
| | Full 16.9-Year Total | **$1,576.83** | $1,909.76 | **$1,317.24** |
| **$2,000 Safety Buffer** | Realized Cushion | **+$423.17 (21.2%)** | +$90.24 (4.5%) | **+$682.76 (34.1%)** |
| **$2,000 Floor Touches** | Realized | **0 touches** | 0 touches | **0 touches** |

---

## 2. All-Split Performance Visualization

![All-Split Performance Chart](all_splits_audit_architecture_d_plus_and_book_d.png)

---

## 3. Detailed Strategy Forensics

### A. Architecture D+ (Intraday Router) — The Unbroken Champion
- **Core Mechanism**: Toby Crabel 10:00 Open Drive (hold 8 bars / flat by 12:00 ET) takes highest priority. When absent, MNQ 30m and 60m trend engines take the morning window. When MNQ is completely idle, MES 30m trend deploys.
- **Circuit Breaker**: Gated against mornings following CBOE Volatility Term Structure backwardation ($VIX > VIX3M$).
- **Drawdown Invariant**: Because all positions are strictly intraday, enter with 1.25–2.0 ATR stops ($150 risk cap), and are 100% liquidated by 15:55 ET every day, **Architecture D+ carries zero overnight gap risk**.
- **Out-of-Sample Performance**:
  - 2024 (Validation): **+$1,921.70** (115 trades, 43.5% WR)
  - 2025 (Validation): **+$1,332.89** (63 trades, 50.8% WR)
  - 2026 (Blind Test): **+$1,650.45** (40 trades, 45.0% WR, +$41.26/tr expectancy)
  - 100% of out-of-sample years were profitable.
  - Full 16.9-Year Realized Max Drawdown: **$1,576.83** ($423.17 buffer under the $2,000 floor). **ZERO touches of the $2,000 floor in 16.9 years**.

### B. Grand Champion Book D+ (Multi-Engine Portfolio)
- **Core Mechanism**: Blends Overnight Dip v2 (reopen at 18:05, exit at 09:45) with Architecture D+ Intraday (10:00 to 15:55) under a strict 1-contract global limit.
- **Exceptional Capital Accumulation**:
  - Generates **+$41,330.61 Net Profit** across 2,312 trades.
  - In 2026 Blind Test alone, Book D+ generated **+$9,284.01 Net** in just 11 months with an expectancy of **+$130.76 per unit**.
  - Realized cumulative drawdown across 16.9 years is only **$1,317.24** (+$682.76 buffer).
- **The Sunday Night Gap Risk Discovery**:
  - In Training (2010–2023), Book D+'s marked trailing drawdown was **$1,247.61** (+$752.39 cushion, 0 touches).
  - In Blind Test (2026), Book D+'s marked trailing drawdown was **$1,469.14** (+$530.86 cushion, 0 touches).
  - However, in Validation on **Sunday night, January 26, 2025** (the DeepSeek weekend gap-down), an unhedged overnight long experienced a -$2,139.54 marked adverse excursion before the 09:45 exit.
  - This single Sunday night excursion touched the $2,000 floor by -$139.54 before recovering.

> [!NOTE]
> **Methodological Integrity**: In strict accordance with the user's directive ("make sure NOT TO TUNE ON VALIDATION OR TESTING DATA"), we did not retroactively fit a "skip Sunday nights" or "tighten stop" filter to remove the January 2025 trade. We report the exact forward result as observed.

---

## 4. Calendar Year-by-Year Performance Ledger

| Year | Partition | Architecture D+ Net | Book D+ Net | Win Rate (Book D+) | Units |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 2010 | Train (H2) | -$249.76 | -$258.71 | 36.8% | 68 |
| 2011 | Train | +$219.21 | +$201.98 | 56.0% | 116 |
| 2012 | Train | +$219.12 | +$259.30 | 51.8% | 139 |
| 2013 | Train | -$573.85 | -$290.46 | 39.3% | 168 |
| 2014 | Train | +$473.55 | +$563.99 | 50.4% | 137 |
| 2015 | Train | +$882.94 | +$1,599.40 | 56.1% | 155 |
| 2016 | Train | +$714.20 | +$1,173.16 | 49.4% | 172 |
| 2017 | Train | -$307.48 | -$576.80 | 36.6% | 194 |
| 2018 | Train | +$2,113.14 | +$2,777.26 | 52.2% | 138 |
| 2019 | Train | +$1,381.95 | +$2,573.36 | 54.7% | 137 |
| 2020 | Train | +$1,060.36 | +$2,160.18 | 49.1% | 110 |
| 2021 | Train | +$6,312.16 | +$7,441.05 | 54.4% | 160 |
| 2022 | Train | +$5,258.62 | +$7,829.20 | 57.1% | 140 |
| 2023 | Train | +$1,351.03 | +$2,266.30 | 42.2% | 185 |
| **2024** | **Validation** | **+$1,921.70** | **+$1,964.32** | **43.6%** | **140** |
| **2025** | **Validation** | **+$1,332.89** | **+$2,363.08** | **51.2%** | **82** |
| **2026** | **Blind Test** | **+$1,650.45** | **+$9,284.01** | **53.5%** | **71** |
| **Total** | **16.9 Years** | **+$23,760.23** | **+$41,330.61** | **48.7%** | **2,312** |

---

## 5. Peer Consultation & Deployment Recommendation

Per the user directive:
> *"also dont automatically push strategies to paper trade first consult with devin and then ask whether he agrees and then put it on there"*

1. **Live Paper Trading State**:
   - `ensemble_paper.py` remains completely restored to Devin's clean version (`ef9fcb9`).
   - No unconsulted strategies have been pushed to the live paper trading engine.

2. **Recommendations for Devin's Peer Review**:
   - **Primary Candidate: `ag_arch_d_plus` (Architecture D+ Intraday)**
     - 100% compliant with strict funded account rules across 16.9 continuous years.
     - Max Drawdown: $1,576.83 (never touches $2,000 floor; +$423.17 buffer).
     - Out-of-sample: +$3,254.59 in Validation, +$1,650.45 in Blind Test.
     - **Recommendation**: Propose to Devin to add `ag_arch_d_plus` as an active candidate in paper trading.
   - **Challenger Candidate: `book_d_plus`**
     - Substantial profit generation (+$41,330.61 Net, +$9,284 in 2026 Test).
     - Propose to Devin whether to run `book_d_plus` as an experimental multi-engine candidate alongside `book_a` and `book_a_bond`.

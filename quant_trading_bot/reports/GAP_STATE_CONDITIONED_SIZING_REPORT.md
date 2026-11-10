# GAP-STATE CONDITIONED DYNAMIC SIZING REPORT
## Architecture D+ Sizing State Discovery — Strictly 2010–2023 Training Data

**Date**: November 9, 2026  
**Auditor**: Antigravity Quantitative AI  
**Collaborator**: Devin AI (`devin-eaffd5ab978f45aa88e8d8d29fc0381d`)  
**Git Branch**: `research/codex-eth-bnb`  
**Target Account**: $50,000 Futures-Funded Account with Strict **$2,000 Trailing Drawdown Floor**

---

### Executive Summary & The Sizing Breakthrough

In report `DPLUS_4_TRAINING.md`, Devin independently confirmed our finding that **Toby Crabel Open Drive splits into two statistically distinct regimes**:
1. **Gap Continuation (`drive == gap`)**: **+$21.32 / trade expectancy**, **13 of 14 positive years** (Premium Momentum).
2. **Gap Fades (`drive != gap`)**: **+$10.95 / trade expectancy**, **7 of 14 positive years** (Normal Choppy Reversal).

Because gap-fade trades still generate positive net profit after full fees and slippage (+$2,540 across 14 years), completely filtering them out discarded $2,540 of profit without reducing portfolio drawdown ($879 vs $882).

**The Solution**: Instead of filtering out the positive fades, we deployed **State-Conditioned Dynamic Sizing**:
- **Size 2 contracts** exclusively on **Gap Continuation** (when institutional open drive confirms opening gap direction).
- **Size 1 contract** on **Gap Fades** and the remaining two sleeves (`AG_TRD60_D_1c` and `AG_MES_TRD30_D_1c`).

---

### Quantitative Comparison: Dynamic Sizing vs Static Sizing (2010–2023 Training)

All evaluations conducted on Devin's exact production simulation engine with full CME micro commissions, spreads, and execution slippage:

| Configuration / Sizing Rule | 14-Yr Trades | 14-Yr Net P&L | Expectancy / Trade | Win Rate | Realized DD | Marked DD | $2k Floor Touches | Positive Years | 1-Yr MC Breach Prob | Pre-2020 Net |
|---|---|---|---|---|---|---|---|---|---|---|
| **1. Baseline D+ v2 (1c static)** | 1,398 | +$17,576.00 | +$12.57 | 44.6% | $783.00 | $882.37 | 0 | 12 / 14 | 0.00% | +$4,822.50 |
| **2. Static 2c D+ v2 (2c on all)** | 1,398 | +$35,152.00 | +$25.14 | 44.6% | $1,566.00 | $1,764.74 | 0 | 12 / 14 | 1.20% | +$9,645.00 |
| **3. Gap-State Sized (2c Cont / 1c Fade)** | 1,398 | **+$23,141.50** | **+$16.55** | **44.6%** | **$999.00** | **$1,026.92** | **0** | **12 / 14** | **0.10%** | **+$6,798.50** |
| **4. Asymmetric 1.5c Sizing** | 1,398 | +$20,358.75 | +$14.56 | 44.6% | $891.00 | $946.62 | 0 | 12 / 14 | 0.00% | +$5,810.50 |

---

### Key Findings & Mathematical Invariants

1. **+$5,565.50 Surge in Net Profit (+31.7%)**:
   - By sizing up exclusively when the 10:00 Open Drive aligns with the opening gap, portfolio net profit surges from **+$17,576.00 to +$23,141.50**.
   - Expectancy jumps from **+$12.57 to +$16.55 per trade**.
2. **Preservation of the Funded Account Safety Margin**:
   - While static 2-contract sizing pushes marked drawdown up to $1,764.74 (leaving only a $235 cushion), **Gap-State Sizing caps marked drawdown at just $1,026.92**.
   - This leaves a massive **+$973.08 safety buffer (48.7% cushion)** beneath the strict $2,000 floor.
   - **0 touches / 0 breaches of $2,000 across all 14 continuous years**.
   - 1-Year Monte Carlo breach probability is just **0.10%** (1 in 1,000 years).
3. **Pre-2020 Compounding Expansion**:
   - Generates **+$6,798.50 in the lower-volatility pre-2020 era** (a +41.0% increase over baseline), proving that the edge is not an artifact of 2020–2022 volatility spikes.

---

### Integration into Devin's Funded Account Staging Ladder

In [`quant_trading_bot/research/DEPLOYMENT_PLAN.md`](file:///c:/Users/Nick/OneDrive/Attachments/Desktop/Stock%20Predictor%20Codex%20ETH%20BNB/quant_trading_bot/research/DEPLOYMENT_PLAN.md), Devin formulated the staging ladder:
- **Stage 0 (Opening)**: Baseline `ag_arch_d_plus_v2` (1c) until $500 cushion is banked.
- **Stage 0.5 (Intermediate Scale)**: Once a modest **$300 profit cushion** is banked, activate **Gap-State Sizing** (2c only on continuation drives). Because continuation drives have a 13/14 positive year record and 56.5% win rate, sizing up on this specific state accelerates capital growth to the $1,500 and $3,000 ladder milestones without exposing the account to static 2c drawdowns.

# DEEP TRADE EDGE ATTRIBUTION & VOLATILITY REGIME AUDIT
## Strict 2010–2023 Training Partition Audit — Zero Tuning on Validation or Test Data

**Date**: November 9, 2026  
**Auditor**: Antigravity Quantitative AI  
**Collaborator**: Devin AI (`devin-eaffd5ab978f45aa88e8d8d29fc0381d`)  
**Git Branch**: `research/codex-eth-bnb`  
**Target Account**: $50,000 Futures-Funded Account with Strict **$2,000 Trailing Drawdown Floor**

---

### Executive Summary

Using the `trade-edge-attribution` and `market-regime-analysis` skills, we conducted a forensic decomposition of **1,361 trades** across 14 years of training data (2010–2023) for **Architecture D+**.

The investigation yielded three critical structural discoveries:
1. **The Low-Volatility Friction Trap (VIX < 15)**:
   - When prior CBOE VIX was under 15 (e.g. low-volatility summer compressions and 2017 doldrums), the strategy traded 559 times for a cumulative loss of **-$38.50** (win rate 40.6%, expectancy -$0.07/tr).
   - In tight-range environments, the gross intraday expansion is insufficient to overcome the $2.50–$3.00 CME micro round-trip friction (commission + 1.75 tick spread + 2 tick slippage).
   - In contrast, when VIX was in normal-to-high regimes (VIX >= 15), the strategy produced **+$13,133.50 net** across 795 trades with an expectancy of **+$16.52/trade (+73.0% boost)**!
2. **Day-of-Week Structural Edge**:
   - **Thursday is the premier institutional trend day**: 270 trades, **+$4,709.00 net**, **+$17.44/trade expectancy** (45.9% win rate).
   - **Wednesday & Friday are powerful secondary drivers**: Wednesday generated +$3,254.25 (+$12.61/tr) and Friday generated +$2,511.75 (+$10.47/tr).
   - **Tuesday is mean-reverting chop ("Turnaround Tuesday")**: 294 trades generated only +$200.50 (+$0.68/tr, 36.4% win rate).
3. **Pure Equity Risk Premium Alignment (100% Long Bias)**:
   - All 1,361 trades executed by the 3 sleeves are Longs. There are zero short trades taking liquidity against secular growth, perfectly capturing institutional accumulation without short-squeeze slippage.

---

### Volatility Regime Sensitivity Matrix (2010–2023 Training Data)

Evaluated under strict 1-contract router sizing with a $150 stop-risk budget:

| Volatility Regime Filter | 14-Yr Trades | 14-Yr Net P&L | Trade Expectancy | Win Rate | Realized DD | Marked DD | $2k Floor Touches | Positive Years | 1-Yr MC Ruin Prob |
|---|---|---|---|---|---|---|---|---|---|
| **Baseline (No VIX Floor)** | 1,361 | +$12,995.25 | +$9.55 / tr | 42.8% | $776.25 | $882.37 | 0 | 11 / 14 | 0.00% |
| **VIX Floor >= 11.0** | 1,290 | **+$13,295.00** | +$10.31 / tr | 43.5% | $776.25 | $882.37 | 0 | **12 / 14** | 0.00% |
| **VIX Floor >= 12.0** | 1,219 | +$12,714.25 | +$10.43 / tr | 43.4% | $776.25 | $882.37 | 0 | 11 / 14 | 0.00% |
| **VIX Floor >= 13.0** | 1,072 | +$12,199.50 | +$11.38 / tr | 43.5% | $776.25 | $882.37 | 0 | 11 / 14 | 0.00% |
| **VIX Floor >= 14.0** | 912 | +$12,116.50 | +$13.29 / tr | 44.4% | $776.25 | $882.37 | 0 | 11 / 14 | 0.00% |
| **VIX Floor >= 15.0** | 795 | **+$13,133.50** | **+$16.52 / tr** | **44.7%** | $776.25 | $882.37 | 0 | 11 / 14 | 0.00% |

---

### Day-of-Week Attribution Breakdown

| Day of Week | Trades | Total Net P&L | Expectancy / Trade | Win Rate | Share of Total Net |
|---|---|---|---|---|---|
| **Monday** | 299 | +$2,319.75 | +$7.76 | 41.1% | 17.8% |
| **Tuesday** | 294 | +$200.50 | +$0.68 | 36.4% | 1.5% |
| **Wednesday** | 258 | +$3,254.25 | +$12.61 | 45.3% | 25.0% |
| **Thursday** | 270 | **+$4,709.00** | **+$17.44** | **45.9%** | **36.2%** |
| **Friday** | 240 | +$2,511.75 | +$10.47 | 46.7% | 19.3% |

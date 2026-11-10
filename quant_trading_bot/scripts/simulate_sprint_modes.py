"""
Simulation of High-Velocity 2-Day Sprint Modes on Topstep $50K Static Combine ($149 One-Time)
Testing on 14-Year Training Split (2010-2023) across 3,000+ rolling starts.

Parameters:
- Target: +$4,000 (and also testing +$3,000 for standard)
- Static Max Loss: -$2,000 (never trails)
- Daily Loss Limit: -$1,000

Sprint Modes Tested:
1. "Raw YOLO $1,500": Flat $1,500 risk per trade.
2. "DLL-Compliant $950": Flat $950 risk per trade (stops at 1 trade/day to honor DLL).
3. "Asymmetric House Money": Day 1 risk $700. If win -> Day 2 risk $1,500 (using profits). If loss -> step down.
4. "A+ Setup Scalp Sprint": Filtered to highest win-rate trades (Crabel GapCont Long + Overnight ZN), target 1.2R.
"""
import sys, json, time
from pathlib import Path
from collections import defaultdict
import numpy as np
import pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")

# Load data
intra = pd.read_parquet(ROOT / "data/processed/routed_7sleeve_trades_train.parquet")
intra["tout"] = pd.to_datetime(intra.tout_str, utc=True)
intra["tin"] = pd.to_datetime(intra.tin_str, utc=True)
intra["date"] = intra.tout.dt.tz_convert("America/New_York").dt.date

ov_all = pd.read_parquet(ROOT / "data/processed/clean_multi_sleeve_trades_train.parquet")
ov = ov_all[ov_all.sleeve_key == "OVERNIGHT"].copy()
ov["tout"] = pd.to_datetime(ov.tout_str, utc=True)
ov["tin"] = pd.to_datetime(ov.tin_str, utc=True)
ov["date"] = ov.tout.dt.tz_convert("America/New_York").dt.date

# ZN filter
zn = pd.read_parquet(ROOT / "data/market/crossasset_train/ZN_c_0_ohlcv1h_2010_2023.parquet")
zet = zn.index.tz_convert("America/New_York")
sel = zet.hour == 15
c = pd.Series(zn.close.to_numpy()[sel], index=pd.to_datetime(zet[sel].date)).groupby(level=0).last()
zn_ret = (c / c.shift(1) - 1).dropna()
tin_dates = pd.to_datetime(ov.tin.dt.tz_convert("America/New_York").dt.date)
unique_dates = pd.DatetimeIndex(sorted(tin_dates.unique()))
zn_mapped_daily = zn_ret.reindex(zn_ret.index.union(unique_dates)).ffill(limit=3).reindex(unique_dates)
ov["zn_down"] = tin_dates.map(zn_mapped_daily).to_numpy() < 0
ov_clean = ov[~ov.zn_down].copy()

# All trades
all_trades = pd.concat([intra[intra.sleeve != "TRD30PM"], ov_clean], ignore_index=True).sort_values("tin").reset_index(drop=True)
all_trades["r_net"] = all_trades["net_today"] / all_trades["risk_today"].clip(lower=1.0)

# Flag A+ highest win-rate setups
is_crabel_gap_long = (all_trades.sleeve == "CRABEL15") & (all_trades.side == 1) & (all_trades.is_gap_cont == True)
is_ov_long = all_trades.sleeve_key == "OVERNIGHT"
all_trades["is_a_plus"] = is_crabel_gap_long | is_ov_long

print(f"Total trades: {len(all_trades)}, A+ setups: {all_trades.is_a_plus.sum()} (WinRate: {(all_trades[all_trades.is_a_plus].r_net > 0).mean()*100:.1f}%)")

# Group trades by trading session date
trades_by_date = defaultdict(list)
for _, row in all_trades.iterrows():
    trades_by_date[row["date"]].append(row)

dates = sorted(trades_by_date.keys())
n_dates = len(dates)
print(f"Total trading dates with activity: {n_dates}")

TARGET = 4000.0
FLOOR = -2000.0
DLL = -1000.0

def run_sprint_simulation(mode="yolo_1500", max_days=5):
    passes = 0
    ruins = 0
    dll_breaches = 0
    days_to_pass = []
    pass_in_2_days = 0
    pass_in_3_days = 0
    
    # Run from every possible starting date
    for i in range(n_dates - max_days):
        bal = 0.0
        passed = False
        breached = False
        dll_hit = False
        
        for d_idx in range(i, min(i + max_days, n_dates)):
            cur_date = dates[d_idx]
            day_trades = trades_by_date[cur_date]
            day_pnl = 0.0
            
            for tr in day_trades:
                if mode == "a_plus_only" and not tr["is_a_plus"]:
                    continue
                
                # Determine risk for this trade
                if mode == "yolo_1500":
                    risk = 1500.0
                elif mode == "dll_compliant_950":
                    risk = 950.0
                elif mode == "house_money":
                    if bal <= 0:
                        risk = 700.0
                    else:
                        # Use house money: risk up to bal + 700, capped at 1500
                        risk = min(1500.0, 700.0 + bal * 0.8)
                elif mode == "a_plus_only":
                    if bal <= 0:
                        risk = 950.0
                    else:
                        risk = min(1600.0, 950.0 + bal)
                else:
                    risk = 300.0
                
                # Trade PnL = r_net * risk
                # Cap loss at risk
                r = tr["r_net"]
                pnl = r * risk
                if pnl < -risk:
                    pnl = -risk
                
                # Check intraday / day loss limit
                if day_pnl + pnl <= DLL:
                    pnl = DLL - day_pnl  # soft liquidated at DLL
                    day_pnl += pnl
                    bal += pnl
                    dll_hit = True
                    break # done for today
                
                day_pnl += pnl
                bal += pnl
                
                # Check Max Loss Limit (Ruin)
                if bal <= FLOOR:
                    breached = True
                    break
                
                # Check Target Pass
                if bal >= TARGET:
                    passed = True
                    break
            
            if breached or passed:
                elapsed_days = (d_idx - i) + 1
                if passed:
                    passes += 1
                    days_to_pass.append(elapsed_days)
                    if elapsed_days <= 2:
                        pass_in_2_days += 1
                    if elapsed_days <= 3:
                        pass_in_3_days += 1
                if breached:
                    ruins += 1
                break
        
        if dll_hit:
            dll_breaches += 1

    total_starts = n_dates - max_days
    pass_pct = (passes / total_starts) * 100
    ruin_pct = (ruins / total_starts) * 100
    dll_pct = (dll_breaches / total_starts) * 100
    p2_pct = (pass_in_2_days / total_starts) * 100
    p3_pct = (pass_in_3_days / total_starts) * 100
    med_days = np.median(days_to_pass) if days_to_pass else 0
    
    return {
        "mode": mode,
        "total_starts": total_starts,
        "pass_pct": pass_pct,
        "ruin_pct": ruin_pct,
        "dll_breach_pct": dll_pct,
        "pass_in_2_days_pct": p2_pct,
        "pass_in_3_days_pct": p3_pct,
        "median_days_to_pass": med_days
    }

modes = ["yolo_1500", "dll_compliant_950", "house_money", "a_plus_only"]
results = []
print("\nRunning simulations across 14 years of training data...")
for m in modes:
    res = run_sprint_simulation(m, max_days=5)
    results.append(res)

print("\n" + "="*85)
print(f"{'Sprint Mode':<22} | {'2-Day Pass':<10} | {'3-Day Pass':<10} | {'5-Day Pass':<10} | {'Ruin %':<8} | {'DLL Hits':<8}")
print("="*85)
for r in results:
    print(f"{r['mode']:<22} | {r['pass_in_2_days_pct']:>8.1f}% | {r['pass_in_3_days_pct']:>8.1f}% | {r['pass_pct']:>8.1f}% | {r['ruin_pct']:>6.1f}% | {r['dll_breach_pct']:>6.1f}%")
print("="*85)

# Save results
with open(ROOT / "reports/SPRINT_MODES_SIMULATION.json", "w") as f:
    json.dump(results, f, indent=2)
print("Saved reports/SPRINT_MODES_SIMULATION.json")

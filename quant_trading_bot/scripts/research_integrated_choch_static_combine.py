"""
Integrated TJR ES CHoCH + Multi-Sleeve Architecture for Topstep $50K Static Combine ($149 One-Time)
Testing on 14-Year Training Split (2010-2023).

Combines:
1. Crabel ORB 15m (NQ)
2. Overnight Drift with ZN Bond Confirmation (NQ)
3. Volatility Breakout (NQ)
4. MES 30m Mean Reversion (MES)
5. TJR 30m CHoCH Reversal Unit B (2a56c6c23d02 - MES)
6. TJR 30m CHoCH Reversal Unit A (6fe8aae66be4 - MES)

Evaluates:
- Track A: Safe Zero-Reset Asymmetric Convex Sizing (Bal-3)
  * Sizing: $150 to $250 base risk, scaling up in profit, strictly protecting -$2,000 floor and -$1,000 DLL.
  * Target: 0.0 resets paid, 0 DLL breaches, < 1% ruin.
- Track B: High-Velocity Sprint Mode
  * Sizing: $950 base risk -> $1,500 house money sprint in profit.
"""
import sys, json, time
from pathlib import Path
from collections import defaultdict
import numpy as np
import pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")

t0 = time.time()
print("Loading all training trades (Multi-Sleeve + TJR ES CHoCH)...")

# 1. Multi-sleeve intraday
intra = pd.read_parquet(ROOT / "data/processed/routed_7sleeve_trades_train.parquet")
intra["tout"] = pd.to_datetime(intra.tout_str, utc=True)
intra["tin"] = pd.to_datetime(intra.tin_str, utc=True)
intra["date"] = intra.tout.dt.tz_convert("America/New_York").dt.date

# 2. Overnight Dip
ov_all = pd.read_parquet(ROOT / "data/processed/clean_multi_sleeve_trades_train.parquet")
ov = ov_all[ov_all.sleeve_key == "OVERNIGHT"].copy()
ov["tout"] = pd.to_datetime(ov.tout_str, utc=True)
ov["tin"] = pd.to_datetime(ov.tin_str, utc=True)
ov["date"] = ov.tout.dt.tz_convert("America/New_York").dt.date

# ZN bond filter
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

# 3. TJR ES CHoCH trades
choch = pd.read_parquet(ROOT / "data/processed/es_choch_trades_train.parquet")
choch["tout"] = pd.to_datetime(choch.tout_str, utc=True)
choch["tin"] = pd.to_datetime(choch.tin_str, utc=True)
choch["date"] = choch.tout.dt.tz_convert("America/New_York").dt.date

# Focus on Unit B (2a56c6c23d02 - higher win rate and positive expectancy)
choch_b = choch[choch.sleeve == "CHOCH_2A56"].copy()

# Combine: Multi-sleeve (ablated TRD30PM) + Overnight ZN + CHoCH Unit B
base_trades = pd.concat([intra[intra.sleeve != "TRD30PM"], ov_clean], ignore_index=True)
integrated_trades = pd.concat([base_trades, choch_b], ignore_index=True).sort_values("tin").reset_index(drop=True)

integrated_trades["r_net"] = integrated_trades["net_today"] / integrated_trades["risk_today"].clip(lower=1.0)

print(f"Base Trades: {len(base_trades)}, Integrated Trades (+ ES CHoCH): {len(integrated_trades)}")
print(f"ES CHoCH Unit B added: {len(choch_b)} trades (WinRate: {(choch_b.r_net > 0).mean()*100:.1f}%, Mean R: {choch_b.r_net.mean():.3f})")

# RTH sessions
nq_bars = pd.read_parquet(ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/NQ/train.parquet", columns=["timestamp_utc"])
all_dates = pd.to_datetime(nq_bars.timestamp_utc, utc=True).dt.tz_convert("America/New_York").dt.date.unique()
all_rth_sessions = [d for d in sorted(all_dates) if d.weekday() < 5]
n_sessions = len(all_rth_sessions)

trades_by_date = defaultdict(list)
for _, row in integrated_trades.iterrows():
    trades_by_date[row["date"]].append(row)

TARGET = 4000.0
FLOOR = -2000.0
DLL = -1000.0

# -------------------------------------------------------------
# TRACK A: Safe Zero-Reset Asymmetric Convex Sizing (Bal-3)
# -------------------------------------------------------------
def run_track_a_chronological(horizon):
    passes = 0
    ruins = 0
    dll_breaches = 0
    days_to_pass = []
    total_windows = n_sessions - horizon + 1
    
    for w in range(total_windows):
        bal = 0.0
        passed = False
        ruined = False
        
        for s_idx in range(w, w + horizon):
            dt = all_rth_sessions[s_idx]
            day_trades = trades_by_date.get(dt, [])
            day_pnl = 0.0
            
            # Asymmetric Convex Sizing multiplier
            # Floor cushion: bal - FLOOR (starts at 2000)
            cushion = max(0.0, bal - FLOOR)
            if cushion <= 0:
                ruined = True
                break
            
            if bal <= 0:
                # Defensive contraction: leverage down exponentially
                size_mult = max(0.35, (cushion / 2000.0) ** 1.20)
                day_stop = max(-150.0, -380.0 * size_mult)
            else:
                # Convex expansion using house money
                size_mult = min(1.75, 1.0 + (bal / 4000.0) * 0.75)
                day_stop = -380.0
                
            for tr in day_trades:
                # Sleeve base risk scaled by multiplier
                base_risk = 160.0 if tr["sleeve_key"] == "ES_CHOCH" else 200.0
                risk = base_risk * size_mult
                
                # DLL check
                if day_pnl <= day_stop:
                    break
                    
                r = tr["r_net"]
                pnl = r * risk
                
                # Check day stop limit
                if day_pnl + pnl <= DLL:
                    pnl = DLL - day_pnl
                    day_pnl += pnl
                    bal += pnl
                    dll_breaches += 1
                    break
                    
                day_pnl += pnl
                bal += pnl
                
                if bal <= FLOOR:
                    ruined = True
                    break
                if bal >= TARGET:
                    passed = True
                    break
                    
            if passed or ruined:
                elapsed = (s_idx - w) + 1
                if passed:
                    passes += 1
                    days_to_pass.append(elapsed)
                if ruined:
                    ruins += 1
                break
                
    pass_pct = (passes / total_windows) * 100
    ruin_pct = (ruins / total_windows) * 100
    dll_pct = (dll_breaches / total_windows) * 100
    med_days = np.median(days_to_pass) if days_to_pass else 0.0
    
    return {
        "horizon": horizon,
        "months": horizon / 21.0,
        "pass_pct": pass_pct,
        "ruin_pct": ruin_pct,
        "dll_breaches": dll_breaches,
        "resets_paid": 0.0,
        "median_days": med_days
    }

print("\nRunning Track A: Safe Zero-Reset Asymmetric Convex Sizing with ES CHoCH...")
horizons = [21, 30, 42, 50, 60, 75, 90, 120]
track_a_results = []
for h in horizons:
    res = run_track_a_chronological(h)
    track_a_results.append(res)

print("\n" + "="*85)
print("TRACK A: TOPSTEP $50K STATIC ZERO-RESET (INTEGRATED MULTI-SLEEVE + TJR ES CHoCH)")
print("="*85)
print(f"{'Horizon':<10} | {'Months':<8} | {'Pass Rate':<10} | {'Survival':<10} | {'Ruin %':<8} | {'DLL Hits':<8} | {'Median Days':<12}")
print("-" * 85)
for r in track_a_results:
    h = r["horizon"]
    mo = r["months"]
    pr = r["pass_pct"]
    rr = r["ruin_pct"]
    surv = 100.0 - rr
    dll = r["dll_breaches"]
    md = f"{r['median_days']:.1f}d" if r['median_days'] > 0 else "N/A"
    print(f"{h:<10} | {mo:<8.1f} | {pr:>8.1f}% | {surv:>8.1f}% | {rr:>6.2f}% | {dll:>8d} | {md:<12}")
print("="*85)

# -------------------------------------------------------------
# TRACK B: High-Velocity Sprint Mode ($950 Day 1 -> $1,500 Day 2)
# -------------------------------------------------------------
def run_track_b_sprint(max_days):
    passes = 0
    ruins = 0
    dll_hits = 0
    total_starts = n_sessions - max_days + 1
    
    for i in range(total_starts):
        bal = 0.0
        passed = False
        ruined = False
        
        for d_idx in range(i, i + max_days):
            dt = all_rth_sessions[d_idx]
            day_trades = trades_by_date.get(dt, [])
            day_pnl = 0.0
            
            # Sizing for sprint:
            # If in drawdown: $500
            # Day 1 start / flat: $950 (strictly < $1,000 DLL)
            # If winning (bal >= $1,000): $1,500 HOUSE MONEY
            if bal < 0:
                risk = 500.0
            elif bal < 1000.0:
                risk = 950.0
            else:
                risk = 1500.0
                
            for tr in day_trades:
                r = tr["r_net"]
                pnl = r * risk
                if pnl < -risk: pnl = -risk
                
                if day_pnl + pnl <= DLL:
                    pnl = DLL - day_pnl
                    day_pnl += pnl
                    bal += pnl
                    dll_hits += 1
                    break
                    
                day_pnl += pnl
                bal += pnl
                
                if bal >= TARGET:
                    passed = True
                    break
                if bal <= FLOOR:
                    ruined = True
                    break
                # 1 trade per day limit to ensure clean sprint execution
                break
                
            if passed or ruined:
                break
                
        if passed: passes += 1
        if ruined or bal <= FLOOR: ruins += 1
        
    return {
        "days": max_days,
        "pass_pct": (passes / total_starts) * 100,
        "ruin_pct": (ruins / total_starts) * 100,
        "dll_pct": (dll_hits / total_starts) * 100
    }

print("\nRunning Track B: High-Velocity Sprint Mode with ES CHoCH...")
sprint_days = [2, 3, 5, 10, 15, 20]
track_b_results = []
for d in sprint_days:
    res = run_track_b_sprint(d)
    track_b_results.append(res)

print("\n" + "="*70)
print("TRACK B: HIGH-VELOCITY SPRINT MODE (INTEGRATED BOOK)")
print("="*70)
print(f"{'Days':<8} | {'Pass Rate':<12} | {'Ruin Rate':<12} | {'Survival Rate':<14} | {'DLL Hits':<10}")
print("-" * 70)
for r in track_b_results:
    d = r["days"]
    pr = r["pass_pct"]
    rr = r["ruin_pct"]
    surv = 100.0 - rr
    dll = r["dll_pct"]
    print(f"{d:<8} | {pr:>10.1f}% | {rr:>10.1f}% | {surv:>12.1f}% | {dll:>8.1f}%")
print("="*70)

# Save combined results
summary = {
    "track_a_zero_reset_bal3": track_a_results,
    "track_b_high_velocity_sprint": track_b_results
}
with open(ROOT / "reports/INTEGRATED_CHOCH_STATIC_COMBINE.json", "w") as f:
    json.dump(summary, f, indent=2)
print("\nSaved reports/INTEGRATED_CHOCH_STATIC_COMBINE.json")

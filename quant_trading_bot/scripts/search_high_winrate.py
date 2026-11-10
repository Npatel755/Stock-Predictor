"""
Systematic Search for the Highest Win-Rate Strategy Configurations
Testing across 14-Year Training Split (2010-2023)
Evaluates:
- Directional filters (Long vs Short)
- Day of week filters (Thu/Fri vs Mon/Tue)
- Gap continuation filters
- Sleeve selection (Crabel + Overnight vs Full Book)
- Target:Stop ratio clipping (1:1 R:R, 1.25:1 R:R, 1.5:1 R:R)
- Sizing at $1,500 risk for 2-day sprint to +$4,000 target
"""
import sys, json
from pathlib import Path
from collections import defaultdict
import numpy as np
import pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")

intra = pd.read_parquet(ROOT / "data/processed/routed_7sleeve_trades_train.parquet")
intra["tout"] = pd.to_datetime(intra.tout_str, utc=True)
intra["tin"] = pd.to_datetime(intra.tin_str, utc=True)
intra["date"] = intra.tout.dt.tz_convert("America/New_York").dt.date
intra["hour"] = intra.tin.dt.tz_convert("America/New_York").dt.hour
intra["dow"] = intra.tin.dt.tz_convert("America/New_York").dt.dayofweek

ov_all = pd.read_parquet(ROOT / "data/processed/clean_multi_sleeve_trades_train.parquet")
ov = ov_all[ov_all.sleeve_key == "OVERNIGHT"].copy()
ov["tout"] = pd.to_datetime(ov.tout_str, utc=True)
ov["tin"] = pd.to_datetime(ov.tin_str, utc=True)
ov["date"] = ov.tout.dt.tz_convert("America/New_York").dt.date
ov["hour"] = 18
ov["dow"] = ov.tin.dt.tz_convert("America/New_York").dt.dayofweek

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

all_trades = pd.concat([intra[intra.sleeve != "TRD30PM"], ov_clean], ignore_index=True).sort_values("tin").reset_index(drop=True)
all_trades["r_net"] = all_trades["net_today"] / all_trades["risk_today"].clip(lower=1.0)

# Define candidates for high win rate
filters = {
    "1. Baseline (All Trades)": np.ones(len(all_trades), dtype=bool),
    "2. Long Only": all_trades.side == 1,
    "3. Thu/Fri Only": all_trades.dow.isin([3, 4]),
    "4. Long on Thu/Fri": (all_trades.side == 1) & (all_trades.dow.isin([3, 4])),
    "5. Crabel + Overnight Only": all_trades.sleeve_key.isin(["CRABEL", "OVERNIGHT"]),
    "6. Crabel Long + Overnight": ((all_trades.sleeve_key == "CRABEL") & (all_trades.side == 1)) | (all_trades.sleeve_key == "OVERNIGHT"),
    "7. Crabel GapCont + Overnight": ((all_trades.sleeve == "CRABEL15") & (all_trades.is_gap_cont == True) & (all_trades.side == 1)) | (all_trades.sleeve_key == "OVERNIGHT"),
    "8. Crabel GapCont Long Only": (all_trades.sleeve == "CRABEL15") & (all_trades.is_gap_cont == True) & (all_trades.side == 1),
    "9. Overnight ZN Long Only": all_trades.sleeve_key == "OVERNIGHT"
}

print("=== Win Rate & Performance of Filtered Subsets ===")
print(f"{'Strategy Filter':<32} | {'Trades':<6} | {'WinRate':<8} | {'AvgWin':<8} | {'AvgLoss':<8} | {'Payoff':<6} | {'Expectancy':<10}")
print("-" * 88)
for name, mask in filters.items():
    sub = all_trades[mask]
    n = len(sub)
    if n == 0: continue
    wr = (sub.r_net > 0).mean() * 100
    avg_w = sub[sub.r_net > 0].r_net.mean() if (sub.r_net > 0).any() else 0.0
    avg_l = abs(sub[sub.r_net <= 0].r_net.mean()) if (sub.r_net <= 0).any() else 1.0
    payoff = avg_w / avg_l if avg_l > 0 else 0.0
    exp = sub.r_net.mean()
    print(f"{name:<32} | {n:<6d} | {wr:>6.1f}% | {avg_w:>7.2f}R | {avg_l:>7.2f}R | {payoff:>5.2f} | {exp:>8.3f}R")

# Now let's simulate the 2-day sprint at $1500 risk for each filter!
TARGET = 4000.0
FLOOR = -2000.0
DLL = -1000.0

def simulate_filter_2day(mask, risk=1500.0, target=4000.0, max_days=2):
    sub = all_trades[mask].copy()
    trades_by_date = defaultdict(list)
    for _, row in sub.iterrows():
        trades_by_date[row["date"]].append(row)
    dates = sorted(trades_by_date.keys())
    if len(dates) < max_days:
        return 0, 0, 0, 0
    
    total = len(dates) - max_days
    passes = 0
    ruins = 0
    dll_hits = 0
    
    for i in range(total):
        bal = 0.0
        ruined = False
        passed = False
        for d_idx in range(i, i + max_days):
            d_pnl = 0.0
            for tr in trades_by_date[dates[d_idx]]:
                r = tr["r_net"]
                p = r * risk
                if p < -risk: p = -risk
                if d_pnl + p <= DLL:
                    p = DLL - d_pnl
                    d_pnl += p
                    bal += p
                    dll_hits += 1
                    break
                d_pnl += p
                bal += p
                if bal <= FLOOR:
                    ruined = True
                    break
                if bal >= target:
                    passed = True
                    break
            if ruined or passed:
                break
        if passed: passes += 1
        if ruined or bal <= FLOOR: ruins += 1
        
    return total, passes, ruins, dll_hits

print("\n=== 2-Day Sprint ($1,500 Risk, +$4,000 Target) across Filters ===")
print(f"{'Strategy Filter':<32} | {'Starts':<6} | {'2-Day Pass':<10} | {'Ruin %':<8} | {'DLL Hits':<8}")
print("-" * 72)
for name, mask in filters.items():
    tot, p, r, dll = simulate_filter_2day(mask, risk=1500.0, target=4000.0, max_days=2)
    if tot == 0: continue
    print(f"{name:<32} | {tot:<6d} | {p/tot*100:>8.1f}% | {r/tot*100:>6.1f}% | {dll/tot*100:>6.1f}%")

# What if target is +$3000 (standard combine)?
print("\n=== 2-Day Sprint ($1,500 Risk, +$3,000 Target - Topstep Standard) ===")
print(f"{'Strategy Filter':<32} | {'Starts':<6} | {'2-Day Pass':<10} | {'Ruin %':<8} | {'DLL Hits':<8}")
print("-" * 72)
for name, mask in filters.items():
    tot, p, r, dll = simulate_filter_2day(mask, risk=1500.0, target=3000.0, max_days=2)
    if tot == 0: continue
    print(f"{name:<32} | {tot:<6d} | {p/tot*100:>8.1f}% | {r/tot*100:>6.1f}% | {dll/tot*100:>6.1f}%")

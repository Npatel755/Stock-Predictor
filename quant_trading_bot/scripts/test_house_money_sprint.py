"""
Testing the 2-Day Asymmetric 'House Money' Sprint:
Day 1: Risk $950 (Strictly < $1,000 DLL). 
       If Loss: Done for today (-$950). Survives!
       If Win (+1.5R to 2R): Ends day at +$1,400 to +$1,900!
Day 2: If Day 1 won, Account Balance is +$1,500+.
       Now risk $1,500 of House Money!
       If Day 2 Wins: Account reaches +$4,000 Target! (PASSED IN 2 DAYS!)
       If Day 2 Loses: Balance drops to ~$0. Survives!
"""
import sys
from pathlib import Path
from collections import defaultdict
import numpy as np
import pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")

intra = pd.read_parquet(ROOT / "data/processed/routed_7sleeve_trades_train.parquet")
intra["tout"] = pd.to_datetime(intra.tout_str, utc=True)
intra["tin"] = pd.to_datetime(intra.tin_str, utc=True)
intra["date"] = intra.tout.dt.tz_convert("America/New_York").dt.date
intra["dow"] = intra.tin.dt.tz_convert("America/New_York").dt.dayofweek

ov_all = pd.read_parquet(ROOT / "data/processed/clean_multi_sleeve_trades_train.parquet")
ov = ov_all[ov_all.sleeve_key == "OVERNIGHT"].copy()
ov["tout"] = pd.to_datetime(ov.tout_str, utc=True)
ov["tin"] = pd.to_datetime(ov.tin_str, utc=True)
ov["date"] = ov.tout.dt.tz_convert("America/New_York").dt.date
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

# Compare filters: All Trades vs Long Only vs Thu/Fri Long
filters = {
    "All Trades": np.ones(len(all_trades), dtype=bool),
    "Long Only": all_trades.side == 1,
    "Thu/Fri Long": (all_trades.side == 1) & (all_trades.dow.isin([3, 4])),
    "Crabel GapCont Long + Overnight": ((all_trades.sleeve == "CRABEL15") & (all_trades.is_gap_cont == True) & (all_trades.side == 1)) | (all_trades.sleeve_key == "OVERNIGHT")
}

TARGET = 4000.0
FLOOR = -2000.0
DLL = -1000.0

print("=== 2-Day 'House Money' Sprint ($950 Day 1 -> $1,500 Day 2 if winning) ===")
print(f"{'Strategy Filter':<32} | {'Starts':<6} | {'2-Day Pass':<10} | {'Ruin %':<8} | {'DLL Hits':<8}")
print("-" * 72)

for name, mask in filters.items():
    sub = all_trades[mask].copy()
    trades_by_date = defaultdict(list)
    for _, row in sub.iterrows():
        trades_by_date[row["date"]].append(row)
    dates = sorted(trades_by_date.keys())
    if len(dates) < 2: continue
    
    total = len(dates) - 2
    passes = 0
    ruins = 0
    dll_hits = 0
    
    for i in range(total):
        bal = 0.0
        ruined = False
        passed = False
        
        # Day 1
        d_pnl = 0.0
        for tr in trades_by_date[dates[i]]:
            risk = 950.0  # safe from DLL
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
            if bal >= TARGET:
                passed = True
                break
            if bal <= FLOOR:
                ruined = True
                break
            # 1 trade per day limit to ensure clean sprint
            break
            
        # Day 2
        if not passed and not ruined:
            d_pnl = 0.0
            # If Day 1 won, use house money
            risk = 1500.0 if bal > 500.0 else (950.0 if bal >= 0 else 500.0)
            for tr in trades_by_date[dates[i+1]]:
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
                if bal >= TARGET:
                    passed = True
                    break
                if bal <= FLOOR:
                    ruined = True
                    break
                break
                
        if passed: passes += 1
        if ruined or bal <= FLOOR: ruins += 1
        
    print(f"{name:<32} | {total:<6d} | {passes/total*100:>8.1f}% | {ruins/total*100:>6.1f}% | {dll_hits/total*100:>6.1f}%")

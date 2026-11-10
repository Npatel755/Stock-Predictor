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

# Filter: Thu/Fri Long + GapCont Long + Overnight ZN
mask = (all_trades.side == 1) & (all_trades.dow.isin([3, 4]))
sub = all_trades[mask].copy()

trades_by_date = defaultdict(list)
for _, row in sub.iterrows():
    trades_by_date[row["date"]].append(row)
dates = sorted(trades_by_date.keys())

TARGET = 4000.0
FLOOR = -2000.0
DLL = -1000.0

def eval_sprint_window(max_days):
    total = len(dates) - max_days
    passes = 0
    ruins = 0
    dll_hits = 0
    
    for i in range(total):
        bal = 0.0
        ruined = False
        passed = False
        
        for d in range(i, i + max_days):
            d_pnl = 0.0
            # Sizing policy:
            # If in drawdown (bal < 0): risk 400
            # If at 0 to +1000: risk 800
            # If at +1000 to +2500: risk 1500 (house money sprint!)
            # If at +2500+: risk just enough to pass: min(1500, TARGET - bal)
            if bal < 0:
                risk = 400.0
            elif bal < 1000.0:
                risk = 800.0
            elif bal < 2500.0:
                risk = 1500.0
            else:
                risk = min(1500.0, max(500.0, TARGET - bal))
                
            for tr in trades_by_date[dates[d]]:
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
            if passed or ruined:
                break
                
        if passed: passes += 1
        if ruined or bal <= FLOOR: ruins += 1
        
    return total, passes, ruins, dll_hits

print("=== Sprint Horizon Analysis for Thu/Fri Long (Highest Expectancy 0.465R) ===")
print(f"{'Horizon Days':<14} | {'Starts':<6} | {'Pass Rate':<10} | {'Ruin Rate':<10} | {'DLL Hits':<10}")
print("-" * 55)
for days in [2, 3, 5, 10, 15, 20]:
    tot, p, r, dll = eval_sprint_window(days)
    print(f"{days:<14} | {tot:<6d} | {p/tot*100:>8.1f}% | {r/tot*100:>8.1f}% | {dll/tot*100:>8.1f}%")

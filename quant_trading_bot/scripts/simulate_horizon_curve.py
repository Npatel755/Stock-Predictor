import json
import numpy as np
import pandas as pd
from collections import defaultdict
from pathlib import Path

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")

intra = pd.read_parquet(ROOT / "data/processed/routed_7sleeve_trades_train.parquet")
intra["tout"] = pd.to_datetime(intra.tout_str, utc=True)
intra["tin"] = pd.to_datetime(intra.tin_str, utc=True)
intra["date"] = intra.tout.dt.tz_convert("America/New_York").dt.date

ov_all = pd.read_parquet(ROOT / "data/processed/clean_multi_sleeve_trades_train.parquet")
ov = ov_all[ov_all.sleeve_key == "OVERNIGHT"].copy()
ov["tout"] = pd.to_datetime(ov.tout_str, utc=True)
ov["tin"] = pd.to_datetime(ov.tin_str, utc=True)
ov["date"] = ov.tout.dt.tz_convert("America/New_York").dt.date

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

trades_by_date = defaultdict(list)
for _, row in all_trades.iterrows():
    trades_by_date[row["date"]].append(row)

dates = sorted(trades_by_date.keys())
n_dates = len(dates)

TARGET = 4000.0
FLOOR = -2000.0
DLL = -1000.0

def evaluate_horizon(risk_amount, max_days):
    passes = 0
    ruins = 0
    dll_hits = 0
    total_starts = n_dates - max_days
    
    for i in range(total_starts):
        bal = 0.0
        for d_idx in range(i, i + max_days):
            day_pnl = 0.0
            for tr in trades_by_date[dates[d_idx]]:
                # Cap risk to remaining cushion to floor if less than risk_amount
                r = tr["r_net"]
                trade_risk = min(risk_amount, bal - FLOOR)
                if trade_risk <= 50.0:
                    break
                
                pnl = r * trade_risk
                if pnl < -trade_risk:
                    pnl = -trade_risk
                
                # DLL check
                if day_pnl + pnl <= DLL:
                    pnl = DLL - day_pnl
                    day_pnl += pnl
                    bal += pnl
                    dll_hits += 1
                    break
                
                day_pnl += pnl
                bal += pnl
                
                if bal <= FLOOR:
                    ruins += 1
                    break
                if bal >= TARGET:
                    passes += 1
                    break
            
            if bal <= FLOOR or bal >= TARGET:
                break
                
    return {
        "risk": risk_amount,
        "max_days": max_days,
        "pass_pct": (passes / total_starts) * 100,
        "ruin_pct": (ruins / total_starts) * 100,
        "dll_pct": (dll_hits / total_starts) * 100
    }

print("Simulating risk profiles across days 2, 3, 5, 10, 20...")
profiles = [
    ("YOLO $1,500", 1500.0),
    ("Sprint $1,000", 1000.0),
    ("DLL Safe $700", 700.0),
    ("Moderate $500", 500.0),
    ("Adaptive Bal-3", 300.0)
]

table_rows = []
for name, r_amt in profiles:
    for days in [2, 3, 5, 10, 20]:
        res = evaluate_horizon(r_amt, days)
        table_rows.append((name, days, res["pass_pct"], res["ruin_pct"], res["dll_pct"]))

print(f"{'Profile':<16} | {'Days':<5} | {'Pass Rate':<10} | {'Ruin Rate':<10} | {'DLL Hit Rate':<12}")
print("-" * 65)
for name, days, pr, rr, dll in table_rows:
    print(f"{name:<16} | {days:<5} | {pr:>8.1f}% | {rr:>8.1f}% | {dll:>10.1f}%")

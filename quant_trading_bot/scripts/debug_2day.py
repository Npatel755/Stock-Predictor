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

total = n_dates - 2
passes = 0
ruins = 0
dll_hits = 0
final_bals = []

for i in range(total):
    bal = 0.0
    passed = False
    ruined = False
    
    for d_idx in [i, i+1]:
        d_pnl = 0.0
        for tr in trades_by_date[dates[d_idx]]:
            risk = 1500.0
            r = tr["r_net"]
            p = r * risk
            if p < -risk:
                p = -risk
            
            # DLL
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
            if bal >= TARGET:
                passed = True
                break
        
        if ruined or passed:
            break
            
    if passed:
        passes += 1
    if ruined or bal <= FLOOR:
        ruins += 1
    final_bals.append(bal)

print(f"2-Day Sprint with $1,500 Risk across {total} rolling starts:")
print(f"Pass Rate: {passes/total*100:.1f}%")
print(f"Ruin Rate (bal <= -2000): {ruins/total*100:.1f}%")
print(f"Mean Final Balance: ${np.mean(final_bals):.1f}")
print(f"Median Final Balance: ${np.median(final_bals):.1f}")
print(f"P10 Final Balance: ${np.percentile(final_bals, 10):.1f}")
print(f"P90 Final Balance: ${np.percentile(final_bals, 90):.1f}")
print(f"Balance <= -1000 (In severe drawdown): {np.mean(np.array(final_bals) <= -1000)*100:.1f}%")

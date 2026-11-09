"""Test managed stop/target on Cross-Asset Relative Strength (NQ vs ES) Momentum.
Signal: At 10:00 ET, if NQ 30m return outperforms ES 30m return by >= z_th std:
Enter Long 1 contract MNQ at 10:00 close.
Exit: Stop loss = entry - stop_atr * ATR14; Target = entry + tgt_r * (stop_atr * ATR14); Hold timeout = 12 bars (3 hours) or flat 15:55.

Evaluated on Training data (2010-2023, 14 years).
Micro costs: 0.61/side, 1.75 tick MNQ spread, 1 tick slippage.
"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd
from numba import njit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import mass_1m_search as m1

COMM, SLIP = 0.61, 1.0
SPEC = {"MNQ": dict(tick=0.25, pv=0.5, spread=1.75), "MES": dict(tick=0.25, pv=1.25, spread=1.0)}
cost_mnq = (SPEC["MNQ"]["spread"] + 2 * SLIP) * SPEC["MNQ"]["pv"] + 2 * COMM
rng = np.random.default_rng(20261109)

print("Loading 15m bars for MNQ and MES...")
b_mnq = m1.load_bars("MNQ", 15, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]].copy()
b_mes = m1.load_bars("MES", 15, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]].copy()

et_mnq = b_mnq.timestamp_utc.dt.tz_convert("America/New_York")
b_mnq["sod"] = et_mnq.dt.hour * 60 + et_mnq.dt.minute
b_mnq["date"] = et_mnq.dt.date
b_mnq["year"] = et_mnq.dt.year

et_mes = b_mes.timestamp_utc.dt.tz_convert("America/New_York")
b_mes["sod"] = et_mes.dt.hour * 60 + et_mes.dt.minute
b_mes["date"] = et_mes.dt.date

# Filter to RTH
rth_mnq = b_mnq[(b_mnq.sod >= 570) & (b_mnq.sod < 960)].reset_index(drop=True)
rth_mes = b_mes[(b_mes.sod >= 570) & (b_mes.sod < 960)].reset_index(drop=True)

# Build 10:00 spread
g_mnq = rth_mnq.groupby("date")
g_mes = rth_mes.groupby("date")

o930_mnq = g_mnq.apply(lambda d: d.loc[d.sod == 570, "open"].iloc[0] if (d.sod == 570).any() else np.nan)
c1000_mnq = g_mnq.apply(lambda d: d.loc[d.sod == 600, "close"].iloc[0] if (d.sod == 600).any() else np.nan)
o930_mes = g_mes.apply(lambda d: d.loc[d.sod == 570, "open"].iloc[0] if (d.sod == 570).any() else np.nan)
c1000_mes = g_mes.apply(lambda d: d.loc[d.sod == 600, "close"].iloc[0] if (d.sod == 600).any() else np.nan)

common_days = sorted(list(set(o930_mnq.dropna().index).intersection(set(o930_mes.dropna().index))))
df_days = pd.DataFrame(index=common_days)
df_days["ret_mnq"] = (c1000_mnq.loc[common_days] / o930_mnq.loc[common_days]) - 1.0
df_days["ret_mes"] = (c1000_mes.loc[common_days] / o930_mes.loc[common_days]) - 1.0
df_days["spread"] = df_days["ret_mnq"] - df_days["ret_mes"]
df_days["spread_z"] = df_days["spread"] / df_days["spread"].rolling(20, min_periods=20).std().shift(1)

# Now map back to 15m MNQ bars
rth_mnq["day"] = pd.factorize(rth_mnq.date)[0]
tr = np.maximum(rth_mnq.high - rth_mnq.low, np.maximum((rth_mnq.high - rth_mnq.close.shift(1)).abs(), (rth_mnq.low - rth_mnq.close.shift(1)).abs()))
atr = tr.rolling(14, min_periods=14).mean().bfill().to_numpy(float)

o = rth_mnq.open.to_numpy(float)
h = rth_mnq.high.to_numpy(float)
l = rth_mnq.low.to_numpy(float)
c = rth_mnq.close.to_numpy(float)
sod = rth_mnq.sod.to_numpy(np.int64)
day = rth_mnq.day.to_numpy(np.int64)
year = rth_mnq.year.to_numpy(np.int64)

# Create day_to_z map
date_to_z = df_days["spread_z"].to_dict()
z_per_bar = np.array([date_to_z.get(d, 0.0) for d in rth_mnq.date])

@njit(cache=True)
def sim_rs(o, h, l, c, atr, z_arr, day, sod, z_th, stop_mult, tgt_r, hold, flat, cost, long_only):
    n = len(o)
    pnl = np.zeros(n)
    pos = 0
    ep = 0.0
    st = 0.0
    tg = 0.0
    ei = 0
    eday = -1
    ntr = 0
    
    for i in range(n):
        # Position management
        if pos != 0:
            ex = False
            px = 0.0
            if day[i] != eday:
                ex = True
                px = o[i]
            elif pos > 0 and l[i] <= st:
                ex = True
                px = st
            elif pos < 0 and h[i] >= st:
                ex = True
                px = st
            elif pos > 0 and h[i] >= tg:
                ex = True
                px = tg
            elif pos < 0 and l[i] <= tg:
                ex = True
                px = tg
            elif (i - ei >= hold) or (sod[i] + 15 >= flat):
                ex = True
                px = c[i]
                
            if ex:
                pnl[i] += pos * (px - ep) / 0.25 * 0.5 - cost
                pos = 0
                ntr += 1
                
        # Entry check: exactly at 10:00 close (sod == 600)
        if pos == 0 and sod[i] == 600 and i + 1 < n and day[i + 1] == day[i] and atr[i] > 0:
            sig = 0
            if z_arr[i] >= z_th:
                sig = 1
            elif (not long_only) and z_arr[i] <= -z_th:
                sig = -1
                
            if sig != 0:
                pos = sig
                ep = o[i + 1] # enter on next bar open (10:00 open)
                risk = stop_mult * atr[i]
                st = ep - risk if pos > 0 else ep + risk
                tg = ep + tgt_r * risk if pos > 0 else ep - tgt_r * risk
                ei = i + 1
                eday = day[i]
                
    return pnl, ntr

print("\n--- SIMULATION RESULTS (2010-2023 Training) ---")
print("Long-Only NQ Leading ES Momentum with Stops & Targets:")

best_configs = []

for z_th in [0.5, 0.75, 1.0, 1.25]:
    for stop_atr in [1.0, 1.25, 1.5, 2.0]:
        for tgt_r in [2.0, 2.5, 3.0, 4.0]:
            for hold in [8, 12, 16, 20]:
                pnl, ntr = sim_rs(o, h, l, c, atr, z_per_bar, day, sod, z_th, stop_atr, tgt_r, hold, 955, cost_mnq, True)
                if ntr < 100: continue
                s_pnl = pd.Series(pnl)
                tot_net = float(s_pnl.sum())
                yearly = s_pnl.groupby(year).sum()
                pos_yrs = int(sum(yearly > 0))
                exp_tr = tot_net / ntr
                
                # Check 2010-2019 pre-2020 net
                pre_2020 = float(s_pnl[year < 2020].sum())
                post_2020 = float(s_pnl[year >= 2020].sum())
                
                # Max Drawdown
                cum = s_pnl.cumsum()
                dd = cum.cummax() - cum
                mdd = float(dd.max())
                
                if tot_net > 5000 and pos_yrs >= 10 and pre_2020 > 500 and mdd < 1500:
                    best_configs.append({
                        "z_th": z_th, "stop_atr": stop_atr, "tgt_r": tgt_r, "hold": hold,
                        "tot_net": tot_net, "pre_2020": pre_2020, "post_2020": post_2020,
                        "ntr": ntr, "exp_tr": exp_tr, "pos_yrs": pos_yrs, "mdd": mdd
                    })

df_res = pd.DataFrame(best_configs)
if len(df_res) > 0:
    df_res = df_res.sort_values("tot_net", ascending=False)
    print(f"\nFound {len(df_res)} qualified configurations with >= 10/14 positive years and Pre-2020 Net > $500!")
    print(df_res.head(10).to_string(index=False))
else:
    print("No configs met strict filter criteria. Testing baseline parameters...")
    for z_th in [0.75, 1.0]:
        pnl, ntr = sim_rs(o, h, l, c, atr, z_per_bar, day, sod, z_th, 1.5, 3.0, 16, 955, cost_mnq, True)
        s_pnl = pd.Series(pnl)
        tot_net = float(s_pnl.sum())
        yearly = s_pnl.groupby(year).sum()
        pre_2020 = float(s_pnl[year < 2020].sum())
        pos_yrs = int(sum(yearly > 0))
        cum = s_pnl.cumsum()
        mdd = float((cum.cummax() - cum).max())
        print(f"z_th: {z_th} | Net: ${tot_net:.2f} | Pre-2020: ${pre_2020:.2f} | Tr: {ntr} | Exp: +${tot_net/ntr:.2f} | +Yrs: {pos_yrs}/14 | MaxDD: ${mdd:.2f}")

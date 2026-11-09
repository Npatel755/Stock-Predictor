"""Research Protocol: Direct 10:00 Institutional Directional Engine (MNQ + MES).
Hypothesis:
Instead of waiting for lagging moving-average crossovers at 11:30-12:00,
entering immediately at 10:00 ET when the Directional Signal confirms:
- Captures the full session trend expansion from 10:00 to 15:55.
- Reduces lunchtime whip stops.
- Uses MNQ when Tech leads, and MES when broad-market Crabel/VIX triggers.

EVALUATED STRICTLY ON TRAINING DATA (2010-2023, 14 FULL YEARS).
DO NOT TOUCH VALIDATION (2024-2025) OR TEST (2026).
Micro costs: 0.61/side commission, 1.75 tick MNQ / 1.0 tick MES spread, 1.0 tick slippage/side.
Router: Strict 1-contract max limit across entire account.
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
from numba import njit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'src'))

import mass_1m_search as m1

COMM, SLIP = 0.61, 1.0
SPEC_MNQ = {"tick": 0.25, "pv": 0.5, "spread": 1.75}
SPEC_MES = {"tick": 0.25, "pv": 1.25, "spread": 1.0}

def rt_cost(prod, qty=1):
    s = SPEC_MNQ if prod == "MNQ" else SPEC_MES
    return ((s["spread"] + 2 * SLIP) * s["pv"] + 2 * COMM) * qty

print("Loading continuous 15m Training bars for MNQ and MES (2010-2023)...", flush=True)
b_mnq_15 = m1.load_bars("MNQ", 15, "2010-01-01", "2024-01-01", "train").copy()
b_mes_15 = m1.load_bars("MES", 15, "2010-01-01", "2024-01-01", "train").copy()

vix = pd.read_csv(ROOT / "data" / "external" / "VIX_History.csv")
vix3m = pd.read_csv(ROOT / "data" / "external" / "VIX3M_History.csv")

vix["date"] = pd.to_datetime(vix["DATE"]).dt.date
vix3m["date"] = pd.to_datetime(vix3m["DATE"]).dt.date

vix_df = pd.merge(vix[["date", "CLOSE"]].rename(columns={"CLOSE": "vix"}),
                  vix3m[["date", "CLOSE"]].rename(columns={"CLOSE": "vix3m"}),
                  on="date").sort_values("date").reset_index(drop=True)

vix_df["ratio"] = vix_df["vix"] / vix_df["vix3m"]
vix_df["ratio_d1"] = vix_df["ratio"].diff(1)
vix_df["trade_date"] = vix_df["date"].shift(-1)
date_to_vix_d1 = dict(zip(vix_df["trade_date"], vix_df["ratio_d1"]))

for b in (b_mnq_15, b_mes_15):
    et = b.timestamp_utc.dt.tz_convert("America/New_York")
    b["sod"] = et.dt.hour * 60 + et.dt.minute
    b["date"] = et.dt.date
    b["year"] = et.dt.year

rth_mnq = b_mnq_15[(b_mnq_15.sod >= 570) & (b_mnq_15.sod <= 955)].reset_index(drop=True)
rth_mes = b_mes_15[(b_mes_15.sod >= 570) & (b_mes_15.sod <= 955)].reset_index(drop=True)

g_mnq = rth_mnq.groupby("date")
g_mes = rth_mes.groupby("date")

o930_mnq = g_mnq.apply(lambda d: d.loc[d.sod == 570, "open"].iloc[0] if (d.sod == 570).any() else np.nan)
c1000_mnq = g_mnq.apply(lambda d: d.loc[d.sod == 585, "close"].iloc[0] if (d.sod == 585).any() else np.nan)
h1000_mnq = g_mnq.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), "high"].max() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)
l1000_mnq = g_mnq.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), "low"].min() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)

o930_mes = g_mes.apply(lambda d: d.loc[d.sod == 570, "open"].iloc[0] if (d.sod == 570).any() else np.nan)
c1000_mes = g_mes.apply(lambda d: d.loc[d.sod == 585, "close"].iloc[0] if (d.sod == 585).any() else np.nan)
h1000_mes = g_mes.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), "high"].max() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)
l1000_mes = g_mes.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), "low"].min() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)

common_days = sorted(list(set(o930_mnq.dropna().index).intersection(set(o930_mes.dropna().index))))
df_days = pd.DataFrame(index=common_days)
df_days["ret_mnq"] = (c1000_mnq.loc[common_days] / o930_mnq.loc[common_days]) - 1.0
df_days["ret_mes"] = (c1000_mes.loc[common_days] / o930_mes.loc[common_days]) - 1.0
df_days["spread"] = df_days["ret_mnq"] - df_days["ret_mes"]
df_days["spread_z"] = df_days["spread"] / df_days["spread"].rolling(20, min_periods=20).std().shift(1)

# Crabel metrics
df_days["range_30m"] = h1000_mnq.loc[common_days] - l1000_mnq.loc[common_days]
df_days["open_pos"] = (o930_mnq.loc[common_days] - l1000_mnq.loc[common_days]) / df_days["range_30m"].replace(0, np.nan)
df_days["close_pos"] = (c1000_mnq.loc[common_days] - l1000_mnq.loc[common_days]) / df_days["range_30m"].replace(0, np.nan)

# VIX delta
df_days["vix_d1"] = [date_to_vix_d1.get(d, np.nan) for d in df_days.index]

# Signal classification:
# Bull Predictors:
df_days["bull_leader"] = (df_days["spread_z"] >= 1.0)
df_days["bull_crabel"] = ((df_days["open_pos"] <= 0.20) & (df_days["close_pos"] >= 0.80))
df_days["bull_vix"] = ((df_days["vix_d1"] <= -0.015) & (df_days["ret_mnq"] >= 0.001))

# Bear Predictors:
df_days["bear_leader"] = (df_days["spread_z"] <= -1.0)
df_days["bear_crabel"] = ((df_days["open_pos"] >= 0.80) & (df_days["close_pos"] <= 0.20))
df_days["bear_vix"] = ((df_days["vix_d1"] >= +0.02) & (df_days["ret_mnq"] <= -0.001))

# Composite Directional Score:
df_days["bull_score"] = df_days["bull_leader"].astype(int) + df_days["bull_crabel"].astype(int) + df_days["bull_vix"].astype(int)
df_days["bear_score"] = df_days["bear_leader"].astype(int) + df_days["bear_crabel"].astype(int) + df_days["bear_vix"].astype(int)

# Direction:
df_days["dir"] = 0
df_days.loc[df_days.bull_score > df_days.bear_score, "dir"] = 1
df_days.loc[df_days.bear_score > df_days.bull_score, "dir"] = -1

# Preferred Instrument:
# If NQ-leader fired, trade MNQ (capture tech leadership). Otherwise if Crabel or VIX on broad market, trade MES.
df_days["pref_prod"] = "MNQ"
df_days.loc[df_days.bull_leader | df_days.bear_leader, "pref_prod"] = "MNQ"
df_days.loc[(~df_days.bull_leader) & (~df_days.bear_leader) & (df_days.bull_crabel | df_days.bear_crabel | df_days.bull_vix | df_days.bear_vix), "pref_prod"] = "MES"

date_to_dir = df_days["dir"].to_dict()
date_to_prod = df_days["pref_prod"].to_dict()
date_to_bscore = df_days["bull_score"].to_dict()
date_to_sscore = df_days["bear_score"].to_dict()

# Calculate ATR for both products
rth_mnq["day"] = pd.factorize(rth_mnq.date)[0]
tr_mnq = np.maximum(rth_mnq.high - rth_mnq.low, np.maximum((rth_mnq.high - rth_mnq.close.shift(1)).abs(), (rth_mnq.low - rth_mnq.close.shift(1)).abs()))
atr_mnq = tr_mnq.rolling(14, min_periods=14).mean().bfill().to_numpy(float)

rth_mes["day"] = pd.factorize(rth_mes.date)[0]
tr_mes = np.maximum(rth_mes.high - rth_mes.low, np.maximum((rth_mes.high - rth_mes.close.shift(1)).abs(), (rth_mes.low - rth_mes.close.shift(1)).abs()))
atr_mes = tr_mes.rolling(14, min_periods=14).mean().bfill().to_numpy(float)

rth_mnq["atr"] = atr_mnq
rth_mes["atr"] = atr_mes

# Pre-extract numpy data
mnq_data = {
    "open": rth_mnq.open.to_numpy(float), "high": rth_mnq.high.to_numpy(float),
    "low": rth_mnq.low.to_numpy(float), "close": rth_mnq.close.to_numpy(float),
    "sod": rth_mnq.sod.to_numpy(np.int64), "date": rth_mnq.date.to_numpy(),
    "year": rth_mnq.year.to_numpy(np.int64), "ts": rth_mnq.timestamp_utc.to_numpy(),
    "atr": atr_mnq
}

mes_data = {
    "open": rth_mes.open.to_numpy(float), "high": rth_mes.high.to_numpy(float),
    "low": rth_mes.low.to_numpy(float), "close": rth_mes.close.to_numpy(float),
    "sod": rth_mes.sod.to_numpy(np.int64), "date": rth_mes.date.to_numpy(),
    "year": rth_mes.year.to_numpy(np.int64), "ts": rth_mes.timestamp_utc.to_numpy(),
    "atr": atr_mes
}

def simulate_direct_1000(name, prod_mode="MNQ", min_score=1, stop_mult=1.5, tgt_r=3.5, hold=16, dynamic_scale=False):
    executed = []
    running_pnl = 0.0
    
    # Iterate over unique trading days
    for dt in common_days:
        b_sc = date_to_bscore.get(dt, 0)
        s_sc = date_to_sscore.get(dt, 0)
        d_val = date_to_dir.get(dt, 0)
        
        if d_val == 1 and b_sc < min_score: continue
        if d_val == -1 and s_sc < min_score: continue
        if d_val == 0: continue
        
        # Determine product
        target_prod = prod_mode
        if prod_mode == "DYNAMIC":
            target_prod = date_to_prod.get(dt, "MNQ")
            
        d = mnq_data if target_prod == "MNQ" else mes_data
        spec = SPEC_MNQ if target_prod == "MNQ" else SPEC_MES
        
        # Find 10:00 entry bar (decision at sod == 585, entry at open of sod == 600)
        # Find index where date == dt and sod == 585
        date_mask = (d["date"] == dt)
        day_indices = np.where(date_mask)[0]
        if len(day_indices) == 0: continue
        
        sod_sub = d["sod"][day_indices]
        idx_585_arr = np.where(sod_sub == 585)[0]
        if len(idx_585_arr) == 0: continue
        
        idx_585 = day_indices[idx_585_arr[0]]
        if idx_585 + 1 >= len(d["open"]): continue
        if d["date"][idx_585 + 1] != dt: continue
        
        entry_idx = idx_585 + 1
        ep = d["open"][entry_idx]
        atr_val = d["atr"][idx_585]
        if atr_val <= 0: continue
        
        side = d_val
        risk = stop_mult * atr_val
        st = ep - risk if side > 0 else ep + risk
        tg = ep + tgt_r * risk if side > 0 else ep - tgt_r * risk
        
        qty = 1
        if dynamic_scale and max(b_sc, s_sc) >= 2:
            qty = 2
            
        exit_px = 0.0
        exit_ts = None
        bars_held = 0
        
        for k in range(entry_idx, len(d["open"])):
            if d["date"][k] != dt:
                exit_ts = d["ts"][k]; exit_px = d["open"][k]; break
            bars_held += 1
            if side > 0:
                if d["low"][k] <= st: exit_ts = d["ts"][k]; exit_px = st; break
                elif d["high"][k] >= tg: exit_ts = d["ts"][k]; exit_px = tg; break
            else:
                if d["high"][k] >= st: exit_ts = d["ts"][k]; exit_px = st; break
                elif d["low"][k] <= tg: exit_ts = d["ts"][k]; exit_px = tg; break
                
            if bars_held >= hold or d["sod"][k] >= 955:
                exit_ts = d["ts"][k]; exit_px = d["close"][k]; break
                
        if exit_ts is None: continue
        
        gross_pts = side * (exit_px - ep)
        gross_dlr = gross_pts / spec["tick"] * spec["pv"] * qty
        fee = rt_cost(target_prod, qty)
        net_dlr = gross_dlr - fee
        running_pnl += net_dlr
        
        executed.append({
            "date": dt, "year": pd.to_datetime(dt).year, "prod": target_prod,
            "side": side, "qty": qty, "net_dlr": net_dlr, "running_pnl": running_pnl
        })
        
    df_res = pd.DataFrame(executed)
    tot = df_res.net_dlr.sum()
    pre = df_res[df_res.year < 2020].net_dlr.sum()
    post = df_res[df_res.year >= 2020].net_dlr.sum()
    yearly = df_res.groupby("year")["net_dlr"].sum()
    pos_y = (yearly > 0).sum()
    
    cum = df_res.net_dlr.cumsum()
    mdd = (cum.cummax() - cum).max()
    exp_tr = tot / len(df_res) if len(df_res) else 0.0
    
    print(f"\n=======================================================", flush=True)
    print(f"{name}", flush=True)
    print(f"=======================================================", flush=True)
    print(f"Total Net: ${tot:+.2f} | Trades: {len(df_res)} ({len(df_res)/14:.1f} tr/yr) | Exp: ${exp_tr:+.2f}/tr", flush=True)
    print(f"Pre-2020 Era (2010-2019): ${pre:+.2f} ({(yearly.loc[yearly.index < 2020] > 0).sum()}/10 pos years)", flush=True)
    print(f"Post-2020 Era (2020-2023): ${post:+.2f} ({(yearly.loc[yearly.index >= 2020] > 0).sum()}/4 pos years)", flush=True)
    print(f"Positive Years: {pos_y} of 14 ({pos_y/14*100:.1f}%)", flush=True)
    print(f"Max Continuous Drawdown: ${mdd:.2f} (Safety Buffer: ${2000 - mdd:+.2f} under $2,000 floor)", flush=True)
    print("Yearly Breakdown:", flush=True)
    for yr, val in yearly.items():
        print(f"  {yr}: ${val:+.2f}", flush=True)
        
    return df_res

# Evaluate Variants on 2010-2023 Training
simulate_direct_1000("1. MNQ 10:00 Direct Directional (Score >= 1, 1 Contract)", prod_mode="MNQ", min_score=1)
simulate_direct_1000("2. MES 10:00 Direct Directional (Score >= 1, 1 Contract)", prod_mode="MES", min_score=1)
simulate_direct_1000("3. DYNAMIC (MNQ on Tech Leader, MES on Broad Crabel/VIX)", prod_mode="DYNAMIC", min_score=1)
simulate_direct_1000("4. HIGH-CONVICTION CONFLUENCE (Score >= 2, 1 Contract)", prod_mode="MNQ", min_score=2)
simulate_direct_1000("5. DYNAMIC SCALING (1ct Score=1, 2ct Score>=2)", prod_mode="DYNAMIC", min_score=1, dynamic_scale=True)

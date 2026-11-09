"""Research Protocol: Directional Market Prediction via Validated Signals for MNQ & MES.
User Mandate:
"why dont you use these signals to predict direction in the market and trade with the mes and mnq"
"make sure NOT TO TUNE ON VALIDATION OR TESTING DATA"

Hypothesis:
The 3 placebo-validated signals (NQ/ES Divergence, Crabel Open-Drive, VIX Velocity Shock)
reliably predict the prevailing institutional order-flow direction for the remainder of the RTH session.
By conditioning the AG Quad trend sleeves (MNQ 30m, MNQ 60m, MNQ 30m PM, MES 30m) to:
- Take ONLY Long trades on Bull-Predicted Days
- Take ONLY Short trades on Bear-Predicted Days
- Filter out whipsaws and false counter-trend signals on directional days
Does this reduce max drawdown, increase per-trade expectancy, and improve pre-2020 net profit?

EVALUATED STRICTLY ON TRAINING DATA (2010-2023, 14 FULL YEARS).
DO NOT TOUCH VALIDATION (2024-2025) OR TEST (2026).
Micro costs: 0.61/side commission, 1.75 tick MNQ / 1.0 tick MES spread, 1.0 tick slippage/side.
Router: Strict 1-contract global limit across entire account. Priority S1 > S2 > S3 > S4.
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'src'))

import mass_1m_search as m1
from quant_futures.ensemble_paper import _AG_MORN30, _AG_TRD60Q, _AG_TRD30PM, _AG_MES_TRD30, custom_signal

COMM, SLIP = 0.61, 1.0
SPEC_MNQ = {"tick": 0.25, "pv": 0.5, "spread": 1.75}
SPEC_MES = {"tick": 0.25, "pv": 1.25, "spread": 1.0}

def rt_cost(prod, qty=1):
    s = SPEC_MNQ if prod == "MNQ" else SPEC_MES
    return ((s["spread"] + 2 * SLIP) * s["pv"] + 2 * COMM) * qty

print("Loading continuous Training bars for MNQ (30m, 60m) and MES (30m) (2010-2023)...", flush=True)
b_mnq_30 = m1.load_bars("MNQ", 30, "2010-01-01", "2024-01-01", "train").copy()
b_mnq_60 = m1.load_bars("MNQ", 60, "2010-01-01", "2024-01-01", "train").copy()
b_mes_30 = m1.load_bars("MES", 30, "2010-01-01", "2024-01-01", "train").copy()

# Load continuous 15m bars to extract point-in-time 10:00 ET signals
b_mnq_15 = m1.load_bars("MNQ", 15, "2010-01-01", "2024-01-01", "train").copy()
b_mes_15 = m1.load_bars("MES", 15, "2010-01-01", "2024-01-01", "train").copy()

# Load VIX and VIX3M histories
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

for b in (b_mnq_30, b_mnq_60, b_mes_30, b_mnq_15, b_mes_15):
    et = b.timestamp_utc.dt.tz_convert("America/New_York")
    b["sod"] = et.dt.hour * 60 + et.dt.minute
    b["date"] = et.dt.date
    b["year"] = et.dt.year

rth_mnq15 = b_mnq_15[(b_mnq_15.sod >= 570) & (b_mnq_15.sod <= 955)].reset_index(drop=True)
rth_mes15 = b_mes_15[(b_mes_15.sod >= 570) & (b_mes_15.sod <= 955)].reset_index(drop=True)

# Build daily 10:00 directional features
g_mnq15 = rth_mnq15.groupby("date")
g_mes15 = rth_mes15.groupby("date")

o930_mnq = g_mnq15.apply(lambda d: d.loc[d.sod == 570, "open"].iloc[0] if (d.sod == 570).any() else np.nan)
c1000_mnq = g_mnq15.apply(lambda d: d.loc[d.sod == 585, "close"].iloc[0] if (d.sod == 585).any() else np.nan)
h1000_mnq = g_mnq15.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), "high"].max() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)
l1000_mnq = g_mnq15.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), "low"].min() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)

o930_mes = g_mes15.apply(lambda d: d.loc[d.sod == 570, "open"].iloc[0] if (d.sod == 570).any() else np.nan)
c1000_mes = g_mes15.apply(lambda d: d.loc[d.sod == 585, "close"].iloc[0] if (d.sod == 585).any() else np.nan)

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
df_days["bull_day"] = df_days["bull_leader"] | df_days["bull_crabel"] | df_days["bull_vix"]

# Bear Predictors:
df_days["bear_leader"] = (df_days["spread_z"] <= -1.0)
df_days["bear_crabel"] = ((df_days["open_pos"] >= 0.80) & (df_days["close_pos"] <= 0.20))
df_days["bear_vix"] = ((df_days["vix_d1"] >= +0.02) & (df_days["ret_mnq"] <= -0.001))
df_days["bear_day"] = df_days["bear_leader"] | df_days["bear_crabel"] | df_days["bear_vix"]

# Composite Directional Prediction:
# +1 = Bull Day, -1 = Bear Day, 0 = Neutral Day
df_days["direction"] = 0
df_days.loc[df_days["bull_day"] & (~df_days["bear_day"]), "direction"] = 1
df_days.loc[df_days["bear_day"] & (~df_days["bull_day"]), "direction"] = -1

date_to_dir = df_days["direction"].to_dict()
date_to_bull = df_days["bull_day"].to_dict()
date_to_bear = df_days["bear_day"].to_dict()

print(f"\n--- Directional Market Prediction Distribution (2010-2023 Training) ---")
print(f"Total Trading Days: {len(df_days)}")
print(f"Bull-Predicted Days: {(df_days.direction == 1).sum()} ({(df_days.direction == 1).mean()*100:.1f}%)")
print(f"Bear-Predicted Days: {(df_days.direction == -1).sum()} ({(df_days.direction == -1).mean()*100:.1f}%)")
print(f"Neutral Days: {(df_days.direction == 0).sum()} ({(df_days.direction == 0).mean()*100:.1f}%)")

# Filter 30m / 60m bars to RTH
rth_mnq30 = b_mnq_30[(b_mnq_30.sod >= 570) & (b_mnq_30.sod <= 955)].reset_index(drop=True)
rth_mnq60 = b_mnq_60[(b_mnq_60.sod >= 540) & (b_mnq_60.sod <= 955)].reset_index(drop=True)
rth_mes30 = b_mes_30[(b_mes_30.sod >= 570) & (b_mes_30.sod <= 955)].reset_index(drop=True)

# Generate raw signals and ATRs
sig_s1, atr_s1 = custom_signal(_AG_MORN30, rth_mnq30)
sig_s2, atr_s2 = custom_signal(_AG_TRD60Q, rth_mnq60)
sig_s3, atr_s3 = custom_signal(_AG_TRD30PM, rth_mnq30)
sig_s4, atr_s4 = custom_signal(_AG_MES_TRD30, rth_mes30)

rth_mnq30["sig_s1"] = sig_s1
rth_mnq30["atr_s1"] = atr_s1
rth_mnq30["sig_s3"] = sig_s3
rth_mnq30["atr_s3"] = atr_s3

rth_mnq60["sig_s2"] = sig_s2
rth_mnq60["atr_s2"] = atr_s2

rth_mes30["sig_s4"] = sig_s4
rth_mes30["atr_s4"] = atr_s4

data_dict = {
    "mnq30": {
        "open": rth_mnq30.open.to_numpy(float), "high": rth_mnq30.high.to_numpy(float),
        "low": rth_mnq30.low.to_numpy(float), "close": rth_mnq30.close.to_numpy(float),
        "sod": rth_mnq30.sod.to_numpy(np.int64), "date": rth_mnq30.date.to_numpy(),
        "year": rth_mnq30.year.to_numpy(np.int64), "ts": rth_mnq30.timestamp_utc.to_numpy(),
        "sig_s1": sig_s1, "atr_s1": atr_s1, "sig_s3": sig_s3, "atr_s3": atr_s3
    },
    "mnq60": {
        "open": rth_mnq60.open.to_numpy(float), "high": rth_mnq60.high.to_numpy(float),
        "low": rth_mnq60.low.to_numpy(float), "close": rth_mnq60.close.to_numpy(float),
        "sod": rth_mnq60.sod.to_numpy(np.int64), "date": rth_mnq60.date.to_numpy(),
        "year": rth_mnq60.year.to_numpy(np.int64), "ts": rth_mnq60.timestamp_utc.to_numpy(),
        "sig_s2": sig_s2, "atr_s2": atr_s2
    },
    "mes30": {
        "open": rth_mes30.open.to_numpy(float), "high": rth_mes30.high.to_numpy(float),
        "low": rth_mes30.low.to_numpy(float), "close": rth_mes30.close.to_numpy(float),
        "sod": rth_mes30.sod.to_numpy(np.int64), "date": rth_mes30.date.to_numpy(),
        "year": rth_mes30.year.to_numpy(np.int64), "ts": rth_mes30.timestamp_utc.to_numpy(),
        "sig_s4": sig_s4, "atr_s4": atr_s4
    }
}

def build_events(gating_mode="none"):
    """
    gating_mode:
    - 'none': Ungated Baseline
    - 'directional': Long-only on Bull days, Short-only on Bear days, skip Neutral
    - 'directional_allow_neutral': Long-only on Bull, Short-only on Bear, bidirectional on Neutral
    """
    evs = []
    
    # S1: MNQ 30m Morning (09:45-12:00)
    d = data_dict["mnq30"]
    for i in range(len(d["open"]) - 1):
        if d["date"][i] != d["date"][i+1]: continue
        dt = d["date"][i]
        sig = d["sig_s1"][i]
        if sig != 0 and (570 <= d["sod"][i] <= 690):
            day_dir = date_to_dir.get(dt, 0)
            if gating_mode == "directional":
                if day_dir == 0: continue
                if (day_dir == 1 and sig < 0) or (day_dir == -1 and sig > 0): continue
            elif gating_mode == "directional_allow_neutral":
                if (day_dir == 1 and sig < 0) or (day_dir == -1 and sig > 0): continue
                
            evs.append({
                "ts": d["ts"][i+1], "date": dt, "year": d["year"][i],
                "sleeve": 1, "prod": "MNQ", "side": sig,
                "start_idx": i+1, "entry_px": d["open"][i+1], "atr": d["atr_s1"][i],
                "stop_mult": 1.5, "tgt_r": 3.5, "hold": 8, "data_key": "mnq30"
            })
            
    # S2: MNQ 60m Macro (10:00-12:00)
    d = data_dict["mnq60"]
    for i in range(len(d["open"]) - 1):
        if d["date"][i] != d["date"][i+1]: continue
        dt = d["date"][i]
        sig = d["sig_s2"][i]
        if sig != 0 and (540 <= d["sod"][i] <= 660):
            day_dir = date_to_dir.get(dt, 0)
            if gating_mode == "directional":
                if day_dir == 0: continue
                if (day_dir == 1 and sig < 0) or (day_dir == -1 and sig > 0): continue
            elif gating_mode == "directional_allow_neutral":
                if (day_dir == 1 and sig < 0) or (day_dir == -1 and sig > 0): continue
                
            evs.append({
                "ts": d["ts"][i+1], "date": dt, "year": d["year"][i],
                "sleeve": 2, "prod": "MNQ", "side": sig,
                "start_idx": i+1, "entry_px": d["open"][i+1], "atr": d["atr_s2"][i],
                "stop_mult": 1.25, "tgt_r": 4.0, "hold": 8, "data_key": "mnq60"
            })
            
    # S3: MNQ 30m Afternoon (13:30-15:15)
    d = data_dict["mnq30"]
    for i in range(len(d["open"]) - 1):
        if d["date"][i] != d["date"][i+1]: continue
        dt = d["date"][i]
        sig = d["sig_s3"][i]
        if sig != 0 and (780 <= d["sod"][i] <= 870):
            day_dir = date_to_dir.get(dt, 0)
            if gating_mode == "directional":
                if day_dir == 0: continue
                if (day_dir == 1 and sig < 0) or (day_dir == -1 and sig > 0): continue
            elif gating_mode == "directional_allow_neutral":
                if (day_dir == 1 and sig < 0) or (day_dir == -1 and sig > 0): continue
                
            evs.append({
                "ts": d["ts"][i+1], "date": dt, "year": d["year"][i],
                "sleeve": 3, "prod": "MNQ", "side": sig,
                "start_idx": i+1, "entry_px": d["open"][i+1], "atr": d["atr_s3"][i],
                "stop_mult": 1.5, "tgt_r": 4.0, "hold": 4, "data_key": "mnq30"
            })
            
    # S4: MES 30m Trend (09:45-15:30)
    d = data_dict["mes30"]
    for i in range(len(d["open"]) - 1):
        if d["date"][i] != d["date"][i+1]: continue
        dt = d["date"][i]
        sig = d["sig_s4"][i]
        if sig != 0 and (570 <= d["sod"][i] <= 900):
            day_dir = date_to_dir.get(dt, 0)
            if gating_mode == "directional":
                if day_dir == 0: continue
                if (day_dir == 1 and sig < 0) or (day_dir == -1 and sig > 0): continue
            elif gating_mode == "directional_allow_neutral":
                if (day_dir == 1 and sig < 0) or (day_dir == -1 and sig > 0): continue
                
            evs.append({
                "ts": d["ts"][i+1], "date": dt, "year": d["year"][i],
                "sleeve": 4, "prod": "MES", "side": sig,
                "start_idx": i+1, "entry_px": d["open"][i+1], "atr": d["atr_s4"][i],
                "stop_mult": 1.25, "tgt_r": 2.5, "hold": 12, "data_key": "mes30"
            })
            
    return pd.DataFrame(evs).sort_values(["ts", "sleeve"]).reset_index(drop=True)

def simulate_engine(df_events, name):
    executed = []
    active_until = pd.Timestamp("1970-01-01", tz="UTC")
    running_pnl = 0.0
    
    for _, ev in df_events.iterrows():
        if ev["ts"] < active_until:
            continue
            
        d = data_dict[ev["data_key"]]
        idx = ev["start_idx"]
        side = ev["side"]
        ep = ev["entry_px"]
        atr = ev["atr"]
        risk = ev["stop_mult"] * atr
        st = ep - risk if side > 0 else ep + risk
        tg = ep + ev["tgt_r"] * risk if side > 0 else ep - ev["tgt_r"] * risk
        prod = ev["prod"]
        spec = SPEC_MNQ if prod == "MNQ" else SPEC_MES
        qty = 1
        
        exit_ts = None
        exit_px = 0.0
        exit_reason = ""
        bars_held = 0
        
        o_arr = d["open"]
        h_arr = d["high"]
        l_arr = d["low"]
        c_arr = d["close"]
        sod_arr = d["sod"]
        date_arr = d["date"]
        ts_arr = d["ts"]
        n_bars = len(o_arr)
        
        for k in range(idx, n_bars):
            if date_arr[k] != ev["date"]:
                exit_ts = ts_arr[k]
                exit_px = o_arr[k]
                exit_reason = "eod"
                break
                
            bars_held += 1
            if side > 0:
                if l_arr[k] <= st:
                    exit_ts = ts_arr[k]; exit_px = st; exit_reason = "stop"; break
                elif h_arr[k] >= tg:
                    exit_ts = ts_arr[k]; exit_px = tg; exit_reason = "target"; break
            else:
                if h_arr[k] >= st:
                    exit_ts = ts_arr[k]; exit_px = st; exit_reason = "stop"; break
                elif l_arr[k] <= tg:
                    exit_ts = ts_arr[k]; exit_px = tg; exit_reason = "target"; break
                    
            if bars_held >= ev["hold"] or sod_arr[k] >= 955:
                exit_ts = ts_arr[k]; exit_px = c_arr[k]; exit_reason = "timeout"; break
                
        if exit_ts is None:
            continue
            
        active_until = exit_ts
        gross_pts = side * (exit_px - ep)
        gross_dlr = gross_pts / spec["tick"] * spec["pv"] * qty
        fee = rt_cost(prod, qty)
        net_dlr = gross_dlr - fee
        running_pnl += net_dlr
        
        executed.append({
            "ts": ev["ts"], "year": ev["year"], "sleeve": ev["sleeve"],
            "prod": prod, "side": side, "qty": qty, "net_dlr": net_dlr,
            "running_pnl": running_pnl
        })
        
    df_res = pd.DataFrame(executed)
    if len(df_res) == 0:
        print(f"{name}: 0 trades!")
        return df_res
        
    tot = df_res.net_dlr.sum()
    pre = df_res[df_res.year < 2020].net_dlr.sum()
    post = df_res[df_res.year >= 2020].net_dlr.sum()
    yearly = df_res.groupby("year")["net_dlr"].sum()
    pos_y = (yearly > 0).sum()
    
    cum = df_res.net_dlr.cumsum()
    mdd = (cum.cummax() - cum).max()
    exp_tr = tot / len(df_res)
    
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

# 1. Baseline Ungated Quad
ev_base = build_events("none")
simulate_engine(ev_base, "1. UNGATED BASELINE QUAD (All trades allowed)")

# 2. Directionally Gated Quad (Filter Neutral days, trade ONLY in predicted direction)
ev_dir = build_events("directional")
simulate_engine(ev_dir, "2. DIRECTIONALLY GATED QUAD (Trade ONLY on Predicted Days in Predicted Direction)")

# 3. Directionally Gated Quad (Allow Neutral days without filter)
ev_dir_neut = build_events("directional_allow_neutral")
simulate_engine(ev_dir_neut, "3. DIRECTIONALLY GATED QUAD (Gate on Predicted Days, Standard on Neutral Days)")

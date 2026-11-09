"""Research Protocol: Systematic Enhancements to AG Quad Champion on 2010-2023 Training Data.
Strict data integrity:
- Evaluated strictly on Training data (2010-2023, 14 continuous years).
- Validation (2024-2025) and Test (2026) remain 100% sealed.
- Micro costs: 0.61/side commission, 1.75 tick MNQ / 1.0 tick MES spread, 1.0 tick slippage/side.
- Global router: Strict 1-contract max limit across entire account. Priority: Sleeve 1 > 2 > 3 > 4.
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

# Add ET timestamps
for b in (b_mnq_30, b_mnq_60, b_mes_30):
    et = b.timestamp_utc.dt.tz_convert("America/New_York")
    b["sod"] = et.dt.hour * 60 + et.dt.minute
    b["date"] = et.dt.date
    b["year"] = et.dt.year

# Filter to RTH
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

# Pre-extract numpy arrays for blazing speed
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

print("Building candidate trade events...", flush=True)
events = []

# S1: MNQ 30m Morning (09:45-12:00)
d = data_dict["mnq30"]
for i in range(len(d["open"]) - 1):
    if d["date"][i] != d["date"][i+1]: continue
    if d["sig_s1"][i] != 0 and (570 <= d["sod"][i] <= 690):
        events.append({
            "ts": d["ts"][i+1], "date": d["date"][i], "year": d["year"][i],
            "sleeve": 1, "prod": "MNQ", "side": d["sig_s1"][i],
            "start_idx": i+1, "entry_px": d["open"][i+1], "atr": d["atr_s1"][i],
            "stop_mult": 1.5, "tgt_r": 3.5, "hold": 8, "data_key": "mnq30"
        })

# S2: MNQ 60m Macro (10:00-12:00)
d = data_dict["mnq60"]
for i in range(len(d["open"]) - 1):
    if d["date"][i] != d["date"][i+1]: continue
    if d["sig_s2"][i] != 0 and (540 <= d["sod"][i] <= 660):
        events.append({
            "ts": d["ts"][i+1], "date": d["date"][i], "year": d["year"][i],
            "sleeve": 2, "prod": "MNQ", "side": d["sig_s2"][i],
            "start_idx": i+1, "entry_px": d["open"][i+1], "atr": d["atr_s2"][i],
            "stop_mult": 1.25, "tgt_r": 4.0, "hold": 8, "data_key": "mnq60"
        })

# S3: MNQ 30m Afternoon (13:30-15:15)
d = data_dict["mnq30"]
for i in range(len(d["open"]) - 1):
    if d["date"][i] != d["date"][i+1]: continue
    if d["sig_s3"][i] != 0 and (780 <= d["sod"][i] <= 870):
        events.append({
            "ts": d["ts"][i+1], "date": d["date"][i], "year": d["year"][i],
            "sleeve": 3, "prod": "MNQ", "side": d["sig_s3"][i],
            "start_idx": i+1, "entry_px": d["open"][i+1], "atr": d["atr_s3"][i],
            "stop_mult": 1.5, "tgt_r": 4.0, "hold": 4, "data_key": "mnq30"
        })

# S4: MES 30m Trend (09:45-15:30)
d = data_dict["mes30"]
for i in range(len(d["open"]) - 1):
    if d["date"][i] != d["date"][i+1]: continue
    if d["sig_s4"][i] != 0 and (570 <= d["sod"][i] <= 900):
        events.append({
            "ts": d["ts"][i+1], "date": d["date"][i], "year": d["year"][i],
            "sleeve": 4, "prod": "MES", "side": d["sig_s4"][i],
            "start_idx": i+1, "entry_px": d["open"][i+1], "atr": d["atr_s4"][i],
            "stop_mult": 1.25, "tgt_r": 2.5, "hold": 12, "data_key": "mes30"
        })

df_ev = pd.DataFrame(events).sort_values(["ts", "sleeve"]).reset_index(drop=True)
print(f"Total candidate trade events: {len(df_ev)}", flush=True)

def run_simulation(name, exit_sod=955, dynamic_scale=False, moc_exit_sod=955):
    executed = []
    active_until = pd.Timestamp("1970-01-01", tz="UTC")
    running_pnl = 0.0
    
    for _, ev in df_ev.iterrows():
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
        if dynamic_scale and ev["sleeve"] == 1 and running_pnl >= 2000.0:
            qty = 2
            
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
                    
            if bars_held >= ev["hold"] or sod_arr[k] >= moc_exit_sod:
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
            "prod": prod, "side": side, "qty": qty, "net_dlr": net_dlr
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

run_simulation("1. BASELINE CHAMPION AG_QUAD (Strict 1c, 15:55 Exit)")
run_simulation("2. ENHANCEMENT A: 15:30 MOC AVOIDANCE (Exit by 15:30 ET)", moc_exit_sod=930)
run_simulation("3. ENHANCEMENT B: DYNAMIC SCALING (1ct Base, 2ct on S1 when Buffer > $2,000)", dynamic_scale=True)
run_simulation("4. COMBINED OPTIMAL ENHANCEMENT (15:30 Exit + Dynamic Scaling)", moc_exit_sod=930, dynamic_scale=True)

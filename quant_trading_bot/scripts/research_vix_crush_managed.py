"""Research & Audit: Managed VIX Term Structure Crush Shock Strategy.
Mechanism:
VIX / VIX3M term structure reflects institutional option hedging demand.
Prior-day Close: If 1-day delta in (VIX/VIX3M) <= -0.02 (panic subsiding, front VIX crushes relative to 3M VIX),
AND Morning 09:30-10:00 session confirms with positive upside drift (morn_ret > 0):
Enter Long at 10:00 close with Stop Loss and Target.

EVALUATED STRICTLY ON TRAINING DATA (2010-2023, 14 FULL YEARS).
DO NOT TOUCH VALIDATION (2024-2025) OR TEST (2026).
Micro costs: 0.61/side, 1.75 tick MNQ, 1.0 tick MES, 1.0 tick slippage.
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
from numba import njit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import mass_1m_search as m1

COMM, SLIP = 0.61, 1.0
SPEC = {"MNQ": dict(tick=0.25, pv=0.5, spread=1.75), "MES": dict(tick=0.25, pv=1.25, spread=1.0)}

def rt_cost(prod):
    s = SPEC[prod]
    return (s["spread"] + 2 * SLIP) * s["pv"] + 2 * COMM

print("Loading continuous 15m Training bars for MNQ and MES (2010-2023)...")
b_mnq = m1.load_bars("MNQ", 15, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]].copy()
b_mes = m1.load_bars("MES", 15, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]].copy()

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
vix_df["ratio_d3"] = vix_df["ratio"].diff(3)

# Point-in-time shift: signal available for trading on day t must be from close of day t-1!
vix_df["trade_date"] = vix_df["date"].shift(-1)

date_to_d1 = dict(zip(vix_df["trade_date"], vix_df["ratio_d1"]))
date_to_d3 = dict(zip(vix_df["trade_date"], vix_df["ratio_d3"]))
date_to_ratio = dict(zip(vix_df["trade_date"], vix_df["ratio"]))

@njit(cache=True)
def sim_vix_crush(o, h, l, c, atr, sig, day, sod, stop_mult, tgt_r, hold, flat, cost, tick_size, point_val):
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
        if pos != 0:
            ex = False
            px = 0.0
            if day[i] != eday: ex = True; px = o[i]
            elif pos > 0 and l[i] <= st: ex = True; px = st
            elif pos < 0 and h[i] >= st: ex = True; px = st
            elif pos > 0 and h[i] >= tg: ex = True; px = tg
            elif pos < 0 and l[i] <= tg: ex = True; px = tg
            elif (i - ei >= hold) or (sod[i] + 15 >= flat): ex = True; px = c[i]
            if ex:
                pnl[i] += pos * (px - ep) / tick_size * point_val - cost
                pos = 0
                ntr += 1
                
        # Enter at 10:00 close (sod 585)
        if pos == 0 and sig[i] != 0 and sod[i] == 585 and i + 1 < n and day[i + 1] == day[i] and atr[i] > 0:
            pos = sig[i]
            ep = o[i + 1] # 10:00 open
            risk = stop_mult * atr[i]
            st = ep - risk if pos > 0 else ep + risk
            tg = ep + tgt_r * risk if pos > 0 else ep - tgt_r * risk
            ei = i + 1
            eday = day[i]
            
    return pnl, ntr

def audit_vix_crush(prod, b):
    et = b.timestamp_utc.dt.tz_convert("America/New_York")
    b["sod"] = et.dt.hour * 60 + et.dt.minute
    b["date"] = et.dt.date
    b["year"] = et.dt.year
    
    rth = b[(b.sod >= 570) & (b.sod <= 955)].reset_index(drop=True)
    rth["day"] = pd.factorize(rth.date)[0]
    
    # Morning 09:30-10:00 return
    g = rth.groupby("date")
    o930 = g.apply(lambda d: d.loc[d.sod == 570, "open"].iloc[0] if (d.sod == 570).any() else np.nan)
    c1000 = g.apply(lambda d: d.loc[d.sod == 585, "close"].iloc[0] if (d.sod == 585).any() else np.nan)
    
    morn_ret_dict = ((c1000 - o930) / o930).to_dict()
    
    tr = np.maximum(rth.high - rth.low, np.maximum((rth.high - rth.close.shift(1)).abs(), (rth.low - rth.close.shift(1)).abs()))
    atr = tr.rolling(14, min_periods=14).mean().bfill().to_numpy(float)
    
    o = rth.open.to_numpy(float)
    h = rth.high.to_numpy(float)
    l = rth.low.to_numpy(float)
    c = rth.close.to_numpy(float)
    sod = rth.sod.to_numpy(np.int64)
    day = rth.day.to_numpy(np.int64)
    year = rth.year.to_numpy(np.int64)
    cost = rt_cost(prod)
    spec = SPEC[prod]
    
    d1_arr = np.array([date_to_d1.get(d, np.nan) for d in rth.date])
    morn_arr = np.array([morn_ret_dict.get(d, 0.0) for d in rth.date])
    
    print(f"\n=======================================================")
    print(f"Auditing VIX Crush Shock Strategy on {prod} (2010-2023)")
    print(f"=======================================================")
    
    best_results = []
    for crush_th in [-0.015, -0.02, -0.025, -0.03]:
        for morn_th in [0.0, 0.001, 0.002]:
            sig = np.zeros(len(rth), dtype=np.int8)
            is_1000 = (sod == 585)
            # Signal: VIX term structure crushed yesterday, and morning shows positive price momentum
            long_cond = is_1000 & (d1_arr <= crush_th) & (morn_arr >= morn_th)
            sig[long_cond] = 1
            
            for stop in [1.25, 1.5, 2.0]:
                for tgt in [2.5, 3.5, 5.0]:
                    for hold in [12, 16, 24]:
                        pnl, ntr = sim_vix_crush(o, h, l, c, atr, sig, day, sod, stop, tgt, hold, 955, cost, spec["tick"], spec["pv"])
                        if ntr < 60: continue
                        s_pnl = pd.Series(pnl)
                        tot = float(s_pnl.sum())
                        pre = float(s_pnl[year < 2020].sum())
                        post = float(s_pnl[year >= 2020].sum())
                        yearly = s_pnl.groupby(year).sum()
                        pos_y = int((yearly > 0).sum())
                        cum = s_pnl.cumsum()
                        mdd = float((cum.cummax() - cum).max())
                        exp_tr = tot / ntr
                        
                        if ntr >= 50:
                            best_results.append({
                                "prod": prod, "crush_th": crush_th, "morn_th": morn_th,
                                "stop": stop, "tgt": tgt, "hold": hold,
                                "tot_net": tot, "pre_2020": pre, "post_2020": post,
                                "ntr": ntr, "exp_tr": exp_tr, "pos_yrs": pos_y, "mdd": mdd
                            })
                            
    df = pd.DataFrame(best_results)
    if len(df) > 0:
        df = df.sort_values("tot_net", ascending=False)
        print(f"Found {len(df)} qualifying VIX Crush configurations on {prod}!")
        print(df.head(10).to_string(index=False))
    else:
        print(f"No qualifying VIX Crush configurations met strict criteria on {prod}.")

audit_vix_crush("MNQ", b_mnq)
audit_vix_crush("MES", b_mes)

"""Research Hypothesis: 60-Minute Institutional Opening Range Breakout (ORB60).
Mechanism:
Between 09:30 and 10:30 ET, the primary institutional opening price discovery takes place,
overlapping with European morning positioning.
At 10:30 ET (sod 630), the 60-minute range (High and Low from 09:30 to 10:30) is established.
If the 10:30 bar closes above the 60m High -> Long breakout into afternoon.
If the 10:30 bar closes below the 60m Low -> Short breakout into afternoon.
Exit: Stop = Entry - Stop_Mult * ATR; Target = 3.0R - 5.0R or trailing stop; Flat by 15:55 ET.

EVALUATED STRICTLY ON TRAINING DATA (2010-2023, 14 FULL YEARS).
DO NOT TOUCH VALIDATION (2024-2025) OR TEST (2026).
Micro costs: 0.61/side commission, 1.75 tick MNQ, 1.0 tick MES, 1.0 tick slippage.
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

for b in (b_mnq, b_mes):
    et = b.timestamp_utc.dt.tz_convert("America/New_York")
    b["sod"] = et.dt.hour * 60 + et.dt.minute
    b["date"] = et.dt.date
    b["year"] = et.dt.year

@njit(cache=True)
def sim_orb60(o, h, l, c, atr, sig, day, sod, stop_mult, tgt_r, hold, flat, cost, tick_size, point_val):
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
                
        # Eligible breakout decision at 10:30 (sod 615 = 10:15-10:30 bar close) or 10:45 (sod 630 = 10:30-10:45 bar close)
        if pos == 0 and sig[i] != 0 and (sod[i] == 615 or sod[i] == 630) and i + 1 < n and day[i + 1] == day[i] and atr[i] > 0:
            pos = sig[i]
            ep = o[i + 1]
            risk = stop_mult * atr[i]
            st = ep - risk if pos > 0 else ep + risk
            tg = ep + tgt_r * risk if pos > 0 else ep - tgt_r * risk
            ei = i + 1
            eday = day[i]
            
    return pnl, ntr

def run_orb60_search(prod, b):
    rth = b[(b.sod >= 570) & (b.sod <= 955)].reset_index(drop=True)
    rth["day"] = pd.factorize(rth.date)[0]
    
    # Calculate 09:30-10:30 High and Low (sod 570, 585, 600, 615)
    g = rth.groupby("date")
    h60 = g.apply(lambda d: d.loc[d.sod.isin([570, 585, 600, 615]), "high"].max() if d.sod.isin([570, 585, 600, 615]).any() else np.nan)
    l60 = g.apply(lambda d: d.loc[d.sod.isin([570, 585, 600, 615]), "low"].min() if d.sod.isin([570, 585, 600, 615]).any() else np.nan)
    
    date_to_h60 = h60.to_dict()
    date_to_l60 = l60.to_dict()
    
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
    
    h60_arr = np.array([date_to_h60.get(d, np.nan) for d in rth.date])
    l60_arr = np.array([date_to_l60.get(d, np.nan) for d in rth.date])
    
    print(f"\nEvaluating ORB60 on {prod} (2010-2023 Training)...")
    
    best_results = []
    # Test buffer: breakout by close > h60 + buf * atr
    for buf in [0.0, 0.1, 0.25]:
        for dec_sod in [615, 630]: # 10:30 or 10:45 decision
            sig = np.zeros(len(rth), dtype=np.int8)
            is_dec = (sod == dec_sod)
            bull = is_dec & (c >= h60_arr + buf * atr)
            bear = is_dec & (c <= l60_arr - buf * atr)
            sig[bull] = 1
            sig[bear] = -1
            
            for stop in [1.25, 1.5, 2.0]:
                for tgt in [2.5, 3.5, 5.0]:
                    for hold in [12, 16, 20]:
                        pnl, ntr = sim_orb60(o, h, l, c, atr, sig, day, sod, stop, tgt, hold, 955, cost, spec["tick"], spec["pv"])
                        if ntr < 80: continue
                        s_pnl = pd.Series(pnl)
                        tot = float(s_pnl.sum())
                        pre = float(s_pnl[year < 2020].sum())
                        post = float(s_pnl[year >= 2020].sum())
                        yearly = s_pnl.groupby(year).sum()
                        pos_y = int((yearly > 0).sum())
                        cum = s_pnl.cumsum()
                        mdd = float((cum.cummax() - cum).max())
                        exp_tr = tot / ntr
                        
                        if tot > 4000 and pos_y >= 9 and pre > 500 and mdd < 1800:
                            best_results.append({
                                "prod": prod, "buf": buf, "dec_sod": dec_sod,
                                "stop": stop, "tgt": tgt, "hold": hold,
                                "tot_net": tot, "pre_2020": pre, "post_2020": post,
                                "ntr": ntr, "exp_tr": exp_tr, "pos_yrs": pos_y, "mdd": mdd
                            })
                            
    df = pd.DataFrame(best_results)
    if len(df) > 0:
        df = df.sort_values("tot_net", ascending=False)
        print(f"Found {len(df)} qualifying ORB60 configs on {prod}!")
        print(df.head(10).to_string(index=False))
    else:
        print(f"No qualifying ORB60 configs on {prod} met criteria.")

run_orb60_search("MNQ", b_mnq)
run_orb60_search("MES", b_mes)

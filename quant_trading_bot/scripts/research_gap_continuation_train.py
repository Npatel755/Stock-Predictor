"""Research: Gap Continuation (Gap-and-Go) with Managed Stops and Targets.
EVALUATED STRICTLY ON TRAINING DATA (2010-2023, 14 YEARS).
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

for b in (b_mnq, b_mes):
    et = b.timestamp_utc.dt.tz_convert("America/New_York")
    b["sod"] = et.dt.hour * 60 + et.dt.minute
    b["date"] = et.dt.date
    b["year"] = et.dt.year

@njit(cache=True)
def sim_gap_continuation(o, h, l, c, atr, sig, day, sod, stop_mult, tgt_r, hold, flat, cost, tick_size, point_val):
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
                
        # Enter at 09:30 open (sod == 570)
        if pos == 0 and sig[i] != 0 and sod[i] == 570 and i + 1 < n and day[i + 1] == day[i] and atr[i] > 0:
            pos = sig[i]
            ep = o[i] # enter at open of 09:30
            risk = stop_mult * atr[i]
            st = ep - risk if pos > 0 else ep + risk
            tg = ep + tgt_r * risk if pos > 0 else ep - tgt_r * risk
            ei = i
            eday = day[i]
            
    return pnl, ntr

def run_gap_search(prod, b):
    rth = b[(b.sod >= 570) & (b.sod <= 955)].reset_index(drop=True)
    rth["day"] = pd.factorize(rth.date)[0]
    
    g = rth.groupby("date")
    dates = sorted(list(g.groups.keys()))
    
    date_to_gap = {}
    for i in range(1, len(dates)):
        prev_d = dates[i-1]
        curr_d = dates[i]
        grp_prev = g.get_group(prev_d)
        grp_curr = g.get_group(curr_d)
        
        prior_close = grp_prev.iloc[-1]["close"]
        row_0930 = grp_curr[grp_curr.sod == 570]
        if len(row_0930) == 0: continue
        today_open = row_0930.iloc[0]["open"]
        gap_pct = (today_open - prior_close) / prior_close
        date_to_gap[curr_d] = gap_pct
        
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
    
    gap_arr = np.array([date_to_gap.get(d, 0.0) for d in rth.date])
    
    print(f"\nEvaluating Gap Continuation on {prod} (2010-2023 Training)...")
    
    best = []
    for gap_th in [0.002, 0.003, 0.005, 0.008]:
        sig = np.zeros(len(rth), dtype=np.int8)
        is_0930 = (sod == 570)
        sig[is_0930 & (gap_arr >= gap_th)] = 1
        sig[is_0930 & (gap_arr <= -gap_th)] = -1
        
        for stop in [1.0, 1.5, 2.0]:
            for tgt in [2.0, 3.0, 4.0]:
                for hold in [8, 16, 24]:
                    pnl, ntr = sim_gap_continuation(o, h, l, c, atr, sig, day, sod, stop, tgt, hold, 955, cost, spec["tick"], spec["pv"])
                    if ntr < 50: continue
                    s_pnl = pd.Series(pnl)
                    tot = float(s_pnl.sum())
                    pre = float(s_pnl[year < 2020].sum())
                    post = float(s_pnl[year >= 2020].sum())
                    yearly = s_pnl.groupby(year).sum()
                    pos_y = int((yearly > 0).sum())
                    cum = s_pnl.cumsum()
                    mdd = float((cum.cummax() - cum).max())
                    
                    if tot > 3000 and pos_y >= 9 and pre > 0 and mdd < 2000:
                        best.append({
                            "prod": prod, "gap_th": gap_th, "stop": stop, "tgt": tgt, "hold": hold,
                            "tot_net": tot, "pre_2020": pre, "post_2020": post,
                            "ntr": ntr, "exp_tr": tot/ntr, "pos_yrs": pos_y, "mdd": mdd
                        })
                        
    df = pd.DataFrame(best)
    if len(df) > 0:
        df = df.sort_values("tot_net", ascending=False)
        print(f"Found {len(df)} qualifying Gap Continuation configs on {prod}:")
        print(df.head(10).to_string(index=False))
    else:
        print(f"No qualifying Gap Continuation configs on {prod} met criteria.")

run_gap_search("MNQ", b_mnq)
run_gap_search("MES", b_mes)

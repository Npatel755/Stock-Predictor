"""Research: Intraday VWAP Deviation Mean Reversion on CME Micro Futures.
Mechanism:
Intraday institutional execution algorithms (VWAP/TWAP) operate by providing liquidity
when price deviates substantially from the session VWAP.
When price extends >= 1.5 - 2.5 standard deviations from the session VWAP between 10:30 and 14:00 ET:
- If Price > VWAP + k * StDev: Fade Short, Target = VWAP, Stop = Entry + Stop_Mult * ATR.
- If Price < VWAP - k * StDev: Fade Long, Target = VWAP, Stop = Entry - Stop_Mult * ATR.
Exit at 15:55 ET flat if target not hit.

EVALUATED STRICTLY ON TRAINING DATA (2010-2023, 14 YEARS).
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
b_mnq = m1.load_bars("MNQ", 15, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close", "volume"]].copy()
b_mes = m1.load_bars("MES", 15, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close", "volume"]].copy()

@njit(cache=True)
def sim_vwap_fade(o, h, l, c, atr, vwap, vwap_std, day, sod, k_std, stop_mult, hold, flat, cost, tick_size, point_val):
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
                
        # Eligible entry window: 10:30 to 14:00 (sod 630 to 840)
        if pos == 0 and (630 <= sod[i] <= 840) and vwap_std[i] > 0 and atr[i] > 0 and i + 1 < n and day[i + 1] == day[i]:
            upper_band = vwap[i] + k_std * vwap_std[i]
            lower_band = vwap[i] - k_std * vwap_std[i]
            
            # Short Fade: close crossed above upper band
            if c[i] >= upper_band:
                pos = -1
                ep = o[i + 1]
                risk = stop_mult * atr[i]
                st = ep + risk
                tg = vwap[i] # target is reversion to session VWAP
                if tg >= ep: # target must be below entry for short
                    tg = ep - 0.5 * risk
                ei = i + 1
                eday = day[i]
            # Long Fade: close crossed below lower band
            elif c[i] <= lower_band:
                pos = 1
                ep = o[i + 1]
                risk = stop_mult * atr[i]
                st = ep - risk
                tg = vwap[i] # target is reversion to session VWAP
                if tg <= ep: # target must be above entry for long
                    tg = ep + 0.5 * risk
                ei = i + 1
                eday = day[i]
                
    return pnl, ntr

def run_vwap_fade_search(prod, b):
    et = b.timestamp_utc.dt.tz_convert("America/New_York")
    b["sod"] = et.dt.hour * 60 + et.dt.minute
    b["date"] = et.dt.date
    b["year"] = et.dt.year
    
    rth = b[(b.sod >= 570) & (b.sod <= 955)].reset_index(drop=True)
    rth["day"] = pd.factorize(rth.date)[0]
    
    # Calculate intraday session VWAP and cumulative volume-weighted variance
    # Typical price = (H + L + C) / 3
    rth["typ"] = (rth.high + rth.low + rth.close) / 3.0
    rth["pv"] = rth["typ"] * rth["volume"]
    
    # Cumulative per day
    g = rth.groupby("date")
    rth["cum_vol"] = g["volume"].cumsum()
    rth["cum_pv"] = g["pv"].cumsum()
    rth["vwap"] = rth["cum_pv"] / rth["cum_vol"].replace(0, np.nan)
    
    # Intraday standard deviation of price around VWAP
    rth["dev_sq"] = ((rth["typ"] - rth["vwap"]) ** 2) * rth["volume"]
    rth["cum_dev_sq"] = g["dev_sq"].cumsum()
    rth["vwap_std"] = np.sqrt(rth["cum_dev_sq"] / rth["cum_vol"].replace(0, np.nan)).bfill()
    
    tr = np.maximum(rth.high - rth.low, np.maximum((rth.high - rth.close.shift(1)).abs(), (rth.low - rth.close.shift(1)).abs()))
    atr = tr.rolling(14, min_periods=14).mean().bfill().to_numpy(float)
    
    o = rth.open.to_numpy(float)
    h = rth.high.to_numpy(float)
    l = rth.low.to_numpy(float)
    c = rth.close.to_numpy(float)
    vwap_arr = rth.vwap.bfill().to_numpy(float)
    vwap_std_arr = rth.vwap_std.bfill().to_numpy(float)
    sod = rth.sod.to_numpy(np.int64)
    day = rth.day.to_numpy(np.int64)
    year = rth.year.to_numpy(np.int64)
    cost = rt_cost(prod)
    spec = SPEC[prod]
    
    print(f"\nEvaluating Intraday VWAP Mean Reversion on {prod} (2010-2023 Training)...")
    
    best = []
    for k_std in [1.5, 2.0, 2.5]:
        for stop_mult in [1.0, 1.5, 2.0]:
            for hold in [4, 8, 12, 16]:
                pnl, ntr = sim_vwap_fade(o, h, l, c, atr, vwap_arr, vwap_std_arr, day, sod, k_std, stop_mult, hold, 955, cost, spec["tick"], spec["pv"])
                if ntr < 50: continue
                s_pnl = pd.Series(pnl)
                tot = float(s_pnl.sum())
                pre = float(s_pnl[year < 2020].sum())
                post = float(s_pnl[year >= 2020].sum())
                yearly = s_pnl.groupby(year).sum()
                pos_y = int((yearly > 0).sum())
                cum = s_pnl.cumsum()
                mdd = float((cum.cummax() - cum).max())
                
                if tot > 3000 and pos_y >= 9 and pre > 500 and mdd < 1800:
                    best.append({
                        "prod": prod, "k_std": k_std, "stop": stop_mult, "hold": hold,
                        "tot_net": tot, "pre_2020": pre, "post_2020": post,
                        "ntr": ntr, "exp_tr": tot/ntr, "pos_yrs": pos_y, "mdd": mdd
                    })
                    
    df = pd.DataFrame(best)
    if len(df) > 0:
        df = df.sort_values("tot_net", ascending=False)
        print(f"Found {len(df)} qualifying VWAP Fade configs on {prod}:")
        print(df.head(10).to_string(index=False))
    else:
        print(f"No qualifying VWAP Fade configs on {prod} met criteria.")

run_vwap_fade_search("MNQ", b_mnq)
run_vwap_fade_search("MES", b_mes)

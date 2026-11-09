"""Research Protocol & Simulation: Volatility Squeeze Expansion (Bollinger inside Keltner).
Pre-registered hypothesis:
Periods of extreme volatility contraction (Bollinger Bands inside Keltner Channels) precede explosive directional moves.
When the squeeze releases, enter in the direction of the 20-period momentum oscillator.

EVALUATED STRICTLY ON TRAINING DATA (2010-2023, 14 YEARS).
DO NOT LOAD OR CONSULT VALIDATION (2024-2025) OR TEST (2026).
Micro costs: 0.61/side commission, 1.75 tick MNQ spread (1.0 tick MES), 1.0 tick slippage/side.
"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd
from numba import njit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'src'))

import mass_1m_search as m1

COMM, SLIP = 0.61, 1.0
SPEC = {"MNQ": dict(tick=0.25, pv=0.5, spread=1.75), "MES": dict(tick=0.25, pv=1.25, spread=1.0)}
rng = np.random.default_rng(20261109)

def rt_cost(prod):
    s = SPEC[prod]
    return (s["spread"] + 2 * SLIP) * s["pv"] + 2 * COMM

print("Loading 15m and 30m Training bars for MNQ and MES (2010-2023)...")
b_mnq_15 = m1.load_bars("MNQ", 15, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]].copy()
b_mes_15 = m1.load_bars("MES", 15, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]].copy()

# Add NY time features
for b in (b_mnq_15, b_mes_15):
    et = b.timestamp_utc.dt.tz_convert("America/New_York")
    b["sod"] = et.dt.hour * 60 + et.dt.minute
    b["date"] = et.dt.date
    b["year"] = et.dt.year
    b["weekday"] = et.dt.weekday

@njit(cache=True)
def sim_squeeze(o, h, l, c, atr, sig, day, sod, hold, stop_mult, tgt_r, s0, s1, flat, cost, tick_size, point_val):
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
                
        if pos == 0 and sig[i] != 0 and sod[i] >= s0 and sod[i] < s1 and i + 1 < n and day[i + 1] == day[i] and atr[i] > 0:
            pos = sig[i]
            ep = o[i + 1] # enter next bar open
            risk = stop_mult * atr[i]
            st = ep - risk if pos > 0 else ep + risk
            tg = ep + tgt_r * risk if pos > 0 else ep - tgt_r * risk
            ei = i + 1
            eday = day[i]
            
    return pnl, ntr

def compute_squeeze_signals(bars, bb_mult=2.0, kc_mult=1.5, length=20):
    c = bars["close"]
    h = bars["high"]
    l = bars["low"]
    
    # Bollinger Bands
    sma = c.rolling(length, min_periods=length).mean()
    std = c.rolling(length, min_periods=length).std()
    bb_up = sma + bb_mult * std
    bb_dn = sma - bb_mult * std
    
    # Keltner Channels
    prev_c = c.shift(1)
    tr = np.maximum(h - l, np.maximum((h - prev_c).abs(), (l - prev_c).abs()))
    atr = tr.rolling(length, min_periods=length).mean()
    kc_up = sma + kc_mult * atr
    kc_dn = sma - kc_mult * atr
    
    # Squeeze condition
    in_squeeze = (bb_up < kc_up) & (bb_dn > kc_dn)
    
    # Squeeze release (was in squeeze, now breaking out)
    squeeze_release = in_squeeze.shift(1).fillna(False) & (~in_squeeze)
    
    # Direction: momentum vs SMA
    mom = c - sma
    
    sig = np.zeros(len(bars), dtype=np.int8)
    sig[squeeze_release & (mom > 0)] = 1
    sig[squeeze_release & (mom < 0)] = -1
    
    # ATR for stop calculation
    tr14 = tr.rolling(14, min_periods=14).mean().bfill().to_numpy(float)
    return sig, tr14

print("\n" + "=" * 90)
print("EVALUATING VOLATILITY SQUEEZE ON TRAINING DATA (2010-2023, 14 YEARS)")
print("=" * 90)

results = []

for prod, b in [("MNQ", b_mnq_15), ("MES", b_mes_15)]:
    b["day"] = pd.factorize(b.date)[0]
    o = b.open.to_numpy(float)
    h = b.high.to_numpy(float)
    l = b.low.to_numpy(float)
    c = b.close.to_numpy(float)
    sod = b.sod.to_numpy(np.int64)
    day = b.day.to_numpy(np.int64)
    year = b.year.to_numpy(np.int64)
    cost = rt_cost(prod)
    spec = SPEC[prod]
    
    for length in [16, 20, 24]:
        for kc_mult in [1.25, 1.5, 1.75]:
            sig, atr = compute_squeeze_signals(b, bb_mult=2.0, kc_mult=kc_mult, length=length)
            
            for stop_atr in [1.25, 1.5, 2.0]:
                for tgt_r in [2.5, 3.0, 4.0]:
                    for hold in [8, 12, 16]:
                        pnl, ntr = sim_squeeze(o, h, l, c, atr, sig, day, sod, hold, stop_atr, tgt_r, 585, 810, 955, cost, spec["tick"], spec["pv"])
                        if ntr < 100: continue
                        s_pnl = pd.Series(pnl)
                        tot_net = float(s_pnl.sum())
                        yearly = s_pnl.groupby(year).sum()
                        pos_yrs = int(sum(yearly > 0))
                        exp_tr = tot_net / ntr
                        
                        pre_2020 = float(s_pnl[year < 2020].sum())
                        post_2020 = float(s_pnl[year >= 2020].sum())
                        
                        cum = s_pnl.cumsum()
                        mdd = float((cum.cummax() - cum).max())
                        
                        if tot_net > 5000 and pos_yrs >= 10 and pre_2020 > 500 and mdd < 1800:
                            results.append({
                                "prod": prod, "len": length, "kc": kc_mult, "stop": stop_atr, "tgt": tgt_r, "hold": hold,
                                "tot_net": tot_net, "pre_2020": pre_2020, "post_2020": post_2020,
                                "ntr": ntr, "exp_tr": exp_tr, "pos_yrs": pos_yrs, "mdd": mdd
                            })

df_res = pd.DataFrame(results)
if len(df_res) > 0:
    df_res = df_res.sort_values("tot_net", ascending=False)
    print(f"\nFound {len(df_res)} qualified Volatility Squeeze configurations on Training (2010-2023)!")
    print(df_res.head(15).to_string(index=False))
else:
    print("Standard Volatility Squeeze did not meet >= 10/14 years and pre-2020 > $500 threshold.")
    print("Testing top unconstrained configurations...")

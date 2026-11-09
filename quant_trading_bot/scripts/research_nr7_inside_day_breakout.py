"""Research Protocol & Simulation: Daily Compression Gated Breakouts (NR7 & Inside Day).
Pre-registered hypothesis:
Standard intraday breakouts fail on choppy rotational days.
However, when the PRIOR session is an NR7 (Narrow Range 7: range is narrowest of the past 7 days)
or an Inside Day (High < High[t-1] and Low > Low[t-1]), volatility is compressed at the daily level.
On these specific sessions, opening range breakouts (09:45 or 10:00 ET) have high follow-through into the close.

EVALUATED STRICTLY ON TRAINING DATA (2010-2023, 14 YEARS).
DO NOT LOAD OR CONSULT VALIDATION (2024-2025) OR TEST (2026).
Micro costs: 0.61/side commission, 1.75 tick MNQ spread, 1.0 tick slippage/side.
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

print("Loading continuous 15m Training bars for MNQ (2010-2023)...")
b_mnq = m1.load_bars("MNQ", 15, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]].copy()

et = b_mnq.timestamp_utc.dt.tz_convert("America/New_York")
b_mnq["sod"] = et.dt.hour * 60 + et.dt.minute
b_mnq["date"] = et.dt.date
b_mnq["year"] = et.dt.year

# Filter to RTH
rth = b_mnq[(b_mnq.sod >= 570) & (b_mnq.sod < 960)].reset_index(drop=True)

# 1. Compute Daily Bar Properties
g = rth.groupby("date")
d_high = g["high"].max()
d_low = g["low"].min()
d_close = g["close"].last()
d_open = g["open"].first()
d_range = d_high - d_low

daily_df = pd.DataFrame({
    "high": d_high, "low": d_low, "open": d_open, "close": d_close, "range": d_range
})
daily_df["year"] = pd.to_datetime(daily_df.index).year

# NR7: today's range is the narrowest of the last 7 sessions
daily_df["min_range_7"] = daily_df["range"].rolling(7, min_periods=7).min()
daily_df["is_nr7"] = (daily_df["range"] == daily_df["min_range_7"])

# Inside Day: High < High[t-1] and Low > Low[t-1]
daily_df["is_inside"] = (daily_df["high"] < daily_df["high"].shift(1)) & (daily_df["low"] > daily_df["low"].shift(1))

# NR4: today's range is narrowest of last 4 sessions
daily_df["min_range_4"] = daily_df["range"].rolling(4, min_periods=4).min()
daily_df["is_nr4"] = (daily_df["range"] == daily_df["min_range_4"])

# Prior session properties (known before 09:30 open of date D)
daily_df["prior_nr7"] = daily_df["is_nr7"].shift(1).fillna(False)
daily_df["prior_inside"] = daily_df["is_inside"].shift(1).fillna(False)
daily_df["prior_nr4_inside"] = (daily_df["is_nr4"] & daily_df["is_inside"]).shift(1).fillna(False)
daily_df["prior_compression"] = daily_df["prior_nr7"] | daily_df["prior_inside"]

print(f"Total training sessions: {len(daily_df)}")
print(f"Prior NR7 sessions: {daily_df['prior_nr7'].sum()} ({daily_df['prior_nr7'].mean()*100:.1f}%)")
print(f"Prior Inside Day sessions: {daily_df['prior_inside'].sum()} ({daily_df['prior_inside'].mean()*100:.1f}%)")
print(f"Prior Compression (NR7 or Inside): {daily_df['prior_compression'].sum()} ({daily_df['prior_compression'].mean()*100:.1f}%)")

# 2. Map compression flags to 15m bars
date_to_nr7 = daily_df["prior_nr7"].to_dict()
date_to_inside = daily_df["prior_inside"].to_dict()
date_to_comp = daily_df["prior_compression"].to_dict()

rth["day"] = pd.factorize(rth.date)[0]
is_comp_arr = np.array([date_to_comp.get(d, False) for d in rth.date])
is_nr7_arr = np.array([date_to_nr7.get(d, False) for d in rth.date])
is_inside_arr = np.array([date_to_inside.get(d, False) for d in rth.date])

# 15m ATR
tr = np.maximum(rth.high - rth.low, np.maximum((rth.high - rth.close.shift(1)).abs(), (rth.low - rth.close.shift(1)).abs()))
atr = tr.rolling(14, min_periods=14).mean().bfill().to_numpy(float)

o = rth.open.to_numpy(float)
h = rth.high.to_numpy(float)
l = rth.low.to_numpy(float)
c = rth.close.to_numpy(float)
sod = rth.sod.to_numpy(np.int64)
day = rth.day.to_numpy(np.int64)
year = rth.year.to_numpy(np.int64)
cost = rt_cost("MNQ")

# Build Opening Range (09:30-10:00: first two 15m bars, sod 570 and 585)
# Breakout occurs if 10:00 bar (sod 600) closes above 09:30-10:00 high or below 09:30-10:00 low
@njit(cache=True)
def sim_compression_orb(o, h, l, c, atr, is_comp, day, sod, stop_mult, tgt_r, hold, flat, cost):
    n = len(o)
    pnl = np.zeros(n)
    pos = 0
    ep = 0.0
    st = 0.0
    tg = 0.0
    ei = 0
    eday = -1
    ntr = 0
    
    orb_h = 0.0
    orb_l = 0.0
    cur_day = -1
    
    for i in range(n):
        if day[i] != cur_day:
            cur_day = day[i]
            orb_h = 0.0
            orb_l = 0.0
            
        # Record 09:30 - 10:00 range (bars 570 and 585)
        if sod[i] == 570:
            orb_h = h[i]
            orb_l = l[i]
        elif sod[i] == 585:
            if h[i] > orb_h: orb_h = h[i]
            if l[i] < orb_l: orb_l = l[i]
            
        # Position management
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
                pnl[i] += pos * (px - ep) / 0.25 * 0.5 - cost
                pos = 0
                ntr += 1
                
        # Entry check: at 10:00 close (sod == 600) or 10:15 close (sod == 615)
        if pos == 0 and is_comp[i] and (sod[i] >= 600) and (sod[i] <= 630) and i + 1 < n and day[i + 1] == day[i] and atr[i] > 0 and orb_h > 0:
            sig = 0
            if c[i] > orb_h:
                sig = 1
            elif c[i] < orb_l:
                sig = -1
                
            if sig != 0:
                pos = sig
                ep = o[i + 1] # enter next bar open
                risk = stop_mult * atr[i]
                st = ep - risk if pos > 0 else ep + risk
                tg = ep + tgt_r * risk if pos > 0 else ep - tgt_r * risk
                ei = i + 1
                eday = day[i]
                
    return pnl, ntr

print("\n" + "=" * 90)
print("EVALUATING DAILY COMPRESSION GATED ORB ON TRAINING DATA (2010-2023)")
print("=" * 90)

configs = []

for comp_name, comp_mask in [("Prior_Compression (NR7 or Inside)", is_comp_arr), 
                             ("Prior_NR7_Only", is_nr7_arr), 
                             ("Prior_Inside_Only", is_inside_arr)]:
    for stop_atr in [1.25, 1.5, 2.0]:
        for tgt_r in [2.5, 3.0, 4.0]:
            for hold in [8, 12, 16, 20]:
                pnl, ntr = sim_compression_orb(o, h, l, c, atr, comp_mask, day, sod, stop_atr, tgt_r, hold, 955, cost)
                if ntr < 80: continue
                s_pnl = pd.Series(pnl)
                tot_net = float(s_pnl.sum())
                yearly = s_pnl.groupby(year).sum()
                pos_yrs = int(sum(yearly > 0))
                exp_tr = tot_net / ntr
                
                pre_2020 = float(s_pnl[year < 2020].sum())
                post_2020 = float(s_pnl[year >= 2020].sum())
                
                cum = s_pnl.cumsum()
                mdd = float((cum.cummax() - cum).max())
                
                if tot_net > 4000 and pos_yrs >= 10 and pre_2020 > 500 and mdd < 1500:
                    configs.append({
                        "filter": comp_name, "stop": stop_atr, "tgt": tgt_r, "hold": hold,
                        "tot_net": tot_net, "pre_2020": pre_2020, "post_2020": post_2020,
                        "ntr": ntr, "exp_tr": exp_tr, "pos_yrs": pos_yrs, "mdd": mdd
                    })

df_conf = pd.DataFrame(configs)
if len(df_conf) > 0:
    df_conf = df_conf.sort_values("tot_net", ascending=False)
    print(f"\nFound {len(df_conf)} qualified Compression ORB configurations on Training (2010-2023)!")
    print(df_conf.head(15).to_string(index=False))
else:
    print("Testing broader parameter sweep...")
    for comp_name, comp_mask in [("Prior_Compression", is_comp_arr)]:
        for stop_atr in [1.5, 2.0]:
            for tgt_r in [3.0, 4.0]:
                pnl, ntr = sim_compression_orb(o, h, l, c, atr, comp_mask, day, sod, stop_atr, tgt_r, 16, 955, cost)
                s_pnl = pd.Series(pnl)
                tot_net = float(s_pnl.sum())
                pre_2020 = float(s_pnl[year < 2020].sum())
                yearly = s_pnl.groupby(year).sum()
                pos_yrs = int(sum(yearly > 0))
                cum = s_pnl.cumsum()
                mdd = float((cum.cummax() - cum).max())
                print(f"Filter: {comp_name} | stop: {stop_atr} | tgt: {tgt_r} | Net: ${tot_net:.2f} | Pre-2020: ${pre_2020:.2f} | Tr: {ntr} | Exp: +${tot_net/ntr:.2f} | +Yrs: {pos_yrs}/14 | MaxDD: ${mdd:.2f}")

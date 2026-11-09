"""Research Protocol & Simulation: Asymmetric Higher-Timeframe Trend Pullback Engine.
Economic Mechanism:
Buying breakouts forces wide stops (1.5-2.0 ATR) at local tops, causing whipsaws and large drawdowns.
Pullback entries in the direction of an established 60m trend allow tight stops (0.75-1.0 ATR) 
and large reward-to-risk (3R-5R), drastically reducing drawdown while boosting expectancy.

Setup Rules:
1. Higher-Timeframe Macro Trend (60m):
   - Fast EMA (12) > Slow EMA (24) -> Macro Bull
   - Fast EMA (12) < Slow EMA (24) -> Macro Bear
2. Intraday Pullback (15m):
   - In Macro Bull: Price pulls back to or below the 15m 20-EMA (or 2+ consecutive lower closes)
   - Trigger: Close > Prior bar High (reversal confirmation)
   - In Macro Bear: Price pulls back to or above the 15m 20-EMA (or 2+ consecutive higher closes)
   - Trigger: Close < Prior bar Low
3. Execution Window: 09:45 to 13:30 ET.
4. Risk Management:
   - Stop Loss: 0.75 ATR to 1.0 ATR (tight!)
   - Target: 3.0R to 4.5R
   - Hold: 8 to 16 bars (2 to 4 hours)
   - Flat EOD: 15:55 ET.
5. Sizing: Strict 1 contract.

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
cost_mnq = (SPEC["MNQ"]["spread"] + 2 * SLIP) * SPEC["MNQ"]["pv"] + 2 * COMM
cost_mes = (SPEC["MES"]["spread"] + 2 * SLIP) * SPEC["MES"]["pv"] + 2 * COMM

print("Loading continuous 15m and 60m Training bars for MNQ (2010-2023)...")
b_15 = m1.load_bars("MNQ", 15, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]].copy()

# Add NY time
et = b_15.timestamp_utc.dt.tz_convert("America/New_York")
b_15["sod"] = et.dt.hour * 60 + et.dt.minute
b_15["date"] = et.dt.date
b_15["year"] = et.dt.year

# Filter to RTH
rth = b_15[(b_15.sod >= 570) & (b_15.sod < 960)].reset_index(drop=True)
rth["day"] = pd.factorize(rth.date)[0]

# Compute 15m Indicators
c = rth.close
h = rth.high
l = rth.low
o = rth.open
prev_c = c.shift(1)

# 15m 20-EMA
ema20_15 = c.ewm(span=20, adjust=False).mean()

# 60m trend proxy on 15m bars: 12-bar 60m EMA is ~48 bars on 15m; 24-bar 60m EMA is ~96 bars on 15m
ema_fast_htf = c.ewm(span=48, adjust=False).mean()
ema_slow_htf = c.ewm(span=96, adjust=False).mean()
htf_trend = (ema_fast_htf - ema_slow_htf)

# 15m ATR
tr = np.maximum(h - l, np.maximum((h - prev_c).abs(), (l - prev_c).abs()))
atr = tr.rolling(14, min_periods=14).mean().bfill().to_numpy(float)

# Pullback condition:
# In HTF Bull: low touches below ema20_15 or 2 consecutive down bars
pullback_bull = (l <= ema20_15) | ((c < prev_c) & (prev_c < c.shift(2)))
# Trigger: close > prior bar high
trigger_bull = (c > h.shift(1)) & (htf_trend > 0) & pullback_bull.shift(1).fillna(False)

# In HTF Bear: high touches above ema20_15 or 2 consecutive up bars
pullback_bear = (h >= ema20_15) | ((c > prev_c) & (prev_c > c.shift(2)))
# Trigger: close < prior bar low
trigger_bear = (c < l.shift(1)) & (htf_trend < 0) & pullback_bear.shift(1).fillna(False)

sig_pullback = np.zeros(len(rth), dtype=np.int8)
sig_pullback[trigger_bull] = 1
sig_pullback[trigger_bear] = -1

o_arr = o.to_numpy(float)
h_arr = h.to_numpy(float)
l_arr = l.to_numpy(float)
c_arr = c.to_numpy(float)
sod_arr = rth.sod.to_numpy(np.int64)
day_arr = rth.day.to_numpy(np.int64)
year_arr = rth.year.to_numpy(np.int64)

@njit(cache=True)
def sim_pullback(o, h, l, c, atr, sig, day, sod, hold, stop_mult, tgt_r, s0, s1, flat, cost, tick_size, point_val, long_only):
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
            if long_only and sig[i] < 0:
                continue
            pos = sig[i]
            ep = o[i + 1] # enter next bar open
            risk = stop_mult * atr[i]
            st = ep - risk if pos > 0 else ep + risk
            tg = ep + tgt_r * risk if pos > 0 else ep - tgt_r * risk
            ei = i + 1
            eday = day[i]
            
    return pnl, ntr

print("\n" + "=" * 90)
print("EVALUATING ASYMMETRIC TREND PULLBACK ON TRAINING DATA (2010-2023)")
print("=" * 90)

configs = []

for long_only in [True, False]:
    for stop_atr in [0.75, 1.0, 1.25]:
        for tgt_r in [2.5, 3.0, 3.5, 4.0]:
            for hold in [8, 12, 16]:
                for s1 in [720, 810]: # entry window up to 12:00 or 13:30
                    pnl, ntr = sim_pullback(o_arr, h_arr, l_arr, c_arr, atr, sig_pullback, day_arr, sod_arr, hold, stop_atr, tgt_r, 585, s1, 955, cost_mnq, 0.25, 0.5, long_only)
                    if ntr < 100: continue
                    s_pnl = pd.Series(pnl)
                    tot_net = float(s_pnl.sum())
                    yearly = s_pnl.groupby(year_arr).sum()
                    pos_yrs = int(sum(yearly > 0))
                    exp_tr = tot_net / ntr
                    
                    pre_2020 = float(s_pnl[year_arr < 2020].sum())
                    post_2020 = float(s_pnl[year_arr >= 2020].sum())
                    
                    cum = s_pnl.cumsum()
                    mdd = float((cum.cummax() - cum).max())
                    
                    if tot_net > 5000 and pos_yrs >= 10 and pre_2020 > 800 and mdd < 1200:
                        configs.append({
                            "long_only": long_only, "stop": stop_atr, "tgt": tgt_r, "hold": hold, "s1": s1,
                            "tot_net": tot_net, "pre_2020": pre_2020, "post_2020": post_2020,
                            "ntr": ntr, "exp_tr": exp_tr, "pos_yrs": pos_yrs, "mdd": mdd
                        })

df_conf = pd.DataFrame(configs)
if len(df_conf) > 0:
    df_conf = df_conf.sort_values("tot_net", ascending=False)
    print(f"\nFound {len(df_conf)} qualified Trend Pullback configurations on Training (2010-2023)!")
    print(df_conf.head(15).to_string(index=False))
else:
    print("Testing baseline parameter sweep...")
    for long_only in [True, False]:
        for stop_atr in [0.75, 1.0]:
            for tgt_r in [3.0, 4.0]:
                pnl, ntr = sim_pullback(o_arr, h_arr, l_arr, c_arr, atr, sig_pullback, day_arr, sod_arr, 12, stop_atr, tgt_r, 585, 780, 955, cost_mnq, 0.25, 0.5, long_only)
                s_pnl = pd.Series(pnl)
                tot_net = float(s_pnl.sum())
                pre_2020 = float(s_pnl[year_arr < 2020].sum())
                yearly = s_pnl.groupby(year_arr).sum()
                pos_yrs = int(sum(yearly > 0))
                cum = s_pnl.cumsum()
                mdd = float((cum.cummax() - cum).max())
                print(f"LongOnly: {long_only} | stop: {stop_atr} | tgt: {tgt_r} | Net: ${tot_net:.2f} | Pre-2020: ${pre_2020:.2f} | Tr: {ntr} | Exp: +${tot_net/ntr:.2f} | +Yrs: {pos_yrs}/14 | MaxDD: ${mdd:.2f}")

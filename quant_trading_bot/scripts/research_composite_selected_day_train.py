"""Research Protocol & Simulation: Composite Selected-Day Multi-Mechanism Engine.
Combines 3 independently placebo-verified day-selection signals on CME Micro Futures:
1. Signal 1 (Cross-Asset Divergence): NQ 30m return outperforms ES 30m return (z >= 1.0).
2. Signal 2 (Crabel Open-Drive): 09:30 open in extreme bottom 20%, 10:00 close in top 15% of 30m range, range >= 0.75 ATR.
3. Signal 3 (VIX Velocity Crush): Prior-day delta in (VIX/VIX3M) <= -0.015, morning 09:30-10:00 return > 0.

EVALUATED STRICTLY ON TRAINING DATA (2010-2023, 14 FULL YEARS).
DO NOT TOUCH VALIDATION (2024-2025) OR TEST (2026).
Micro costs: 0.61/side commission, 1.75 tick MNQ spread, 1.0 tick slippage.
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

def rt_cost(prod, qty=1):
    s = SPEC[prod]
    return ((s["spread"] + 2 * SLIP) * s["pv"] + 2 * COMM) * qty

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
vix_df["trade_date"] = vix_df["date"].shift(-1) # point-in-time prior close to next trade date

date_to_vix_d1 = dict(zip(vix_df["trade_date"], vix_df["ratio_d1"]))

et_mnq = b_mnq.timestamp_utc.dt.tz_convert("America/New_York")
b_mnq["sod"] = et_mnq.dt.hour * 60 + et_mnq.dt.minute
b_mnq["date"] = et_mnq.dt.date
b_mnq["year"] = et_mnq.dt.year

et_mes = b_mes.timestamp_utc.dt.tz_convert("America/New_York")
b_mes["sod"] = et_mes.dt.hour * 60 + et_mes.dt.minute
b_mes["date"] = et_mes.dt.date

rth_mnq = b_mnq[(b_mnq.sod >= 570) & (b_mnq.sod <= 955)].reset_index(drop=True)
rth_mes = b_mes[(b_mes.sod >= 570) & (b_mes.sod <= 955)].reset_index(drop=True)

g_mnq = rth_mnq.groupby("date")
g_mes = rth_mes.groupby("date")

# 1. Build NQ vs ES Spread Z-score
o930_mnq = g_mnq.apply(lambda d: d.loc[d.sod == 570, "open"].iloc[0] if (d.sod == 570).any() else np.nan)
c1000_mnq = g_mnq.apply(lambda d: d.loc[d.sod == 585, "close"].iloc[0] if (d.sod == 585).any() else np.nan)
h1000_mnq = g_mnq.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), "high"].max() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)
l1000_mnq = g_mnq.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), "low"].min() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)

o930_mes = g_mes.apply(lambda d: d.loc[d.sod == 570, "open"].iloc[0] if (d.sod == 570).any() else np.nan)
c1000_mes = g_mes.apply(lambda d: d.loc[d.sod == 585, "close"].iloc[0] if (d.sod == 585).any() else np.nan)

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

# Signal Definitions:
# Sig 1: Tech Leader
df_days["sig_leader"] = (df_days["spread_z"] >= 1.0).astype(int)
# Sig 2: Crabel Open Drive
df_days["sig_crabel"] = ((df_days["open_pos"] <= 0.20) & (df_days["close_pos"] >= 0.80)).astype(int)
# Sig 3: VIX Crush Shock
df_days["sig_vix"] = ((df_days["vix_d1"] <= -0.015) & (df_days["ret_mnq"] >= 0.001)).astype(int)

# Multi-Signal Composite Score (0 to 3)
df_days["score"] = df_days["sig_leader"] + df_days["sig_crabel"] + df_days["sig_vix"]

print("\n--- Day-Signal Distribution on 2010-2023 Training ---")
print(f"Total Trading Days: {len(df_days)}")
print(f"Days with Score >= 1 (Any signal): {(df_days.score >= 1).sum()} ({(df_days.score >= 1).mean()*100:.1f}%)")
print(f"Days with Score == 1: {(df_days.score == 1).sum()}")
print(f"Days with Score == 2: {(df_days.score == 2).sum()}")
print(f"Days with Score == 3 (All 3 aligned!): {(df_days.score == 3).sum()}")

# Map signals back to MNQ bars
date_to_score = df_days["score"].to_dict()
date_to_sig1 = df_days["sig_leader"].to_dict()
date_to_sig2 = df_days["sig_crabel"].to_dict()
date_to_sig3 = df_days["sig_vix"].to_dict()

rth_mnq["day"] = pd.factorize(rth_mnq.date)[0]
tr = np.maximum(rth_mnq.high - rth_mnq.low, np.maximum((rth_mnq.high - rth_mnq.close.shift(1)).abs(), (rth_mnq.low - rth_mnq.close.shift(1)).abs()))
atr = tr.rolling(14, min_periods=14).mean().bfill().to_numpy(float)

o = rth_mnq.open.to_numpy(float)
h = rth_mnq.high.to_numpy(float)
l = rth_mnq.low.to_numpy(float)
c = rth_mnq.close.to_numpy(float)
sod = rth_mnq.sod.to_numpy(np.int64)
day = rth_mnq.day.to_numpy(np.int64)
year = rth_mnq.year.to_numpy(np.int64)
spec = SPEC["MNQ"]

score_arr = np.array([date_to_score.get(d, 0) for d in rth_mnq.date])
sig1_arr = np.array([date_to_sig1.get(d, 0) for d in rth_mnq.date])
sig2_arr = np.array([date_to_sig2.get(d, 0) for d in rth_mnq.date])
sig3_arr = np.array([date_to_sig3.get(d, 0) for d in rth_mnq.date])

@njit(cache=True)
def sim_composite(o, h, l, c, atr, sig_score, min_score, dynamic_size, day, sod, stop_mult, tgt_r, hold, flat, comm, slip, pv, tick):
    n = len(o)
    pnl = np.zeros(n)
    pos = 0 # 0 or qty
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
            elif l[i] <= st: ex = True; px = st
            elif h[i] >= tg: ex = True; px = tg
            elif (i - ei >= hold) or (sod[i] + 15 >= flat): ex = True; px = c[i]
            if ex:
                cost = ((1.75 + 2 * slip) * pv + 2 * comm) * pos
                pnl[i] += pos * (px - ep) / tick * pv - cost
                pos = 0
                ntr += 1
                
        # Enter at 10:00 ET close (sod 585) on next bar open (sod 600)
        if pos == 0 and sod[i] == 585 and sig_score[i] >= min_score and i + 1 < n and day[i + 1] == day[i] and atr[i] > 0:
            qty = 1
            if dynamic_size and sig_score[i] >= 2:
                qty = 2
            pos = qty
            ep = o[i + 1]
            risk = stop_mult * atr[i]
            st = ep - risk
            tg = ep + tgt_r * risk
            ei = i + 1
            eday = day[i]
            
    return pnl, ntr

print(f"\n=========================================================================")
print(f"COMPOSITE ENSEMBLE EVALUATION ON MNQ (2010-2023 Training, 14 Years)")
print(f"=========================================================================")

# Test Configurations:
# 1. Any Signal (Score >= 1, Fixed 1 Contract)
# 2. Confluence Only (Score >= 2, Fixed 1 Contract)
# 3. Dynamic Scaling (Score == 1 -> 1 contract; Score >= 2 -> 2 contracts)
configs = [
    ("Union (Score >= 1, 1 Contract)", 1, False, 1.5, 4.0, 16),
    ("Union (Score >= 1, 1 Contract, 3.5R)", 1, False, 1.5, 3.5, 12),
    ("Confluence (Score >= 2, 1 Contract)", 2, False, 1.5, 4.0, 16),
    ("Dynamic Sizing (Score=1: 1ct, Score>=2: 2ct)", 1, True, 1.5, 4.0, 16),
    ("Dynamic Sizing (Score=1: 1ct, Score>=2: 2ct, 3.5R)", 1, True, 1.5, 3.5, 12),
]

for label, min_sc, dyn, stop_m, tgt_r, hold_b in configs:
    pnl, ntr = sim_composite(o, h, l, c, atr, score_arr, min_sc, dyn, day, sod, stop_m, tgt_r, hold_b, 955, COMM, SLIP, spec["pv"], spec["tick"])
    s_pnl = pd.Series(pnl)
    tot = float(s_pnl.sum())
    pre = float(s_pnl[year < 2020].sum())
    post = float(s_pnl[year >= 2020].sum())
    yearly = s_pnl.groupby(year).sum()
    pos_y = int((yearly > 0).sum())
    cum = s_pnl.cumsum()
    mdd = float((cum.cummax() - cum).max())
    exp_tr = tot / ntr if ntr else 0.0
    
    print(f"\n--- {label} ---")
    print(f"Total Net: ${tot:+.2f} | Trades: {ntr} ({ntr/14:.1f} tr/yr) | Exp: ${exp_tr:+.2f}/tr")
    print(f"Pre-2020 Era (2010-2019): ${pre:+.2f} (Exp: ${s_pnl[year < 2020].sum()/(year < 2020).sum() if ntr else 0:.2f})")
    print(f"Post-2020 Era (2020-2023): ${post:+.2f}")
    print(f"Positive Years: {pos_y} of 14 ({pos_y/14*100:.1f}%)")
    print(f"Max Continuous Drawdown: ${mdd:.2f} (Safety Cushion: ${2000 - mdd:+.2f} under $2,000 floor)")
    print("Yearly Breakdown:")
    for yr, val in yearly.items():
        print(f"  {yr}: ${val:+.2f}")

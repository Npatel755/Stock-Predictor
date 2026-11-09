"""Research Protocol: Two-Sided Symmetric Composite and Regime-Filtered Sizing.
Hypothesis:
1. Long-only strategies suffer large drawdowns during sustained equity bear markets (e.g. 2022: -$1,097 to -$1,718).
2. Because relative divergence continues symmetrically (as proven in pairs_1 and verified by Devin),
   trading both Long (when Tech leads/crush) AND Short (when Tech lags/shock) should hedge market beta,
   dramatically reduce max drawdown, and eliminate the 2022 drag.
3. Alternatively, a macro regime filter (Daily Close > 200 SMA) filters out bear-market long whipsaws.

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
vix_df["trade_date"] = vix_df["date"].shift(-1)

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

# Build 10:00 features
o930_mnq = g_mnq.apply(lambda d: d.loc[d.sod == 570, "open"].iloc[0] if (d.sod == 570).any() else np.nan)
c1000_mnq = g_mnq.apply(lambda d: d.loc[d.sod == 585, "close"].iloc[0] if (d.sod == 585).any() else np.nan)
h1000_mnq = g_mnq.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), "high"].max() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)
l1000_mnq = g_mnq.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), "low"].min() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)

# Daily closes for 200 SMA
daily_close_mnq = g_mnq.apply(lambda d: d.iloc[-1]["close"])
daily_sma200 = daily_close_mnq.rolling(200, min_periods=200).mean().shift(1) # prior day 200 SMA
date_to_sma200_gate = (daily_close_mnq.shift(1) > daily_sma200).to_dict()

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
df_days["vix_d1"] = [date_to_vix_d1.get(d, np.nan) for d in df_days.index]
df_days["above_sma200"] = [date_to_sma200_gate.get(d, False) for d in df_days.index]

# Long Signals:
df_days["long_leader"] = (df_days["spread_z"] >= 1.0).astype(int)
df_days["long_crabel"] = ((df_days["open_pos"] <= 0.20) & (df_days["close_pos"] >= 0.80)).astype(int)
df_days["long_vix"] = ((df_days["vix_d1"] <= -0.015) & (df_days["ret_mnq"] >= 0.001)).astype(int)
df_days["long_score"] = df_days["long_leader"] + df_days["long_crabel"] + df_days["long_vix"]

# Short Signals:
df_days["short_leader"] = (df_days["spread_z"] <= -1.0).astype(int)
df_days["short_crabel"] = ((df_days["open_pos"] >= 0.80) & (df_days["close_pos"] <= 0.20)).astype(int)
df_days["short_vix"] = ((df_days["vix_d1"] >= +0.02) & (df_days["ret_mnq"] <= -0.001)).astype(int)
df_days["short_score"] = df_days["short_leader"] + df_days["short_crabel"] + df_days["short_vix"]

# Net Direction Signal:
# If long_score > short_score -> +1 (or score diff)
# If short_score > long_score -> -1
df_days["net_sig"] = 0
df_days.loc[df_days.long_score > df_days.short_score, "net_sig"] = 1
df_days.loc[df_days.short_score > df_days.long_score, "net_sig"] = -1

# Map to 15m bars
date_to_long_score = df_days["long_score"].to_dict()
date_to_short_score = df_days["short_score"].to_dict()
date_to_net_sig = df_days["net_sig"].to_dict()
date_to_sma = df_days["above_sma200"].to_dict()

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

net_sig_arr = np.array([date_to_net_sig.get(d, 0) for d in rth_mnq.date], dtype=np.int8)
long_score_arr = np.array([date_to_long_score.get(d, 0) for d in rth_mnq.date], dtype=np.int8)
short_score_arr = np.array([date_to_short_score.get(d, 0) for d in rth_mnq.date], dtype=np.int8)
sma_gate_arr = np.array([date_to_sma.get(d, False) for d in rth_mnq.date], dtype=bool)

@njit(cache=True)
def sim_two_sided(o, h, l, c, atr, sig, day, sod, stop_mult, tgt_r, hold, flat, comm, slip, pv, tick):
    n = len(o)
    pnl = np.zeros(n)
    pos = 0 # -1, 0, +1
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
                cost = (1.75 + 2 * slip) * pv + 2 * comm
                pnl[i] += pos * (px - ep) / tick * pv - cost
                pos = 0
                ntr += 1
                
        # Enter at 10:00 ET close (sod 585) on next bar open (sod 600)
        if pos == 0 and sod[i] == 585 and sig[i] != 0 and i + 1 < n and day[i + 1] == day[i] and atr[i] > 0:
            pos = sig[i]
            ep = o[i + 1]
            risk = stop_mult * atr[i]
            st = ep - risk if pos > 0 else ep + risk
            tg = ep + tgt_r * risk if pos > 0 else ep - tgt_r * risk
            ei = i + 1
            eday = day[i]
            
    return pnl, ntr

print(f"\n=========================================================================")
print(f"TWO-SIDED & REGIME-FILTERED COMPOSITE (2010-2023 Training, 14 Years)")
print(f"=========================================================================")

# 1. Symmetric Two-Sided Composite (Long on net_sig > 0, Short on net_sig < 0)
pnl_sym, ntr_sym = sim_two_sided(o, h, l, c, atr, net_sig_arr, day, sod, 1.5, 3.5, 12, 955, COMM, SLIP, spec["pv"], spec["tick"])
s_sym = pd.Series(pnl_sym)
tot_sym = float(s_sym.sum())
pre_sym = float(s_sym[year < 2020].sum())
post_sym = float(s_sym[year >= 2020].sum())
yearly_sym = s_sym.groupby(year).sum()
pos_sym = int((yearly_sym > 0).sum())
cum_sym = s_sym.cumsum()
mdd_sym = float((cum_sym.cummax() - cum_sym).max())

print("\n--- 1. SYMMETRIC TWO-SIDED COMPOSITE (Long + Short) ---")
print(f"Total Net: ${tot_sym:+.2f} | Trades: {ntr_sym} ({ntr_sym/14:.1f} tr/yr) | Exp: ${tot_sym/ntr_sym:+.2f}/tr")
print(f"Pre-2020 Era (2010-2019): ${pre_sym:+.2f}")
print(f"Post-2020 Era (2020-2023): ${post_sym:+.2f}")
print(f"Positive Years: {pos_sym} of 14 ({pos_sym/14*100:.1f}%)")
print(f"Max Continuous Drawdown: ${mdd_sym:.2f} (Safety Cushion: ${2000 - mdd_sym:+.2f} under $2,000 floor)")
print("Yearly Breakdown:")
for yr, val in yearly_sym.items():
    print(f"  {yr}: ${val:+.2f}")

# 2. Long-Only Gated by 200 SMA (Close > 200 SMA = Long, otherwise Flat)
sig_long_gated = np.zeros(len(rth_mnq), dtype=np.int8)
sig_long_gated[(long_score_arr >= 1) & sma_gate_arr] = 1

pnl_gated, ntr_gated = sim_two_sided(o, h, l, c, atr, sig_long_gated, day, sod, 1.5, 3.5, 12, 955, COMM, SLIP, spec["pv"], spec["tick"])
s_gated = pd.Series(pnl_gated)
tot_gated = float(s_gated.sum())
pre_gated = float(s_gated[year < 2020].sum())
post_gated = float(s_gated[year >= 2020].sum())
yearly_gated = s_gated.groupby(year).sum()
pos_gated = int((yearly_gated > 0).sum())
cum_gated = s_gated.cumsum()
mdd_gated = float((cum_gated.cummax() - cum_gated).max())

print("\n--- 2. LONG-ONLY GATED BY 200 SMA ---")
print(f"Total Net: ${tot_gated:+.2f} | Trades: {ntr_gated} ({ntr_gated/14:.1f} tr/yr) | Exp: ${tot_gated/ntr_gated:+.2f}/tr")
print(f"Pre-2020 Era (2010-2019): ${pre_gated:+.2f}")
print(f"Post-2020 Era (2020-2023): ${post_gated:+.2f}")
print(f"Positive Years: {pos_gated} of 14 ({pos_gated/14*100:.1f}%)")
print(f"Max Continuous Drawdown: ${mdd_gated:.2f} (Safety Cushion: ${2000 - mdd_gated:+.2f} under $2,000 floor)")
print("Yearly Breakdown:")
for yr, val in yearly_gated.items():
    print(f"  {yr}: ${val:+.2f}")

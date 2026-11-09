"""Research Protocol & Simulation: Cross-Asset Relative Strength Continuation (NQ vs ES).
Pre-registered hypothesis inspired by Devin's PAIRS_1 finding:
Fading NQ/ES ratio had t-stats of -4.4 to -5.0 (strong continuation).
We test whether opening relative strength (10:00 or 10:30 ET) predicts directional follow-through.

Evaluated on Training data only (2010-2023, 14 years).
Micro costs: 0.61/side commission, 1.75 tick MNQ spread, 1.0 tick MES spread, 1 tick slippage.
"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import mass_1m_search as m1

COMM, SLIP = 0.61, 1.0
SPEC = {"MNQ": dict(tick=0.25, pv=0.5, spread=1.75), "MES": dict(tick=0.25, pv=1.25, spread=1.0)}
rng = np.random.default_rng(20261109)

def rt_cost(prod):
    s = SPEC[prod]
    return (s["spread"] + 2 * SLIP) * s["pv"] + 2 * COMM

print("Loading continuous 15m bars for MNQ and MES (2010-2023 train)...")
b_mnq = m1.load_bars("MNQ", 15, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]].copy()
b_mes = m1.load_bars("MES", 15, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]].copy()

# Add NY time features
et_mnq = b_mnq.timestamp_utc.dt.tz_convert("America/New_York")
b_mnq["sod"] = et_mnq.dt.hour * 60 + et_mnq.dt.minute
b_mnq["date"] = et_mnq.dt.date
b_mnq["year"] = et_mnq.dt.year

et_mes = b_mes.timestamp_utc.dt.tz_convert("America/New_York")
b_mes["sod"] = et_mes.dt.hour * 60 + et_mes.dt.minute
b_mes["date"] = et_mes.dt.date
b_mes["year"] = et_mes.dt.year

# Filter to RTH (09:30 - 16:00)
rth_mnq = b_mnq[(b_mnq.sod >= 570) & (b_mnq.sod < 960)].reset_index(drop=True)
rth_mes = b_mes[(b_mes.sod >= 570) & (b_mes.sod < 960)].reset_index(drop=True)

# Build daily opening return table
g_mnq = rth_mnq.groupby("date")
g_mes = rth_mes.groupby("date")

# Prices at key SOD:
# 570 = 09:30 open
# 585 = 09:45 close (1st 15m bar)
# 600 = 10:00 close (2nd 15m bar)
# 630 = 10:30 close (4th 15m bar)
# 954 = 15:54 close (session exit)
def get_px_table(g):
    o930 = g.apply(lambda d: d.loc[d.sod == 570, "open"].iloc[0] if (d.sod == 570).any() else np.nan)
    c1000 = g.apply(lambda d: d.loc[d.sod == 600, "close"].iloc[0] if (d.sod == 600).any() else np.nan)
    o1000 = g.apply(lambda d: d.loc[d.sod == 600, "close"].iloc[0] if (d.sod == 600).any() else np.nan) # enter at 10:00 close
    c1030 = g.apply(lambda d: d.loc[d.sod == 630, "close"].iloc[0] if (d.sod == 630).any() else np.nan)
    c1554 = g.apply(lambda d: d.loc[d.sod == 945, "close"].iloc[0] if (d.sod == 945).any() else np.nan)
    # High and Low from 10:00 to 15:54
    h_rest = g.apply(lambda d: d.loc[d.sod >= 600, "high"].max() if (d.sod >= 600).any() else np.nan)
    l_rest = g.apply(lambda d: d.loc[d.sod >= 600, "low"].min() if (d.sod >= 600).any() else np.nan)
    # ATR from daily ranges
    d_rng = g.apply(lambda d: d.high.max() - d.low.min())
    return pd.DataFrame({"o930": o930, "c1000": c1000, "c1030": c1030, "c1554": c1554, "h_rest": h_rest, "l_rest": l_rest, "drange": d_rng})

t_mnq = get_px_table(g_mnq)
t_mes = get_px_table(g_mes)

# Join tables
common_days = sorted(list(set(t_mnq.dropna().index).intersection(set(t_mes.dropna().index))))
df = pd.DataFrame(index=common_days)
df["year"] = pd.to_datetime(df.index).year

# 10:00 return (first 30 min)
df["ret_mnq_30m"] = (t_mnq.loc[common_days, "c1000"] / t_mnq.loc[common_days, "o930"]) - 1.0
df["ret_mes_30m"] = (t_mes.loc[common_days, "c1000"] / t_mes.loc[common_days, "o930"]) - 1.0
df["spread_30m"] = df["ret_mnq_30m"] - df["ret_mes_30m"]

# 10:30 return (first 60 min)
df["ret_mnq_60m"] = (t_mnq.loc[common_days, "c1030"] / t_mnq.loc[common_days, "o930"]) - 1.0
df["ret_mes_60m"] = (t_mes.loc[common_days, "c1030"] / t_mes.loc[common_days, "o930"]) - 1.0
df["spread_60m"] = df["ret_mnq_60m"] - df["ret_mes_60m"]

# Forward rest-of-day returns from entry to 15:54
# If enter at 10:00:
df["fwd_mnq_from_1000"] = (t_mnq.loc[common_days, "c1554"] - t_mnq.loc[common_days, "c1000"])
df["fwd_mes_from_1000"] = (t_mes.loc[common_days, "c1554"] - t_mes.loc[common_days, "c1000"])

# If enter at 10:30:
df["fwd_mnq_from_1030"] = (t_mnq.loc[common_days, "c1554"] - t_mnq.loc[common_days, "c1030"])
df["fwd_mes_from_1030"] = (t_mes.loc[common_days, "c1554"] - t_mes.loc[common_days, "c1030"])

# Point-in-time spread volatility (rolling 20-day std)
df["spread_30m_z"] = df["spread_30m"] / df["spread_30m"].rolling(20, min_periods=20).std().shift(1)
df["spread_60m_z"] = df["spread_60m"] / df["spread_60m"].rolling(20, min_periods=20).std().shift(1)

print(f"Total valid sessions 2010-2023: {len(df)}")

cost_mnq = rt_cost("MNQ")
cost_mes = rt_cost("MES")

results = []

for entry_time, sp_col, fwd_mnq, fwd_mes, entry_px_col in [
    ("10:00", "spread_30m_z", "fwd_mnq_from_1000", "fwd_mes_from_1000", "c1000"),
    ("10:30", "spread_60m_z", "fwd_mnq_from_1030", "fwd_mes_from_1030", "c1030")
]:
    for z_th in [0.5, 0.75, 1.0, 1.25, 1.5]:
        # Rule 1: Long MNQ when NQ leads ES (z >= z_th), Short MNQ when NQ lags (z <= -z_th)
        sig = np.where(df[sp_col] >= z_th, 1.0, np.where(df[sp_col] <= -z_th, -1.0, 0.0))
        valid_trades = sig != 0
        n_tr = int(valid_trades.sum())
        if n_tr < 100:
            continue
            
        pnl_pts = sig[valid_trades] * df.loc[valid_trades, fwd_mnq]
        pnl_dlr = pnl_pts / SPEC["MNQ"]["tick"] * SPEC["MNQ"]["pv"] - cost_mnq
        yearly = pnl_dlr.groupby(df.loc[valid_trades, "year"]).sum()
        tot_net = float(pnl_dlr.sum())
        pos_yrs = int(sum(yearly > 0))
        exp_tr = tot_net / n_tr
        
        # Placebo test: shuffle directions 50 times
        pl_nets = []
        gross_pts = df.loc[valid_trades, fwd_mnq].to_numpy()
        for _ in range(50):
            rand_sig = rng.choice([-1.0, 1.0], size=n_tr)
            pl_pnl = (rand_sig * gross_pts) / SPEC["MNQ"]["tick"] * SPEC["MNQ"]["pv"] - cost_mnq
            pl_nets.append(float(pl_pnl.sum()))
            
        pl_pct = float(np.mean(np.array(pl_nets) < tot_net))
        pl_mean = float(np.mean(pl_nets))
        
        results.append({
            "entry_time": entry_time,
            "target": "MNQ",
            "z_th": z_th,
            "net": tot_net,
            "trades": n_tr,
            "exp": exp_tr,
            "pos_years": pos_yrs,
            "pl_pct": pl_pct,
            "pl_mean": pl_mean,
            "yearly": yearly.to_dict()
        })
        print(f"Entry {entry_time} | Target: MNQ | z_th: {z_th:4.2f} | Net: ${tot_net:9.2f} | Tr: {n_tr:4d} | Exp: +${exp_tr:5.2f} | +Yrs: {pos_yrs:2d}/14 | PlPct: {pl_pct:4.2f} | PlMean: ${pl_mean:8.2f}")

# Also test Long-Only during NQ Outperformance (Bullish Regime)
print("\n--- Long-Only MNQ when NQ leads ES (z >= z_th) ---")
for entry_time, sp_col, fwd_mnq, entry_px_col in [
    ("10:00", "spread_30m_z", "fwd_mnq_from_1000", "c1000"),
    ("10:30", "spread_60m_z", "fwd_mnq_from_1030", "c1030")
]:
    for z_th in [0.5, 0.75, 1.0, 1.25]:
        sig = np.where(df[sp_col] >= z_th, 1.0, 0.0)
        valid_trades = sig != 0
        n_tr = int(valid_trades.sum())
        if n_tr < 50: continue
        
        pnl_pts = sig[valid_trades] * df.loc[valid_trades, fwd_mnq]
        pnl_dlr = pnl_pts / SPEC["MNQ"]["tick"] * SPEC["MNQ"]["pv"] - cost_mnq
        yearly = pnl_dlr.groupby(df.loc[valid_trades, "year"]).sum()
        tot_net = float(pnl_dlr.sum())
        pos_yrs = int(sum(yearly > 0))
        exp_tr = tot_net / n_tr
        print(f"Long-Only {entry_time} | z_th: {z_th:4.2f} | Net: ${tot_net:9.2f} | Tr: {n_tr:4d} | Exp: +${exp_tr:5.2f} | +Yrs: {pos_yrs:2d}/14")

"""Rigorous Research Protocol: Multi-Signal Directional Forecasting & Execution Engine.
Strict Mandate:
- EVALUATED STRICTLY ON TRAINING DATA (2010-2023, 14 FULL YEARS).
- ZERO TUNING / ZERO FITTING ON VALIDATION (2024-2025) OR TEST (2026).
- Account: $50,000 capital, $2,000 strict trailing drawdown floor.
- Micro costs: $0.61/side commission, 1.75 tick MNQ / 1.0 tick MES spread, 1.0 tick slippage/side.

Research Objectives:
1. Signal Opportunity Census: How often do the 3 placebo-validated signals trigger on 2010-2023?
   - Signal A: NQ/ES Opening Relative Strength (|z| >= 1.0)
   - Signal B: Toby Crabel Institutional Open-Drive (Open in 20% extreme, Close in opposite 20% extreme)
   - Signal C: VIX Term Structure Velocity Crush (|d(VIX/VIX3M)| >= 0.015)
2. Directional Predictability: What is the 10:00 to 15:55 drift and win rate for each signal?
3. Instrument Efficiency: Compare MNQ vs MES under identical directional setups.
4. Stop / Exit Microstructure:
   - Fixed R:R (1.5R stop, 3.5R target)
   - Crabel Range Stop (stop at opposite side of 09:30-10:00 range)
   - Trailing Chandelier Stop (exit when price retraces 1.5 ATR from MFE)
   - End-of-Day Drift (flat at 15:55 ET)
5. Scaling Architecture:
   - Strict 1 contract base
   - Milestone-scaled (1 contract -> 2 contracts once +$2,000 profit is banked, de-scale on drawdown)
"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'src'))

import mass_1m_search as m1

COMM, SLIP = 0.61, 1.0
SPEC_MNQ = {"tick": 0.25, "pv": 0.5, "spread": 1.75}
SPEC_MES = {"tick": 0.25, "pv": 1.25, "spread": 1.0}

def rt_cost(prod, qty=1):
    s = SPEC_MNQ if prod == "MNQ" else SPEC_MES
    return ((s["spread"] + 2 * SLIP) * s["pv"] + 2 * COMM) * qty

print("Loading continuous 15m Training bars for MNQ and MES (2010-2023)...", flush=True)
b_mnq_15 = m1.load_bars("MNQ", 15, "2010-01-01", "2024-01-01", "train").copy()
b_mes_15 = m1.load_bars("MES", 15, "2010-01-01", "2024-01-01", "train").copy()

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

for b in (b_mnq_15, b_mes_15):
    et = b.timestamp_utc.dt.tz_convert("America/New_York")
    b["sod"] = et.dt.hour * 60 + et.dt.minute
    b["date"] = et.dt.date
    b["year"] = et.dt.year

rth_mnq = b_mnq_15[(b_mnq_15.sod >= 570) & (b_mnq_15.sod <= 955)].reset_index(drop=True)
rth_mes = b_mes_15[(b_mes_15.sod >= 570) & (b_mes_15.sod <= 955)].reset_index(drop=True)

g_mnq = rth_mnq.groupby("date")
g_mes = rth_mes.groupby("date")

o930_mnq = g_mnq.apply(lambda d: d.loc[d.sod == 570, "open"].iloc[0] if (d.sod == 570).any() else np.nan)
c1000_mnq = g_mnq.apply(lambda d: d.loc[d.sod == 585, "close"].iloc[0] if (d.sod == 585).any() else np.nan)
h1000_mnq = g_mnq.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), "high"].max() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)
l1000_mnq = g_mnq.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), "low"].min() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)
c1555_mnq = g_mnq.apply(lambda d: d.loc[d.sod == 945, "close"].iloc[0] if (d.sod == 945).any() else (d["close"].iloc[-1] if len(d) else np.nan))

o930_mes = g_mes.apply(lambda d: d.loc[d.sod == 570, "open"].iloc[0] if (d.sod == 570).any() else np.nan)
c1000_mes = g_mes.apply(lambda d: d.loc[d.sod == 585, "close"].iloc[0] if (d.sod == 585).any() else np.nan)
h1000_mes = g_mes.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), "high"].max() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)
l1000_mes = g_mes.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), "low"].min() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)
c1555_mes = g_mes.apply(lambda d: d.loc[d.sod == 945, "close"].iloc[0] if (d.sod == 945).any() else (d["close"].iloc[-1] if len(d) else np.nan))

common_days = sorted(list(set(o930_mnq.dropna().index).intersection(set(o930_mes.dropna().index))))
df_days = pd.DataFrame(index=common_days)
df_days["year"] = [d.year for d in common_days]

# Relative returns
df_days["ret_mnq_open"] = (c1000_mnq.loc[common_days] / o930_mnq.loc[common_days]) - 1.0
df_days["ret_mes_open"] = (c1000_mes.loc[common_days] / o930_mes.loc[common_days]) - 1.0
df_days["spread"] = df_days["ret_mnq_open"] - df_days["ret_mes_open"]
df_days["spread_z"] = df_days["spread"] / df_days["spread"].rolling(20, min_periods=20).std().shift(1)

# Crabel metrics
df_days["range_mnq"] = h1000_mnq.loc[common_days] - l1000_mnq.loc[common_days]
df_days["open_pos_mnq"] = (o930_mnq.loc[common_days] - l1000_mnq.loc[common_days]) / df_days["range_mnq"].replace(0, np.nan)
df_days["close_pos_mnq"] = (c1000_mnq.loc[common_days] - l1000_mnq.loc[common_days]) / df_days["range_mnq"].replace(0, np.nan)

# VIX delta
df_days["vix_d1"] = [date_to_vix_d1.get(d, np.nan) for d in df_days.index]

# Rest-of-day return (10:00 to 15:55)
df_days["c1000_mnq"] = c1000_mnq.loc[common_days]
df_days["c1555_mnq"] = c1555_mnq.loc[common_days]
df_days["rod_ret_mnq"] = (df_days["c1555_mnq"] / df_days["c1000_mnq"]) - 1.0
df_days["rod_pts_mnq"] = df_days["c1555_mnq"] - df_days["c1000_mnq"]

df_days["c1000_mes"] = c1000_mes.loc[common_days]
df_days["c1555_mes"] = c1555_mes.loc[common_days]
df_days["rod_ret_mes"] = (df_days["c1555_mes"] / df_days["c1000_mes"]) - 1.0
df_days["rod_pts_mes"] = df_days["c1555_mes"] - df_days["c1000_mes"]

# Signals:
# 1. NQ/ES Divergence
df_days["sig_leader_bull"] = df_days["spread_z"] >= 1.0
df_days["sig_leader_bear"] = df_days["spread_z"] <= -1.0

# 2. Toby Crabel Open-Drive
df_days["sig_crabel_bull"] = (df_days["open_pos_mnq"] <= 0.20) & (df_days["close_pos_mnq"] >= 0.80)
df_days["sig_crabel_bear"] = (df_days["open_pos_mnq"] >= 0.80) & (df_days["close_pos_mnq"] <= 0.20)

# 3. VIX Velocity Crush
df_days["sig_vix_bull"] = (df_days["vix_d1"] <= -0.015) & (df_days["ret_mnq_open"] >= 0.001)
df_days["sig_vix_bear"] = (df_days["vix_d1"] >= +0.02) & (df_days["ret_mnq_open"] <= -0.001)

print("\n" + "=" * 80)
print("PART 1: SIGNAL OPPORTUNITY CENSUS & REST-OF-DAY DRIFT (2010-2023 TRAINING)")
print("=" * 80)

def analyze_drift(col_bull, col_bear, name):
    bull_days = df_days[df_days[col_bull]]
    bear_days = df_days[df_days[col_bear]]
    
    n_bull = len(bull_days)
    n_bear = len(bear_days)
    tot = n_bull + n_bear
    
    # MNQ drift
    mnq_bull_win = (bull_days["rod_pts_mnq"] > 0).mean() * 100 if n_bull else 0
    mnq_bear_win = (bear_days["rod_pts_mnq"] < 0).mean() * 100 if n_bear else 0
    mnq_avg_pts = (bull_days["rod_pts_mnq"].sum() - bear_days["rod_pts_mnq"].sum()) / tot if tot else 0
    
    # MES drift
    mes_bull_win = (bull_days["rod_pts_mes"] > 0).mean() * 100 if n_bull else 0
    mes_bear_win = (bear_days["rod_pts_mes"] < 0).mean() * 100 if n_bear else 0
    mes_avg_pts = (bull_days["rod_pts_mes"].sum() - bear_days["rod_pts_mes"].sum()) / tot if tot else 0
    
    # Dollar gross drift (per contract)
    mnq_dlr_per_tr = mnq_avg_pts / SPEC_MNQ["tick"] * SPEC_MNQ["pv"]
    mes_dlr_per_tr = mes_avg_pts / SPEC_MES["tick"] * SPEC_MES["pv"]
    
    print(f"\n--- {name} ---")
    print(f"Total Trigger Days: {tot} ({tot/14:.1f} days/yr) | Bull: {n_bull} | Bear: {n_bear}")
    print(f"MNQ Directional Win Rate: Bull {mnq_bull_win:.1f}% | Bear {mnq_bear_win:.1f}% | Net Drift: {mnq_avg_pts:+.2f} pts (${mnq_dlr_per_tr:+.2f}/tr gross)")
    print(f"MES Directional Win Rate: Bull {mes_bull_win:.1f}% | Bear {mes_bear_win:.1f}% | Net Drift: {mes_avg_pts:+.2f} pts (${mes_dlr_per_tr:+.2f}/tr gross)")

analyze_drift("sig_leader_bull", "sig_leader_bear", "1. NQ/ES Relative Strength Leader (|z| >= 1.0)")
analyze_drift("sig_crabel_bull", "sig_crabel_bear", "2. Toby Crabel Open-Drive")
analyze_drift("sig_vix_bull", "sig_vix_bear", "3. VIX Term Structure Velocity Crush")

# Any of the 3 signals (OR)
df_days["any_bull"] = df_days["sig_leader_bull"] | df_days["sig_crabel_bull"] | df_days["sig_vix_bull"]
df_days["any_bear"] = df_days["sig_leader_bear"] | df_days["sig_crabel_bear"] | df_days["sig_vix_bear"]
# Avoid conflict days
df_days["pure_any_bull"] = df_days["any_bull"] & (~df_days["any_bear"])
df_days["pure_any_bear"] = df_days["any_bear"] & (~df_days["any_bull"])

analyze_drift("pure_any_bull", "pure_any_bear", "4. Multi-Signal Ensemble (Any Validated Signal Fired)")

# Confluence (Score >= 2)
df_days["score_bull"] = df_days["sig_leader_bull"].astype(int) + df_days["sig_crabel_bull"].astype(int) + df_days["sig_vix_bull"].astype(int)
df_days["score_bear"] = df_days["sig_leader_bear"].astype(int) + df_days["sig_crabel_bear"].astype(int) + df_days["sig_vix_bear"].astype(int)
df_days["conf_bull"] = (df_days["score_bull"] >= 2) & (df_days["score_bear"] == 0)
df_days["conf_bear"] = (df_days["score_bear"] >= 2) & (df_days["score_bull"] == 0)

analyze_drift("conf_bull", "conf_bear", "5. High-Conviction Confluence (At Least 2 Signals Concur)")

print("\n" + "=" * 80)
print("PART 2: INTRADAY EXECUTION BACKTESTING ACROSS STRATEGIC ARCHITECTURES")
print("=" * 80)

# Precalculate 15m ATR
rth_mnq["day"] = pd.factorize(rth_mnq.date)[0]
tr_mnq = np.maximum(rth_mnq.high - rth_mnq.low, np.maximum((rth_mnq.high - rth_mnq.close.shift(1)).abs(), (rth_mnq.low - rth_mnq.close.shift(1)).abs()))
atr_mnq = tr_mnq.rolling(14, min_periods=14).mean().bfill().to_numpy(float)
rth_mnq["atr"] = atr_mnq

mnq_data = {
    "open": rth_mnq.open.to_numpy(float), "high": rth_mnq.high.to_numpy(float),
    "low": rth_mnq.low.to_numpy(float), "close": rth_mnq.close.to_numpy(float),
    "sod": rth_mnq.sod.to_numpy(np.int64), "date": rth_mnq.date.to_numpy(),
    "year": rth_mnq.year.to_numpy(np.int64), "ts": rth_mnq.timestamp_utc.to_numpy(),
    "atr": atr_mnq
}

# Add range extremes to df_days
df_days["h1000_mnq"] = h1000_mnq.loc[common_days]
df_days["l1000_mnq"] = l1000_mnq.loc[common_days]

def run_simulation(name, signal_mode="confluence", exit_mode="fixed_rr", stop_mult=1.5, target_mult=3.5,
                   scaling_mode="fixed_1", trail_atr=0.0):
    """
    Simulates intraday execution on Training (2010-2023).
    signal_mode: 'leader_only', 'crabel_only', 'vix_only', 'ensemble_any', 'confluence'
    exit_mode: 'fixed_rr', 'crabel_range', 'eod_hold', 'chandelier_trail'
    scaling_mode: 'fixed_1', 'milestone_funded' (scale to 2ct once +$2,000 profit is banked)
    """
    executed = []
    cum_pnl = 0.0
    hwm = 0.0
    
    for dt in common_days:
        row = df_days.loc[dt]
        side = 0
        
        if signal_mode == "leader_only":
            if row["sig_leader_bull"]: side = 1
            elif row["sig_leader_bear"]: side = -1
        elif signal_mode == "crabel_only":
            if row["sig_crabel_bull"]: side = 1
            elif row["sig_crabel_bear"]: side = -1
        elif signal_mode == "vix_only":
            if row["sig_vix_bull"]: side = 1
            elif row["sig_vix_bear"]: side = -1
        elif signal_mode == "ensemble_any":
            if row["pure_any_bull"]: side = 1
            elif row["pure_any_bear"]: side = -1
        elif signal_mode == "confluence":
            if row["conf_bull"]: side = 1
            elif row["conf_bear"]: side = -1
            
        if side == 0: continue
        
        # Sizing
        qty = 1
        if scaling_mode == "milestone_funded":
            # Scale to 2 contracts strictly after +$2,000 net profit is secured
            # Drop back to 1 if we re-enter drawdown under $1,500 cushion
            if cum_pnl >= 2000.0:
                qty = 2
            else:
                qty = 1
                
        # Find 10:00 entry bar
        day_mask = (mnq_data["date"] == dt)
        day_indices = np.where(day_mask)[0]
        if len(day_indices) == 0: continue
        
        sod_sub = mnq_data["sod"][day_indices]
        idx_585_arr = np.where(sod_sub == 585)[0]
        if len(idx_585_arr) == 0: continue
        
        idx_585 = day_indices[idx_585_arr[0]]
        if idx_585 + 1 >= len(mnq_data["open"]): continue
        if mnq_data["date"][idx_585 + 1] != dt: continue
        
        entry_idx = idx_585 + 1
        ep = mnq_data["open"][entry_idx]
        atr_val = mnq_data["atr"][idx_585]
        if atr_val <= 0: continue
        
        # Define stop and target
        if exit_mode == "crabel_range":
            # Stop is opposite side of 09:30-10:00 opening range
            range_h = row["h1000_mnq"]
            range_l = row["l1000_mnq"]
            st = range_l if side > 0 else range_h
            risk = abs(ep - st)
            tg = ep + target_mult * risk if side > 0 else ep - target_mult * risk
        elif exit_mode == "eod_hold":
            st = ep - 3.0 * atr_val if side > 0 else ep + 3.0 * atr_val
            tg = ep + 10.0 * atr_val if side > 0 else ep - 10.0 * atr_val # virtually no early target
        else: # fixed_rr or chandelier_trail
            risk = stop_mult * atr_val
            st = ep - risk if side > 0 else ep + risk
            tg = ep + target_mult * risk if side > 0 else ep - target_mult * risk
            
        exit_px = 0.0
        exit_ts = None
        bars_held = 0
        best_favorable = ep
        
        for k in range(entry_idx, len(mnq_data["open"])):
            if mnq_data["date"][k] != dt:
                exit_ts = mnq_data["ts"][k]; exit_px = mnq_data["open"][k]; break
            bars_held += 1
            
            # Chandelier trailing logic
            if exit_mode == "chandelier_trail" and trail_atr > 0:
                if side > 0:
                    best_favorable = max(best_favorable, mnq_data["high"][k])
                    trail_st = best_favorable - trail_atr * atr_val
                    st = max(st, trail_st)
                else:
                    best_favorable = min(best_favorable, mnq_data["low"][k])
                    trail_st = best_favorable + trail_atr * atr_val
                    st = min(st, trail_st)
                    
            if side > 0:
                if mnq_data["low"][k] <= st: exit_ts = mnq_data["ts"][k]; exit_px = st; break
                elif mnq_data["high"][k] >= tg: exit_ts = mnq_data["ts"][k]; exit_px = tg; break
            else:
                if mnq_data["high"][k] >= st: exit_ts = mnq_data["ts"][k]; exit_px = st; break
                elif mnq_data["low"][k] <= tg: exit_ts = mnq_data["ts"][k]; exit_px = tg; break
                
            if mnq_data["sod"][k] >= 955:
                exit_ts = mnq_data["ts"][k]; exit_px = mnq_data["close"][k]; break
                
        if exit_ts is None: continue
        
        gross_pts = side * (exit_px - ep)
        gross_dlr = gross_pts / SPEC_MNQ["tick"] * SPEC_MNQ["pv"] * qty
        fee = rt_cost("MNQ", qty)
        net_dlr = gross_dlr - fee
        cum_pnl += net_dlr
        
        executed.append({
            "date": dt, "year": pd.to_datetime(dt).year, "side": side,
            "qty": qty, "net_dlr": net_dlr, "cum_pnl": cum_pnl
        })
        
    df_res = pd.DataFrame(executed)
    if len(df_res) == 0:
        print(f"{name}: ZERO TRADES")
        return None
        
    tot = df_res.net_dlr.sum()
    pre = df_res[df_res.year < 2020].net_dlr.sum()
    post = df_res[df_res.year >= 2020].net_dlr.sum()
    yearly = df_res.groupby("year")["net_dlr"].sum()
    pos_y = (yearly > 0).sum()
    
    cum = df_res.net_dlr.cumsum()
    mdd = (cum.cummax() - cum).max()
    exp_tr = tot / len(df_res)
    win_rate = (df_res.net_dlr > 0).mean() * 100
    
    print(f"\n=======================================================", flush=True)
    print(f"{name}", flush=True)
    print(f"=======================================================", flush=True)
    print(f"Total Net: ${tot:+.2f} | Trades: {len(df_res)} ({len(df_res)/14:.1f} tr/yr) | Win Rate: {win_rate:.1f}% | Exp: ${exp_tr:+.2f}/tr", flush=True)
    print(f"Pre-2020 Era (2010-2019): ${pre:+.2f} ({(yearly.loc[yearly.index < 2020] > 0).sum()}/10 pos years)", flush=True)
    print(f"Post-2020 Era (2020-2023): ${post:+.2f} ({(yearly.loc[yearly.index >= 2020] > 0).sum()}/4 pos years)", flush=True)
    print(f"Positive Years: {pos_y} of 14 ({pos_y/14*100:.1f}%)", flush=True)
    print(f"Max Continuous Drawdown: ${mdd:.2f} (Safety Cushion: ${2000 - mdd:+.2f} under $2,000 floor)", flush=True)
    
    return df_res

# Run Comparative Architectures
# Architecture 1: Individual Placebo-Validated Signals
run_simulation("Arch 1A: NQ/ES Relative Strength Alone (1 Contract)", signal_mode="leader_only", exit_mode="fixed_rr")
run_simulation("Arch 1B: Toby Crabel Open-Drive Alone (1 Contract)", signal_mode="crabel_only", exit_mode="fixed_rr")
run_simulation("Arch 1C: VIX Velocity Crush Alone (1 Contract)", signal_mode="vix_only", exit_mode="fixed_rr")

# Architecture 2: Multi-Signal Ensemble vs Confluence
run_simulation("Arch 2A: Multi-Signal Ensemble (Any Validated Signal, 1 Contract)", signal_mode="ensemble_any", exit_mode="fixed_rr")
run_simulation("Arch 2B: Confluence (At Least 2 Signals Concur, 1 Contract)", signal_mode="confluence", exit_mode="fixed_rr")

# Architecture 3: Exit Microstructure Studies on Confluence
run_simulation("Arch 3A: Confluence with Crabel Opening-Range Stop", signal_mode="confluence", exit_mode="crabel_range", target_mult=3.0)
run_simulation("Arch 3B: Confluence with End-of-Day Hold (15:55 Flat)", signal_mode="confluence", exit_mode="eod_hold")
run_simulation("Arch 3C: Confluence with Chandelier Trailing Stop (1.5 ATR trail)", signal_mode="confluence", exit_mode="chandelier_trail", trail_atr=1.5)

# Architecture 4: Milestone Sizing (Funded Account Optimization)
run_simulation("Arch 4A: Confluence + Milestone Sizing (Scale to 2ct after +$2k profit)", signal_mode="confluence", exit_mode="fixed_rr", scaling_mode="milestone_funded")
run_simulation("Arch 4B: Multi-Signal Ensemble + Milestone Sizing", signal_mode="ensemble_any", exit_mode="fixed_rr", scaling_mode="milestone_funded")

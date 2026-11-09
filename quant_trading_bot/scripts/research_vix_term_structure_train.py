"""Research Hypothesis: VIX Term Structure Contango/Backwardation Velocity Shocks.
Mechanism:
VIX / VIX3M term structure reflects institutional option hedging demand.
Point-in-time: Uses PRIOR DAY CLOSE of VIX and VIX3M (available at 09:30 ET open, zero lookahead).
- Contango: VIX / VIX3M < 0.90 (equities calm, structural equity accumulation)
- Backwardation / Inversion: VIX / VIX3M >= 1.00 (systematic hedging, forced deleveraging)
- Rapid Inversion Shock: 1-day delta in (VIX/VIX3M) >= +0.05 or +0.08
- Rapid Crush: 1-day delta in (VIX/VIX3M) <= -0.05

EVALUATED STRICTLY ON TRAINING DATA (2010-2023, 14 FULL YEARS).
DO NOT TOUCH VALIDATION (2024-2025) OR TEST (2026).
Micro costs: 0.61/side commission, 1.75 tick MNQ / 1.0 tick MES spread, 1.0 tick slippage.
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import mass_1m_search as m1

COMM, SLIP = 0.61, 1.0
SPEC = {"MNQ": dict(tick=0.25, pv=0.5, spread=1.75), "MES": dict(tick=0.25, pv=1.25, spread=1.0)}

def rt_cost(prod):
    s = SPEC[prod]
    return (s["spread"] + 2 * SLIP) * s["pv"] + 2 * COMM

print("Loading continuous 15m Training bars for MNQ (2010-2023)...")
b_mnq = m1.load_bars("MNQ", 15, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]].copy()

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
vix_df["ratio_d3"] = vix_df["ratio"].diff(3)
vix_df["vix_d1"] = vix_df["vix"].diff(1)

# Point-in-time shift: signal available for trading on day t must be from close of day t-1!
vix_df["prior_date"] = vix_df["date"]
vix_df["trade_date"] = vix_df["date"].shift(-1) # line up prior close to next trading day

date_to_ratio = dict(zip(vix_df["trade_date"], vix_df["ratio"]))
date_to_d1 = dict(zip(vix_df["trade_date"], vix_df["ratio_d1"]))
date_to_d3 = dict(zip(vix_df["trade_date"], vix_df["ratio_d3"]))
date_to_vix = dict(zip(vix_df["trade_date"], vix_df["vix"]))

et = b_mnq.timestamp_utc.dt.tz_convert("America/New_York")
b_mnq["sod"] = et.dt.hour * 60 + et.dt.minute
b_mnq["date"] = et.dt.date
b_mnq["year"] = et.dt.year

rth = b_mnq[(b_mnq.sod >= 570) & (b_mnq.sod <= 955)].reset_index(drop=True)
cost = rt_cost("MNQ")
spec = SPEC["MNQ"]

# Daily RTH performance: 10:00 open to 15:55 close
g = rth.groupby("date")
day_records = []
for d, grp in g:
    row_1000 = grp[grp.sod == 600]
    row_exit = grp[grp.sod == 945]
    if len(row_1000) == 0 or len(row_exit) == 0:
        continue
    ep = row_1000.iloc[0]["open"]
    xp = row_exit.iloc[0]["close"]
    
    mid = grp[(grp.sod >= 600) & (grp.sod <= 945)]
    h_max = mid.high.max()
    l_min = mid.low.min()
    
    # 09:30 to 10:00 morning momentum
    morn = grp[grp.sod.isin([570, 585])]
    morn_ret = (row_1000.iloc[0]["open"] - morn.iloc[0]["open"]) / morn.iloc[0]["open"] if len(morn) > 0 else 0.0
    
    # Range of morning
    morn_range = (morn.high.max() - morn.low.min()) if len(morn) > 0 else 0.0
    
    pts_long = xp - ep
    dlr_long = pts_long / spec["tick"] * spec["pv"] - cost
    
    pts_short = ep - xp
    dlr_short = pts_short / spec["tick"] * spec["pv"] - cost
    
    dt = pd.to_datetime(d)
    day_records.append({
        "date": d,
        "year": dt.year,
        "ratio": date_to_ratio.get(d, np.nan),
        "ratio_d1": date_to_d1.get(d, np.nan),
        "ratio_d3": date_to_d3.get(d, np.nan),
        "vix": date_to_vix.get(d, np.nan),
        "morn_ret": morn_ret,
        "dlr_long": dlr_long,
        "dlr_short": dlr_short,
        "ep": ep,
        "xp": xp,
        "h_max": h_max,
        "l_min": l_min
    })

df_days = pd.DataFrame(day_records).dropna(subset=["ratio"]).reset_index(drop=True)

print(f"\n=======================================================")
print(f"VIX Term Structure Regime Analysis (2010-2023 Train, {len(df_days)} Days)")
print(f"=======================================================")

# 1. Contango vs Backwardation split
df_days["regime"] = pd.cut(df_days["ratio"], bins=[0, 0.85, 0.95, 1.05, 5.0], labels=["Deep Contango (<0.85)", "Mild Contango (0.85-0.95)", "Mild Inversion (0.95-1.05)", "Deep Inversion (>1.05)"])
print("\n--- Long Drift by VIX Term Structure Regime ---")
reg_summary = df_days.groupby("regime", observed=False).agg(
    days=("dlr_long", "count"),
    tot_long=("dlr_long", "sum"),
    exp_long=("dlr_long", "mean"),
    win_rate_long=("dlr_long", lambda x: (x > 0).mean()),
    tot_short=("dlr_short", "sum"),
    exp_short=("dlr_short", "mean")
)
print(reg_summary)

# 2. Velocity Shocks
print("\n--- 1-Day VIX Term Structure Inversion Shocks (Delta >= +0.03) ---")
shock_up = df_days[df_days.ratio_d1 >= 0.03]
print(f"Count: {len(shock_up)} days")
print(f"Short Net: ${shock_up.dlr_short.sum():.2f} (Exp: ${shock_up.dlr_short.mean():.2f}/day, Win: {(shock_up.dlr_short > 0).mean()*100:.1f}%)")
print(f"Long Net: ${shock_up.dlr_long.sum():.2f} (Exp: ${shock_up.dlr_long.mean():.2f}/day, Win: {(shock_up.dlr_long > 0).mean()*100:.1f}%)")

print("\n--- 1-Day VIX Term Structure Crush Shocks (Delta <= -0.03) ---")
shock_dn = df_days[df_days.ratio_d1 <= -0.03]
print(f"Count: {len(shock_dn)} days")
print(f"Long Net: ${shock_dn.dlr_long.sum():.2f} (Exp: ${shock_dn.dlr_long.mean():.2f}/day, Win: {(shock_dn.dlr_long > 0).mean()*100:.1f}%)")
print(f"Short Net: ${shock_dn.dlr_short.sum():.2f} (Exp: ${shock_dn.dlr_short.mean():.2f}/day, Win: {(shock_dn.dlr_short > 0).mean()*100:.1f}%)")

# 3. Macro Shock + Morning Alignment Interaction
# If ratio_d1 >= 0.03 AND morning return is negative -> Short at 10:00
print("\n--- Macro Inversion Shock + Morning Downside Alignment ---")
align_short = df_days[(df_days.ratio_d1 >= 0.02) & (df_days.morn_ret < -0.002)]
tot_s = align_short.dlr_short.sum()
pre_s = align_short[align_short.year < 2020].dlr_short.sum()
post_s = align_short[align_short.year >= 2020].dlr_short.sum()
yearly_s = align_short.groupby("year")["dlr_short"].sum()
print(f"Count: {len(align_short)} days")
print(f"Total Short Net: ${tot_s:.2f} | Exp: ${tot_s/len(align_short) if len(align_short) else 0:.2f}/tr | Pre-2020: ${pre_s:.2f} | Post-2020: ${post_s:.2f} | Pos Yrs: {(yearly_s > 0).sum()}/14")

# If ratio_d1 <= -0.02 AND morning return is positive -> Long at 10:00
print("\n--- Macro Crush Shock + Morning Upside Alignment ---")
align_long = df_days[(df_days.ratio_d1 <= -0.02) & (df_days.morn_ret > 0.002)]
tot_l = align_long.dlr_long.sum()
pre_l = align_long[align_long.year < 2020].dlr_long.sum()
post_l = align_long[align_long.year >= 2020].dlr_long.sum()
yearly_l = align_long.groupby("year")["dlr_long"].sum()
print(f"Count: {len(align_long)} days")
print(f"Total Long Net: ${tot_l:.2f} | Exp: ${tot_l/len(align_long) if len(align_long) else 0:.2f}/tr | Pre-2020: ${pre_l:.2f} | Post-2020: ${post_l:.2f} | Pos Yrs: {(yearly_l > 0).sum()}/14")

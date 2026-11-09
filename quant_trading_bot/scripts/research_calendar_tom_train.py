"""Research Hypothesis: Institutional Calendar Turn-of-Month (TOM) & OpEx Intraday Drift.
Mechanism:
Passive 401(k) contributions, sovereign funds, and pension rebalancing generate structural
net buying pressure into US equities around month-end (trading days -2, -1, +1, +2, +3 of month).
LucidFlex / funded evaluation rule: Flat by 15:55 ET (strictly intraday, no overnight hold).

EVALUATED STRICTLY ON TRAINING DATA (2010-2023, 14 FULL YEARS).
DO NOT TOUCH VALIDATION (2024-2025) OR TEST (2026).
Micro costs: 0.61/side commission, 1.75 tick MNQ spread / 1.0 tick MES spread, 1.0 tick slippage.
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

print("Loading continuous 15m Training bars for MNQ and MES (2010-2023)...")
b_mnq = m1.load_bars("MNQ", 15, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]].copy()
b_mes = m1.load_bars("MES", 15, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]].copy()

def test_calendar_drift(prod, b):
    et = b.timestamp_utc.dt.tz_convert("America/New_York")
    b["sod"] = et.dt.hour * 60 + et.dt.minute
    b["date"] = et.dt.date
    b["year"] = et.dt.year
    
    rth = b[(b.sod >= 570) & (b.sod <= 955)].reset_index(drop=True)
    cost = rt_cost(prod)
    spec = SPEC[prod]
    
    # Identify unique trading days and calendar properties
    unique_dates = pd.to_datetime(sorted(rth.date.unique()))
    df_dates = pd.DataFrame({"date": unique_dates})
    df_dates["month"] = df_dates.date.dt.month
    df_dates["year"] = df_dates.date.dt.year
    
    # Calculate trading day of month (+1, +2, +3... from start; -1, -2, -3... from end)
    df_dates["day_from_start"] = df_dates.groupby(["year", "month"]).cumcount() + 1
    df_dates["days_in_month"] = df_dates.groupby(["year", "month"])["date"].transform("count")
    df_dates["day_from_end"] = df_dates["day_from_start"] - df_dates["days_in_month"] - 1 # e.g. -1 is last day of month
    
    date_to_start = dict(zip(df_dates.date.dt.date, df_dates.day_from_start))
    date_to_end = dict(zip(df_dates.date.dt.date, df_dates.day_from_end))
    
    # Measure RTH return for each day: enter at 09:45 (sod 585 open) or 10:00 (sod 600 open), exit at 15:55 (sod 945/950/955 close)
    g = rth.groupby("date")
    
    # Day-level returns:
    day_stats = []
    for d, grp in g:
        # 10:00 entry (open of 600)
        row_1000 = grp[grp.sod == 600]
        row_exit = grp[grp.sod == 945]
        if len(row_1000) == 0 or len(row_exit) == 0:
            continue
        ep = row_1000.iloc[0]["open"]
        xp = row_exit.iloc[0]["close"]
        
        # High and Low between 10:00 and 15:55
        mid = grp[(grp.sod >= 600) & (grp.sod <= 945)]
        max_h = mid.high.max()
        min_l = mid.low.min()
        
        gross_pts = xp - ep
        gross_dlr = gross_pts / spec["tick"] * spec["pv"]
        net_dlr = gross_dlr - cost
        
        dt = pd.to_datetime(d)
        day_stats.append({
            "date": d,
            "year": dt.year,
            "day_from_start": date_to_start.get(d, 0),
            "day_from_end": date_to_end.get(d, 0),
            "net_dlr": net_dlr,
            "gross_dlr": gross_dlr,
            "mfe_dlr": (max_h - ep) / spec["tick"] * spec["pv"],
            "mae_dlr": (ep - min_l) / spec["tick"] * spec["pv"]
        })
        
    df_sim = pd.DataFrame(day_stats)
    
    print(f"\n=======================================================")
    print(f"Calendar Turn-of-Month Analysis for {prod} (2010-2023 Train)")
    print(f"=======================================================")
    
    # Analyze by day_from_end (-5 to -1) and day_from_start (1 to 5)
    print("\n--- Day from End of Month (Last 5 days) ---")
    end_summary = df_sim[df_sim.day_from_end.isin([-5, -4, -3, -2, -1])].groupby("day_from_end").agg(
        trades=("net_dlr", "count"),
        tot_net=("net_dlr", "sum"),
        exp_tr=("net_dlr", "mean"),
        win_rate=("net_dlr", lambda x: (x > 0).mean())
    )
    print(end_summary)
    
    print("\n--- Day from Start of Month (First 5 days) ---")
    start_summary = df_sim[df_sim.day_from_start.isin([1, 2, 3, 4, 5])].groupby("day_from_start").agg(
        trades=("net_dlr", "count"),
        tot_net=("net_dlr", "sum"),
        exp_tr=("net_dlr", "mean"),
        win_rate=("net_dlr", lambda x: (x > 0).mean())
    )
    print(start_summary)
    
    # Combined TOM window: Days -1, +1, +2, +3
    tom_mask = df_sim.day_from_end.isin([-1]) | df_sim.day_from_start.isin([1, 2, 3])
    df_tom = df_sim[tom_mask].copy()
    
    tot_tom_net = df_tom.net_dlr.sum()
    pre_2020 = df_tom[df_tom.year < 2020].net_dlr.sum()
    post_2020 = df_tom[df_tom.year >= 2020].net_dlr.sum()
    yearly = df_tom.groupby("year")["net_dlr"].sum()
    pos_yrs = (yearly > 0).sum()
    
    cum = df_tom.net_dlr.cumsum()
    mdd = (cum.cummax() - cum).max()
    
    print(f"\n>>> Combined Turn-of-Month (Days -1, +1, +2, +3) on {prod}:")
    print(f"Total Net: ${tot_tom_net:.2f} | Trades: {len(df_tom)} | Exp/tr: +${df_tom.net_dlr.mean():.2f}")
    print(f"Pre-2020 Net: ${pre_2020:.2f} (Exp: +${df_tom[df_tom.year < 2020].net_dlr.mean():.2f}/tr)")
    print(f"Post-2020 Net: ${post_2020:.2f} (Exp: +${df_tom[df_tom.year >= 2020].net_dlr.mean():.2f}/tr)")
    print(f"Positive Years: {pos_yrs}/14")
    print(f"Max Continuous Drawdown: ${mdd:.2f}")
    print("Yearly P&L Breakdown:")
    for yr, val in yearly.items():
        print(f"  {yr}: ${val:+.2f}")

test_calendar_drift("MNQ", b_mnq)
test_calendar_drift("MES", b_mes)

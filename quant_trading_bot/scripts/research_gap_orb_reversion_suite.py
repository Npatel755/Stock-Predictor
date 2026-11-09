"""Comprehensive Training-Only Search: Gap Continuation/Fade, Opening Range Breakout (ORB), and VWAP Reversion.
Strictly evaluated on 2010-2023 Training (14 years).
Zero access to Validation (2024-2025) or Test (2026).
Micro costs: 0.61/side, 1.75 tick MNQ / 1.0 tick MES, 1.0 tick slippage.
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

for b in (b_mnq, b_mes):
    et = b.timestamp_utc.dt.tz_convert("America/New_York")
    b["sod"] = et.dt.hour * 60 + et.dt.minute
    b["date"] = et.dt.date
    b["year"] = et.dt.year

# =========================================================================
# 1. OVERNIGHT GAP ANALYSIS (09:30 open vs prior 16:00 close)
# =========================================================================
def test_gap_suite(prod, b):
    print(f"\n=======================================================")
    print(f"1. OVERNIGHT GAP FADE / CONTINUATION ON {prod} (2010-2023)")
    print(f"=======================================================")
    rth = b[(b.sod >= 570) & (b.sod <= 955)].reset_index(drop=True)
    g = rth.groupby("date")
    
    dates = sorted(list(g.groups.keys()))
    cost = rt_cost(prod)
    spec = SPEC[prod]
    
    gap_records = []
    for i in range(1, len(dates)):
        prev_d = dates[i-1]
        curr_d = dates[i]
        
        grp_prev = g.get_group(prev_d)
        grp_curr = g.get_group(curr_d)
        
        # Prior close at 16:00 (sod 945 or 955 close)
        prior_close = grp_prev.iloc[-1]["close"]
        
        # Today's 09:30 open
        row_0930 = grp_curr[grp_curr.sod == 570]
        row_exit = grp_curr[grp_curr.sod == 945]
        if len(row_0930) == 0 or len(row_exit) == 0:
            continue
            
        today_open = row_0930.iloc[0]["open"]
        exit_close = row_exit.iloc[0]["close"]
        
        gap_pts = today_open - prior_close
        gap_pct = gap_pts / prior_close
        
        # Intraday drift: today_open to exit_close
        intraday_pts = exit_close - today_open
        
        # Max high and low of the day
        day_h = grp_curr.high.max()
        day_l = grp_curr.low.min()
        
        # Gap filled check:
        # If gap up (gap_pts > 0), filled if day_l <= prior_close
        # If gap down (gap_pts < 0), filled if day_h >= prior_close
        gap_filled = False
        if gap_pts > 0 and day_l <= prior_close:
            gap_filled = True
        elif gap_pts < 0 and day_h >= prior_close:
            gap_filled = True
            
        dt = pd.to_datetime(curr_d)
        gap_records.append({
            "date": curr_d,
            "year": dt.year,
            "gap_pts": gap_pts,
            "gap_pct": gap_pct,
            "gap_filled": gap_filled,
            "intraday_pts": intraday_pts,
            "today_open": today_open,
            "prior_close": prior_close,
            "exit_close": exit_close
        })
        
    df_gap = pd.DataFrame(gap_records)
    print(f"Total days analyzed: {len(df_gap)}")
    print(f"Overall Gap Fill Rate: {df_gap.gap_filled.mean()*100:.1f}%")
    
    # Gap Fade Test:
    # If gap up (gap_pct >= 0.3%): Short at open, exit at gap fill or 15:55 close
    # If gap down (gap_pct <= -0.3%): Long at open, exit at gap fill or 15:55 close
    for gap_th in [0.002, 0.003, 0.005]:
        fade_records = []
        for _, row in df_gap.iterrows():
            if row["gap_pct"] >= gap_th:
                # Gap Up -> Short Fade
                # Exit at prior close if filled, else exit at exit_close
                fill_px = row["prior_close"] if row["gap_filled"] else row["exit_close"]
                pts = row["today_open"] - fill_px
                dlr = pts / spec["tick"] * spec["pv"] - cost
                fade_records.append({"year": row["year"], "dlr": dlr, "side": "short", "filled": row["gap_filled"]})
            elif row["gap_pct"] <= -gap_th:
                # Gap Down -> Long Fade
                fill_px = row["prior_close"] if row["gap_filled"] else row["exit_close"]
                pts = fill_px - row["today_open"]
                dlr = pts / spec["tick"] * spec["pv"] - cost
                fade_records.append({"year": row["year"], "dlr": dlr, "side": "long", "filled": row["gap_filled"]})
                
        df_f = pd.DataFrame(fade_records)
        if len(df_f) > 0:
            tot = df_f.dlr.sum()
            pre = df_f[df_f.year < 2020].dlr.sum()
            post = df_f[df_f.year >= 2020].dlr.sum()
            yearly = df_f.groupby("year")["dlr"].sum()
            pos_y = (yearly > 0).sum()
            cum = df_f.dlr.cumsum()
            mdd = (cum.cummax() - cum).max()
            print(f"Gap Fade (|gap| >= {gap_th*100:.1f}%): Net: ${tot:.2f} | Tr: {len(df_f)} | Exp: ${tot/len(df_f):.2f}/tr | Pre-2020: ${pre:.2f} | Post-2020: ${post:.2f} | +Yrs: {pos_y}/14 | MaxDD: ${mdd:.2f}")

test_gap_suite("MNQ", b_mnq)
test_gap_suite("MES", b_mes)

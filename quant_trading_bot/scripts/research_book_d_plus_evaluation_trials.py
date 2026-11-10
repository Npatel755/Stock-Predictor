"""Research Book D+ Evaluation Pass Rate & Horizon Optimization.
Evaluates the combination of VIX-gated Overnight Reopen Dip + Intraday Architecture D+
(Crabel 15m Continuation + 30m Trend + 60m Trend + MES 30m Trend)
across all 14 years (2010-2023 Training Split).
"""
import sys, json, os
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

# Load Book D+ replication engine
src = (ROOT / "scripts/replicate_antigravity_d_plus.py").read_text()
ns = {"__file__": str(ROOT / "scripts/replicate_antigravity_d_plus.py")}
exec(src, ns)

dplus = ns["dplus"]
p_on = ns["p_on"]
skip_night = ns["skip_night"]
mn = ns["mn"]
next_day_fn = ns["ns"]["next_day"]
low_open_dict = ns["ns"]["low_open"]

# Also load gap for Crabel continuation filter
b = ns["bars_for"](dict(instrument="MNQ", bar_minutes=15))[0]
loc = b.timestamp_utc.dt.tz_convert("America/New_York")
m = loc.dt.hour * 60 + loc.dt.minute
day_col = loc.dt.date
rth = b[(m >= 570) & (m <= 960)]
first_open = rth.groupby(day_col[rth.index]).open.first()
last_close = rth.groupby(day_col[rth.index]).close.last()
gap = (first_open - last_close.shift(1)).dropna()
gap_dict = dict(zip(pd.to_datetime(pd.Series(gap.index)).dt.date.to_numpy(), gap.to_numpy()))

# Compile all daily events
# On each trade day, what trades happen?
daily_events = {}

# 1. Overnight trades
for (nk, p), sk in zip(p_on.items(), skip_night):
    if sk:
        continue
    ex_day = next_day_fn(nk)
    e = float(mn.at[nk, "e1805"])
    lo = min(float(mn.at[nk, "low_night"]), float(low_open_dict.get(ex_day, np.inf)))
    # Net PnL is p at 1 contract ($2/pt minus friction)
    # MAE is (lo - e) * 2.0 - 3.0
    mae = (lo - e) * 2.0 - 3.0
    pnl = float(p)
    daily_events.setdefault(ex_day, []).append({
        "type": "overnight",
        "pnl_1c": pnl,
        "mae_1c": mae,
        "entry_time": "18:05",
        "sleeve": "OVERNIGHT_DIP"
    })

# 2. Intraday trades
for t in dplus:
    t_day = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
    pnl = float(t["net"])
    # Stop risk is worst-case intraday excursion
    mae = -float(t.get("stop_risk", 25.0))
    sleeve = t["sleeve"]
    is_crabel = "CRABEL" in sleeve
    side_val = t.get("side", t.get("direction", 1))
    if isinstance(side_val, (int, float, np.integer, np.floating)):
        is_long = side_val > 0
    else:
        is_long = str(side_val).lower() in ("long", "buy", "1")
    t_gap = gap_dict.get(t_day, 0.0)
    cont = bool((is_long and t_gap >= 0) or (not is_long and t_gap <= 0))

    daily_events.setdefault(t_day, []).append({
        "type": "intraday",
        "pnl_1c": pnl,
        "mae_1c": mae,
        "entry_time": str(t["entry_ts"]),
        "sleeve": sleeve,
        "is_crabel": is_crabel,
        "cont": cont
    })

all_calendar_days = sorted(list(daily_events.keys()))
print(f"Total active trading days with Book D+ opportunities: {len(all_calendar_days)}")

def simulate_evaluations(
    intra_size_stg1=4,
    on_size_stg1=2,
    intra_size_stg2=8,
    on_size_stg2=4,
    stage2_cushion=1200.0,
    filter_crabel_fades=True,
    max_days=90,
    daily_lock=1750.0,
    dll=1000.0,
    trailing_floor=2000.0,
    target=4000.0
):
    total_starts = len(all_calendar_days) - max_days
    passed = 0
    ruined = 0
    pass_days = []
    ruin_reasons = {"dll": 0, "floor": 0}
    max_drawdowns_on_pass = []

    for i in range(total_starts):
        cum = 0.0
        hwm = 0.0
        floor = -trailing_floor
        busted = False
        passed_eval = False
        max_d_pnl = -9999.0
        peak_dd_on_pass = 0.0

        for step in range(max_days):
            d = all_calendar_days[i + step]
            events = daily_events.get(d, [])
            if not events:
                continue

            # Determine staging
            if cum >= stage2_cushion:
                i_size = intra_size_stg2
                o_size = on_size_stg2
            else:
                i_size = intra_size_stg1
                o_size = on_size_stg1

            day_pnl = 0.0
            day_mae = 0.0

            for ev in events:
                if filter_crabel_fades and ev.get("is_crabel") and not ev.get("cont"):
                    continue

                sz = o_size if ev["type"] == "overnight" else i_size
                pnl = ev["pnl_1c"] * sz
                mae = ev["mae_1c"] * sz

                if (day_pnl + mae) < day_mae:
                    day_mae = day_pnl + mae

                day_pnl += pnl

                # Circuit breaker intraday
                if day_pnl >= daily_lock or day_pnl <= -400.0:
                    break

            # Check DLL
            if day_pnl <= -dll or day_mae <= -dll:
                busted = True
                ruin_reasons["dll"] += 1
                break

            # Check Trailing Floor during the day
            if (cum + day_mae) <= floor:
                busted = True
                ruin_reasons["floor"] += 1
                break

            # End of day update
            cum += day_pnl
            current_dd = hwm - cum
            if current_dd > peak_dd_on_pass:
                peak_dd_on_pass = current_dd

            if cum > hwm:
                hwm = cum
                # Lock floor at 0 once HWM >= +2000
                if hwm >= trailing_floor:
                    floor = 0.0
                else:
                    floor = -trailing_floor + hwm

            if cum <= floor:
                busted = True
                ruin_reasons["floor"] += 1
                break

            if day_pnl > max_d_pnl:
                max_d_pnl = day_pnl

            # Target reached with 50% consistency compliance
            if cum >= target and max_d_pnl <= (target * 0.5):
                passed_eval = True
                passed += 1
                pass_days.append(step + 1)
                max_drawdowns_on_pass.append(peak_dd_on_pass)
                break

        if busted and not passed_eval:
            ruined += 1

    p_arr = np.array(pass_days) if pass_days else np.array([0])
    dd_arr = np.array(max_drawdowns_on_pass) if max_drawdowns_on_pass else np.array([0])
    pass_pct = passed / total_starts * 100
    ruin_pct = ruined / total_starts * 100
    resolved_pass_pct = passed / max(1, passed + ruined) * 100
    in_progress = 100.0 - pass_pct - ruin_pct

    return {
        "max_days": max_days,
        "intra_size_stg1": intra_size_stg1,
        "intra_size_stg2": intra_size_stg2,
        "stage2_cushion": stage2_cushion,
        "pass_pct": round(pass_pct, 1),
        "ruin_pct": round(ruin_pct, 1),
        "resolved_pass_pct": round(resolved_pass_pct, 1),
        "in_progress": round(in_progress, 1),
        "median_days": round(float(np.median(p_arr)), 1) if passed > 0 else None,
        "p25_days": round(float(np.percentile(p_arr, 25)), 1) if passed > 0 else None,
        "min_days": int(p_arr.min()) if passed > 0 else None,
        "avg_dd_on_pass": round(float(dd_arr.mean()), 2) if passed > 0 else None,
        "ruin_reasons": ruin_reasons
    }

print("\n--- GRID EVALUATION: TESTING BOOK D+ HORIZONS & SIZING ---")
configs = [
    # Baseline Cushion-Staged
    ("Cushion-Staged (4 -> 8 MNQ)", dict(intra_size_stg1=4, on_size_stg1=2, intra_size_stg2=8, on_size_stg2=4, stage2_cushion=1200.0)),
    # Moderate Cushion-Staged
    ("Cushion-Staged (5 -> 9 MNQ)", dict(intra_size_stg1=5, on_size_stg1=2, intra_size_stg2=9, on_size_stg2=4, stage2_cushion=1200.0)),
    # Aggressive Cushion-Staged
    ("Cushion-Staged Sprint (6 -> 10 MNQ)", dict(intra_size_stg1=6, on_size_stg1=3, intra_size_stg2=10, on_size_stg2=4, stage2_cushion=1200.0)),
    # Free-roll Sprint (6 -> 12 MNQ)
    ("High-Frequency Sprint (6 -> 12 MNQ)", dict(intra_size_stg1=6, on_size_stg1=3, intra_size_stg2=12, on_size_stg2=4, stage2_cushion=1400.0)),
]

results = {}
for name, cfg in configs:
    print(f"\n=======================================================")
    print(f"Testing Strategy: {name}")
    print(f"=======================================================")
    results[name] = {}
    for h in [60, 75, 90, 110, 130, 180]:
        res = simulate_evaluations(**cfg, max_days=h)
        results[name][h] = res
        print(f"Horizon {h:3d}d: Pass Rate = {res['pass_pct']:5.1f}% | Ruin = {res['ruin_pct']:4.1f}% | Resolved = {res['resolved_pass_pct']:5.1f}% | Median Pass = {res['median_days']}d | In Progress = {res['in_progress']:4.1f}%")

with open(ROOT / "reports/BOOK_D_PLUS_EVALUATION_RESULTS.json", "w") as f:
    json.dump(results, f, indent=2)

print("\n[SUCCESS] Completed Book D+ Evaluation Pass Rate Optimization.")

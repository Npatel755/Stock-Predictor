import sys, json, os
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
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

daily_events = {}

for (nk, p), sk in zip(p_on.items(), skip_night):
    if sk: continue
    ex_day = next_day_fn(nk)
    e = float(mn.at[nk, "e1805"])
    lo = min(float(mn.at[nk, "low_night"]), float(low_open_dict.get(ex_day, np.inf)))
    mae = (lo - e) * 2.0 - 3.0
    daily_events.setdefault(ex_day, []).append({
        "type": "overnight",
        "pnl_1c": float(p),
        "mae_1c": mae,
        "entry_time": "18:05",
        "sleeve": "OVERNIGHT_DIP"
    })

for t in dplus:
    t_day = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
    pnl = float(t["net"])
    mae = -float(t.get("stop_risk", 25.0))
    sleeve = t["sleeve"]
    is_crabel = "CRABEL" in sleeve
    side_val = t.get("side", t.get("direction", 1))
    is_long = (side_val > 0) if isinstance(side_val, (int, float, np.integer, np.floating)) else str(side_val).lower() in ("long", "buy", "1")
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

def test_combination(include_overnight=True, on_sz=1, intra_sz=6, on_stop_pts=40.0, max_days=90):
    total_starts = len(all_calendar_days) - max_days
    passed = 0; ruined = 0
    dll_count = 0; floor_count = 0
    pass_days = []
    
    for i in range(total_starts):
        cum = 0.0; hwm = 0.0; floor = -2000.0; busted = False
        for step in range(max_days):
            d = all_calendar_days[i + step]
            events = daily_events.get(d, [])
            day_pnl = 0.0; day_mae = 0.0
            
            for ev in events:
                if ev.get("is_crabel") and not ev.get("cont"): continue
                if ev["type"] == "overnight":
                    if not include_overnight: continue
                    sz = on_sz
                    mae = max(ev["mae_1c"], -on_stop_pts * 2.0) * sz
                    pnl = ev["pnl_1c"] * sz
                    if ev["mae_1c"] < -on_stop_pts * 2.0:
                        pnl = -on_stop_pts * 2.0 * sz
                else:
                    sz = intra_sz
                    mae = ev["mae_1c"] * sz
                    pnl = ev["pnl_1c"] * sz
                    
                if (day_pnl + mae) < day_mae: day_mae = day_pnl + mae
                day_pnl += pnl
                if day_pnl >= 1750.0 or day_pnl <= -400.0: break
                
            if day_pnl <= -1000.0 or day_mae <= -1000.0 or (cum + day_mae) <= floor:
                busted = True
                dll_count += 1
                break
            cum += day_pnl
            if cum > hwm:
                hwm = cum
                floor = 0.0 if hwm >= 2000.0 else -2000.0 + hwm
            if cum <= floor:
                busted = True
                floor_count += 1
                break
            if cum >= 4000.0:
                passed += 1
                pass_days.append(step + 1)
                break
        if busted: ruined += 1
        
    p_pct = passed / total_starts * 100
    r_pct = ruined / total_starts * 100
    res_pct = passed / max(1, passed + ruined) * 100
    med = np.median(pass_days) if pass_days else 0
    print(f"ON: {include_overnight} (sz={on_sz}, stop={on_stop_pts}pt) | Intra: {intra_sz}c | 90d -> Pass: {p_pct:5.1f}% | Ruin: {r_pct:4.1f}% (DLL:{dll_count}, Floor:{floor_count}) | Resolved: {res_pct:5.1f}% | Median: {med:.1f}d")

print("--- Testing Pure Intraday vs. Stopped Overnight ---")
test_combination(include_overnight=False, intra_sz=6, max_days=90)
test_combination(include_overnight=False, intra_sz=8, max_days=90)
for st in [25.0, 35.0, 50.0]:
    test_combination(include_overnight=True, on_sz=1, intra_sz=6, on_stop_pts=st, max_days=90)
    test_combination(include_overnight=True, on_sz=2, intra_sz=6, on_stop_pts=st, max_days=90)

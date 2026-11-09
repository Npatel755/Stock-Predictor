"""book_1 (research/book_1/PROTOCOL.md): intraday-trailing-floor check of overnight_dip_v2 + ag_all_weather_v2_1c, training 2010-23."""
import json, sys, os
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import mass_1m_search as m1
os.environ["SIZING_BUDGET"] = "1e9"
srcs = (ROOT / "scripts/sizing_1_pilot.py").read_text().split("\nfor key in (")[0]; ns1 = {"__file__": str(ROOT / "scripts/sizing_1_pilot.py")}; exec(srcs, ns1)
aw = ns1["run_candidate"]("ag_all_weather_v2", True)
src3 = (ROOT / "scripts/overnight_3_pilot.py").read_text().split("out = {")[0]; n3 = {"__file__": str(ROOT / "scripts/overnight_3_pilot.py")}; exec(src3, n3)
mn, ms = n3["nights"]("MNQ"), n3["nights"]("MES"); mg, msd = ms.gap.reindex(mn.index), ms.sd20.reindex(mn.index)
mask = ((mn.gap <= -0.5 * mn.sd20) & (mg <= -0.5 * msd)).fillna(False); p_on = n3["pnl"](mn, "MNQ", ex="x0945"); p_on = p_on[mask & p_on.notna()]
b = m1.load_bars("MNQ", 1, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "low"]]; et = b.timestamp_utc.dt.tz_convert("America/New_York")
b["date"] = et.dt.date; b["sod"] = et.dt.hour * 60 + et.dt.minute; low_open = b[(b.sod >= 570) & (b.sod < 585)].groupby("date").low.min()
dates = np.array(sorted(set(mn.index) | set(low_open.index)))
def next_day(d):
    i = dates.searchsorted(d, side="right"); return dates[i] if i < len(dates) else None
TV = 2.0; ev = []  # (time, kind, worst_unrealized, realized)
for nk, p in p_on.items():
    ex_day = next_day(nk); e = float(mn.at[nk, "e1805"]); lo = min(float(mn.at[nk, "low_night"]), float(low_open.get(ex_day, np.inf)))
    t_in = pd.Timestamp(f"{nk} 18:05", tz="America/New_York"); t_out = pd.Timestamp(f"{ex_day} 09:45", tz="America/New_York")
    ev.append((t_in, "worst", (lo - e) * TV - 3.0, 0.0)); ev.append((t_out, "close", 0.0, float(p)))
for t in aw:
    ev.append((pd.Timestamp(t["entry_ts"]).tz_convert("America/New_York"), "worst", -float(t["stop_risk"]), 0.0)); ev.append((pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York"), "close", 0.0, float(t["net"])))
ev.sort(key=lambda x: x[0]); closed = 0.0; hwm = 0.0; worst_tdd = 0.0; worst_when = None; br = {2000: 0, 2500: 0, 3000: 0}; in_breach = {f: False for f in br}; day_worst = {}
for ts, kind, unreal, real in ev:
    if kind == "worst": eq = closed + unreal
    else: closed += real; eq = closed; hwm = max(hwm, eq)
    tdd = hwm - eq; d = ts.date(); day_worst[d] = min(day_worst.get(d, 0.0), eq - (closed - real if kind == "close" else closed))
    if tdd > worst_tdd: worst_tdd, worst_when = tdd, str(ts)
    for f in br:
        if tdd >= f and not in_breach[f]: br[f] += 1; in_breach[f] = True
        if tdd < f * 0.5: in_breach[f] = False
dw = pd.Series(day_worst); out = dict(intraday_trailing_dd=round(worst_tdd, 2), when=worst_when, breach_episodes=br, closed_net=round(closed, 2), worst_day_mtm=round(float(dw.min()), 2), days_mtm_below_1000=int((dw <= -1000).sum()), days_mtm_below_500=int((dw <= -500).sum()), n_events=len(ev))
print(out, flush=True); json.dump(out, open(ROOT / "reports/BOOK_1_TRAINING.json", "w"), indent=1, default=str); print("DONE")

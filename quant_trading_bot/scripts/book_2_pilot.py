"""book_2 (research/book_2/PROTOCOL.md): overnight_dip_v2 + ag_arch_d_plus_v2 as one 1c account, training 2010-23 only."""
import json, sys, os
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import mass_1m_search as m1
src = (ROOT / "scripts/dplus_1_pilot.py").read_text().split("\nout = {}")[0]; ns = {"__file__": str(ROOT / "scripts/dplus_1_pilot.py")}; exec(src, ns)
spec, run_sl, route = ns["spec"], ns["run_sl"], ns["route"]; ns1 = ns["ns1"]
by = {sl["name"]: run_sl(sl, i) for i, sl in enumerate(spec["sleeves"])}
V1 = route(sum((v for k, v in by.items() if k != "AG_TRD30_D_1c"), []))
src3 = (ROOT / "scripts/overnight_3_pilot.py").read_text().split("out = {")[0]; n3 = {"__file__": str(ROOT / "scripts/overnight_3_pilot.py")}; exec(src3, n3)
mn, ms = n3["nights"]("MNQ"), n3["nights"]("MES"); mg, msd = ms.gap.reindex(mn.index), ms.sd20.reindex(mn.index)
mask = ((mn.gap <= -0.5 * mn.sd20) & (mg <= -0.5 * msd)).fillna(False); p_on = n3["pnl"](mn, "MNQ", ex="x0945"); p_on = p_on[mask & p_on.notna()]
b = m1.load_bars("MNQ", 1, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "low"]]; et = b.timestamp_utc.dt.tz_convert("America/New_York")
b["date"] = et.dt.date; b["sod"] = et.dt.hour * 60 + et.dt.minute; low_open = b[(b.sod >= 570) & (b.sod < 585)].groupby("date").low.min()
dates = np.array(sorted(set(mn.index) | set(low_open.index)))
def next_day(d):
    i = dates.searchsorted(d, side="right"); return dates[i] if i < len(dates) else None
def book(scale):
    ev = []; daily = {}
    for nk, p in p_on.items():
        ex_day = next_day(nk); e = float(mn.at[nk, "e1805"]); lo = min(float(mn.at[nk, "low_night"]), float(low_open.get(ex_day, np.inf)))
        ev.append((pd.Timestamp(f"{nk} 18:05", tz="America/New_York"), "worst", (lo - e) * 2.0 - 3.0, 0.0)); ev.append((pd.Timestamp(f"{ex_day} 09:45", tz="America/New_York"), "close", 0.0, float(p)))
        daily[ex_day] = daily.get(ex_day, 0.0) + float(p)
    for t in V1:
        x = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York"); en = pd.Timestamp(t["entry_ts"]).tz_convert("America/New_York")
        ev.append((en, "worst", -float(t["stop_risk"]) * scale, 0.0)); ev.append((x, "close", 0.0, float(t["net"]) * scale)); daily[x.date()] = daily.get(x.date(), 0.0) + float(t["net"]) * scale
    ev.sort(key=lambda z: z[0]); closed = hwm = worst = 0.0; when = None; br = {2000: 0, 2500: 0}; inb = {f: False for f in br}
    for ts, kind, unreal, real in ev:
        if kind == "worst": eq = closed + unreal
        else: closed += real; eq = closed; hwm = max(hwm, eq)
        tdd = hwm - eq
        if tdd > worst: worst, when = tdd, str(ts)
        for f in br:
            if tdd >= f and not inb[f]: br[f] += 1; inb[f] = True
            if tdd < f * 0.5: inb[f] = False
    d = pd.Series(daily).sort_index(); yr = d.groupby(pd.to_datetime(d.index).year).sum()
    mc = ns1["breach"](d)
    return dict(closed_net=round(float(d.sum()), 2), marked_dd=round(worst, 2), when=when, touches=br, pos_years=int((yr > 0).sum()),
                by_year={int(a): round(float(v), 2) for a, v in yr.items()}, half1=round(float(yr[yr.index < 2017].sum()), 2), half2=round(float(yr[yr.index >= 2017].sum()), 2),
                worst_day=round(float(d.min()), 2), n_days=int(len(d)), breach_mc=mc)
out = dict(book_ad_1c=book(1.0), book_ad_intraday_2c=book(2.0), overnight_net=round(float(p_on.sum()), 2), dplus_v2_net=round(sum(t["net"] for t in V1), 2))
g = out["book_ad_1c"]; out["passes"] = bool(g["marked_dd"] < 2000 and g["touches"][2000] == 0 and g["closed_net"] >= 25486 and g["pos_years"] >= 11 and g["half1"] > 0 and g["half2"] > 0)
print(json.dumps(out, indent=1, default=str)); json.dump(out, open(ROOT / "reports/BOOK_2_TRAINING.json", "w"), indent=1, default=str); print("DONE")

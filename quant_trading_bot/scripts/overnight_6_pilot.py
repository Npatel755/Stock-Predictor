"""overnight_6 (research/overnight_6/PROTOCOL.md): Sunday split + pre-FOMC drift, training 2010-2023 only."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
src3 = (ROOT / "scripts/overnight_3_pilot.py").read_text().split("out = {")[0]; ns = {"__file__": str(ROOT / "scripts/overnight_3_pilot.py")}; exec(src3, ns)
nights, pnl = ns["nights"], ns["pnl"]; rng = np.random.default_rng(97)
mn, ms = nights("MNQ"), nights("MES"); mg, msd = ms.gap.reindex(mn.index), ms.sd20.reindex(mn.index)
v2 = ((mn.gap <= -0.5 * mn.sd20) & (mg <= -0.5 * msd)).fillna(False); full = pnl(mn, "MNQ", ex="x0945")
cal = pd.read_csv(ROOT / "research/news/official_calendar_2010_2026.csv"); fomc = set(pd.to_datetime(cal[cal.family == "FOMC"].date_et).dt.date)
dates = np.array(sorted(set(mn.index)))
def next_day(d):
    i = dates.searchsorted(d, side="right"); return dates[i] if i < len(dates) else None
pre_fomc = pd.Series([next_day(d) in fomc for d in mn.index], index=mn.index)
def stats(q, n_plc=0):
    q = q.dropna(); yr = q.groupby(mn.year.loc[q.index]).sum(); eq = q.cumsum()
    r = dict(net=round(float(q.sum()), 2), nights=int(len(q)), per_night=round(float(q.mean()), 2) if len(q) else None, pos_years=int((yr > 0).sum()), years=int(len(yr)),
             max_dd=round(float((eq.cummax() - eq).max()), 2) if len(q) else None, pre2020=round(float(yr[yr.index < 2020].sum()), 2), t=round(float(q.mean() / q.std() * np.sqrt(len(q))), 2) if len(q) > 2 else None,
             by_year={int(y): round(float(v), 2) for y, v in yr.items()})
    if n_plc:
        cnt = yr.index.to_series().map(q.groupby(mn.year.loc[q.index]).size()); plc = []
        for _ in range(n_plc):
            pick = np.concatenate([rng.choice(mn.index[mn.year == y], size=min(int(c), int((mn.year == y).sum())), replace=False) for y, c in cnt.items()])
            plc.append(float(full.loc[pick].fillna(0).sum()))
        r.update(beat=int(sum(r["net"] > x for x in plc)), n_plc=n_plc, placebo_mean=round(float(np.mean(plc)), 2))
    return r
out = {"champion": stats(full[v2])}
out["S1_sunday_only"] = stats(full[v2 & (mn.dow == 6)]); out["S2_weekday_only"] = stats(full[v2 & (mn.dow != 6)])
out["F3_pre_fomc_unconditional"] = stats(full[pre_fomc], 200); f3 = out["F3_pre_fomc_unconditional"]
f3["pass"] = bool(f3["net"] > 0 and f3["pos_years"] >= 10 and (f3["t"] or 0) >= 2 and f3["beat"] >= 190)
out["F4_v2_union_pre_fomc"] = stats(full[v2 | pre_fomc]); f4 = out["F4_v2_union_pre_fomc"]; ch = out["champion"]
f4["pass"] = bool(f4["net"] > ch["net"] and f4["pos_years"] >= 12 and f4["max_dd"] <= ch["max_dd"] and f4["per_night"] >= ch["per_night"])
for k, v in out.items(): print(k, {a: b for a, b in v.items() if a != "by_year"}, flush=True)
json.dump(out, open(ROOT / "reports/OVERNIGHT_6_TRAINING.json", "w"), indent=1, default=str); print("DONE")

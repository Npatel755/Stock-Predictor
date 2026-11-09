"""overnight_5 (research/overnight_5/PROTOCOL.md): calendar gate on overnight_dip_v2, training 2010-2023 only."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
src3 = (ROOT / "scripts/overnight_3_pilot.py").read_text().split("out = {")[0]; ns = {"__file__": str(ROOT / "scripts/overnight_3_pilot.py")}; exec(src3, ns)
nights, pnl, SPEC = ns["nights"], ns["pnl"], ns["SPEC"]
mn, ms = nights("MNQ"), nights("MES"); mg, msd = ms.gap.reindex(mn.index), ms.sd20.reindex(mn.index)
mask = ((mn.gap <= -0.5 * mn.sd20) & (mg <= -0.5 * msd)).fillna(False); p = pnl(mn, "MNQ", ex="x0945"); p = p[mask & p.notna()]; n = mn.loc[p.index]
cal = pd.read_csv(ROOT / "research/news/official_calendar_2010_2026.csv"); cal["d"] = pd.to_datetime(cal.date_et).dt.date
rel_days = set(cal[cal.family.isin(["CPI", "EMPLOYMENT", "PPI", "RETAIL_SALES", "GDP"]) & (cal.minute_et == 510)].d); fomc_days = set(cal[cal.family == "FOMC"].d)
# exit day = next trading date after the entry date = date of the 09:45 bar; approximate with the next date present in the bars' trading-date list
dates = np.array(sorted(set(mn.index))); 
def next_day(d):
    i = dates.searchsorted(d, side="right"); return dates[i] if i < len(dates) else None
xd = pd.Series({d: next_day(d) for d in p.index})
is_rel = xd.map(lambda d: d in rel_days).astype(bool); is_fomc = xd.map(lambda d: d in fomc_days).astype(bool)
def stats(q):
    yr = q.groupby(n.year.loc[q.index]).sum(); eq = q.cumsum()
    return dict(net=round(float(q.sum()), 2), nights=int(len(q)), per_night=round(float(q.mean()), 2) if len(q) else None, pos_years=int((yr > 0).sum()), max_dd=round(float((eq.cummax() - eq).max()), 2) if len(q) else None,
                pre2020=round(float(yr[yr.index < 2020].sum()), 2), t=round(float(q.mean() / q.std() * np.sqrt(len(q))), 2) if len(q) > 2 else None)
out = {"champion": stats(p)}
V = {"R1_skip_release": ~is_rel, "R2_release_only": is_rel, "F1_skip_fomc": ~is_fomc, "F2_fomc_only": is_fomc, "R3_skip_release_and_fomc": ~(is_rel | is_fomc)}
for k, m in V.items():
    r = stats(p[m.values]); removed = stats(p[~m.values]) if (~m.values).any() else None; r["removed"] = removed
    r["pass"] = bool(k.startswith(("R1", "F1", "R3")) and r["net"] > out["champion"]["net"] and r["pos_years"] >= 12 and r["max_dd"] <= out["champion"]["max_dd"] and r["per_night"] >= out["champion"]["per_night"]
                     and r["nights"] >= 100 and removed and removed["net"] < 0 and (removed["t"] or 0) <= -1.5)
    out[k] = r; print(k, r, flush=True)
leg = ((mn.x0945 - mn.x0830) / SPEC["MNQ"]["tick"]).loc[p.index]; out["attribution"] = dict(release_nights_0830_0945_ticks=round(float(leg[is_rel.values].mean()), 2), other_nights_0830_0945_ticks=round(float(leg[~is_rel.values].mean()), 2))
print("champion", out["champion"], "attribution", out["attribution"]); json.dump(out, open(ROOT / "reports/OVERNIGHT_5_TRAINING.json", "w"), indent=1, default=str); print("DONE")

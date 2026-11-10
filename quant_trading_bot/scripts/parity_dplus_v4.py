"""Parity: runner candidate ag_arch_d_plus_v2_gapsize_4c_v4 vs the dplus_7e research cell (4-micro continuation, $600 account stop).

Training 2010-23 only. Research side = scripts/dplus_7e_pilot.py's routed 3c v3 trades with post-hoc 4/3 continuation scaling and the
account-level stop. Runner side = ensemble_paper.run_routed on the same bars. Compared per entry (base + addon twins summed) and per day.
Writes reports/PARITY_DPLUS_V4.md and reports/PARITY_DPLUS_V4.json.
"""
import json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P = (ROOT / "scripts/dplus_7e_pilot.py").read_text(encoding="utf-8")
ns = {"__file__": str(ROOT / "scripts/dplus_7e_pilot.py")}
exec(P.split("\nout = {}")[0], ns)
ep, tr, gs, NY, OVR, measure = ns["ep"], ns["tr"], ns["gs"], ns["NY"], ns["OVR"], ns["measure"]
d7 = ns["ns"]; bars_for = d7["bars_for"]; START = d7["ns"]["START"]
CM, X = 4 / 3, 600.0

# ---- research rows (same construction as dplus_7e measure(), kept for trade-level comparison)
rows = []
for t in tr:
    tin = pd.Timestamp(t["entry_ts"]).tz_convert(NY); tout = pd.Timestamp(t["exit_ts"]).tz_convert(NY)
    cont = "CRABEL" in t["sleeve"] and int(t["side"]) * gs.get(tin.date(), 0) >= 0
    rows.append(dict(tin=tin, tout=tout, net=float(t["net"]) * (CM if cont else 1), day=tout.date(), eday=tin.date()))
rows.sort(key=lambda r: r["tin"])
kept = []
for r in rows:
    if sum(x["net"] for x in kept if x["day"] == r["eday"] and x["tout"] <= r["tin"]) <= -X:
        continue
    kept.append(r)
research_metrics = measure(CM, X)

# ---- runner (engine overrides cleared: the candidate's own sleeve settings must carry hard_drawdown / daily_loss)
OVR.clear()
spec = ep.CANDIDATES["ag_arch_d_plus_v2_gapsize_4c_v4"]
sleeves = [sl for k in ("ag_arch_d_plus_v2_3c_v3", "ag_arch_d_plus_v2_gap_addon_1of3_v3") for sl in ep.CANDIDATES[k]["sleeves"]]
bars = {}
for sl in sleeves:
    bars.setdefault(ep.bars_key(sl), bars_for(sl)[0])
runs = ep.run_routed(spec, bars, START)
rt = [t for r in runs.values() for t in r["trades"]]
assert max(pd.Timestamp(t["exit_ts"]) for t in rt) < pd.Timestamp("2024-01-01", tz="UTC")

R = pd.Series([r["net"] for r in kept], index=[r["tin"] for r in kept]).groupby(level=0).sum()
Q = pd.Series([float(t["net"]) for t in rt], index=[pd.Timestamp(t["entry_ts"]).tz_convert(NY) for t in rt]).groupby(level=0).sum()
both = R.index.intersection(Q.index)
diff = (R[both] - Q[both]).abs()
Rd = pd.Series([r["net"] for r in kept], index=[r["day"] for r in kept]).groupby(level=0).sum()
Qd = pd.Series([float(t["net"]) for t in rt], index=[pd.Timestamp(t["exit_ts"]).tz_convert(NY).date() for t in rt]).groupby(level=0).sum()


def day_stats(day):
    wd = day[day > 0]; yrs = pd.Series(day.values, index=pd.to_datetime(day.index))
    d150 = yrs[yrs >= 150].groupby(yrs[yrs >= 150].index.year).size().reindex(range(2010, 2024), fill_value=0)
    return dict(net=round(float(day.sum()), 2), median_win_day=round(float(np.median(wd)), 2), days150_per_year=round(float(d150.mean()), 1),
                worst_day=round(float(day.min()), 2), days_le_minus_1000=int((day <= -1000).sum()))


out = dict(research_entries=len(R), runner_entries=len(Q), common_entries=len(both), research_only=len(R.index.difference(Q.index)),
           runner_only=len(Q.index.difference(R.index)), max_abs_net_diff_common=round(float(diff.max()), 4) if len(diff) else None,
           research_days=day_stats(Rd), runner_days=day_stats(Qd), research_metrics_dplus_7e=research_metrics,
           research_only_sample=[str(x) for x in R.index.difference(Q.index)[:10]], runner_only_sample=[str(x) for x in Q.index.difference(R.index)[:10]])
out["exact"] = bool(out["research_only"] == 0 and out["runner_only"] == 0 and (out["max_abs_net_diff_common"] or 0) < 0.02)
(ROOT / "reports/PARITY_DPLUS_V4.json").write_text(json.dumps(out, indent=1, default=str))
print(json.dumps(out, indent=1, default=str))

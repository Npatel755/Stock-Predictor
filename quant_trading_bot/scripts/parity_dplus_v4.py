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
# The live VIX filter fetches only the last year from yfinance; for a 2010-23 replay give it the same CBOE history the research used
# (data/external VIX/VIX3M CSVs, VIX > VIX3M at the CBOE close), otherwise the stand-aside silently does nothing.
def _cboe(n):
    d = pd.read_csv(ROOT / f"data/external/{n}_History.csv"); d.index = pd.to_datetime(d.DATE, format="%m/%d/%Y"); return d.CLOSE.astype(float)
_j = pd.concat([_cboe("VIX").rename("vix"), _cboe("VIX3M").rename("vix3m")], axis=1).dropna().sort_index()
ep._VIX_CACHE["series"] = (_j.vix > _j.vix3m)
spec = ep.CANDIDATES["ag_arch_d_plus_v2_gapsize_4c_v4"]
sleeves = [sl for k in ("ag_arch_d_plus_v2_3c_v4", "ag_arch_d_plus_v2_gap_addon_1of3_v4") for sl in ep.CANDIDATES[k]["sleeves"]]
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
bad = diff[diff > 0.02].sort_values(ascending=False)
out["entries_with_net_diff"] = len(bad)
out["net_diff_detail"] = [dict(entry=str(k), research=round(float(R[k]), 2), runner=round(float(Q[k]), 2),
                               runner_trades=[(t["sleeve"], t["qty"], t["net"], t["exit_ts"]) for t in rt if pd.Timestamp(t["entry_ts"]).tz_convert(NY) == k],
                               research_rows=[(round(r["net"], 2), str(r["tout"])) for r in kept if r["tin"] == k]) for k in bad.index[:8]]

# ---- diagnostics: where does the gap come from?
fam = lambda s: "CRABEL" if "CRABEL" in s else ("MES" if "MES" in s else "TRD60")
yr_r = pd.DataFrame([(fam(t["sleeve"]), pd.Timestamp(t["exit_ts"]).year, float(t["net"])) for t in tr], columns=["sl", "yr", "net"])
yr_q0 = None
base_runs = ep.run_routed(ep.CANDIDATES["ag_arch_d_plus_v2_3c_v4"], bars, START)        # plain 3c v4 base, no addon, no account stop
bt = [t for r in base_runs.values() for t in r["trades"]]
yr_q0 = pd.DataFrame([(fam(t["sleeve"]), pd.Timestamp(t["exit_ts"]).year, float(t["net"])) for t in bt], columns=["sl", "yr", "net"])
out["base_3c_v3_research_net_by_sleeve"] = yr_r.groupby("sl").net.sum().round(0).to_dict()
out["base_3c_v3_runner_net_by_sleeve"] = yr_q0.groupby("sl").net.sum().round(0).to_dict()
out["base_3c_v3_research_trades"] = len(tr); out["base_3c_v3_runner_trades"] = len(bt)
out["base_3c_v3_net_by_year"] = {int(y): [round(float(yr_r[yr_r.yr == y].net.sum()), 0), round(float(yr_q0[yr_q0.yr == y].net.sum()), 0)] for y in sorted(yr_r.yr.unique())}
out["runner_locks"] = {n: r.get("lock") for n, r in base_runs.items()}
out["runner_last_trade_by_sleeve"] = {n: (r["trades"][-1]["exit_ts"] if r["trades"] else None) for n, r in base_runs.items()}
# independent (unrouted) sleeve runs on the runner path, to separate routing from engine state
indep = {sl["name"]: ep.run_sleeve(sl, bars[ep.bars_key(sl)], START, ep.day_filter_mask(ep.CANDIDATES["ag_arch_d_plus_v2_3c_v4"], bars[ep.bars_key(sl)], sl))
         for sl in ep.CANDIDATES["ag_arch_d_plus_v2_3c_v4"]["sleeves"]}
out["unrouted_runner_net_by_sleeve"] = {n: [len(r["trades"]), round(sum(float(t["net"]) for t in r["trades"]), 0), r.get("lock")] for n, r in indep.items()}
(ROOT / "reports/PARITY_DPLUS_V4.json").write_text(json.dumps(out, indent=1, default=str))
print(json.dumps(out, indent=1, default=str))

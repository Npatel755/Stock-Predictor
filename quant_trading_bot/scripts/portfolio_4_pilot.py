"""portfolio_4 (research/portfolio_4/PROTOCOL.md): ag_all_weather_v2_1c + overnight_dip_v2 combined, training 2010-2023, no parameter changes."""
import json, sys, os
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
rng = np.random.default_rng(137)
os.environ["SIZING_BUDGET"] = "1e9"
srcs = (ROOT / "scripts/sizing_1_pilot.py").read_text().split("\nfor key in (")[0]; ns1 = {"__file__": str(ROOT / "scripts/sizing_1_pilot.py")}; exec(srcs, ns1)
aw = ns1["run_candidate"]("ag_all_weather_v2", True); d_aw = ns1["daily"](aw)
src3 = (ROOT / "scripts/overnight_3_pilot.py").read_text().split("out = {")[0]; n3 = {"__file__": str(ROOT / "scripts/overnight_3_pilot.py")}; exec(src3, n3)
mn, ms = n3["nights"]("MNQ"), n3["nights"]("MES"); mg, msd = ms.gap.reindex(mn.index), ms.sd20.reindex(mn.index)
mask = ((mn.gap <= -0.5 * mn.sd20) & (mg <= -0.5 * msd)).fillna(False); p_on = n3["pnl"](mn, "MNQ", ex="x0945"); p_on = p_on[mask & p_on.notna()]
dates = np.array(sorted(set(mn.index) | set(d_aw.index)))
def next_day(d):
    i = dates.searchsorted(d, side="right"); return dates[i] if i < len(dates) else None
on_daily = pd.Series(p_on.values, index=[next_day(d) for d in p_on.index]).groupby(level=0).sum()
cal = sorted(set(on_daily.index) | set(d_aw.index)); D = pd.DataFrame(index=cal); D["overnight"] = on_daily.reindex(cal).fillna(0); D["aw_1c"] = d_aw.reindex(cal).fillna(0); D["total"] = D.overnight + D.aw_1c
D["year"] = [d.year for d in D.index]; D["month"] = [f"{d.year}-{d.month:02d}" for d in D.index]
def dd(x): e = x.cumsum(); return float((e.cummax() - e).max())
def mc(x, n_days, paths=3000, L=10, floors=(2000, 3000)):
    x = x.to_numpy(); n = len(x); br = {f: 0 for f in floors}; nets = []
    for _ in range(paths):
        idx = []
        while len(idx) < n_days:
            st = rng.integers(n); ln = rng.geometric(1 / L); idx.extend(((st + np.arange(ln)) % n).tolist())
        idx = np.array(idx[:n_days]); e = np.cumsum(x[idx]); pk = np.maximum.accumulate(np.concatenate([[0], e]))[:-1]; m = (pk - e).max()
        for f in floors: br[f] += int(m >= f)
        nets.append(float(e[-1]))
    return dict(**{f"p_dd_{f}": round(br[f] / paths, 3) for f in floors}, net_p5=round(float(np.percentile(nets, 5))), net_p50=round(float(np.median(nets))), net_p95=round(float(np.percentile(nets, 95))))
yr = D.groupby("year")[["overnight", "aw_1c", "total"]].sum().round(2); mo = D.groupby("month")[["overnight", "aw_1c"]].sum()
fills = [pd.Timestamp(x["entry_ts"]).tz_convert("America/New_York") for x in aw]; on_exit = {next_day(d): pd.Timestamp(f"{next_day(d)} 09:45", tz="America/New_York") for d in p_on.index}
viol = sum(1 for f in fills if f.date() in on_exit and f < on_exit[f.date()])
per_year = len(D) / 14; sel = ~D.year.isin([2020, 2021, 2022])
out = dict(by_year={int(y): r.to_dict() for y, r in yr.iterrows()}, monthly_corr=round(float(mo.overnight.corr(mo.aw_1c)), 3), net=dict(overnight=round(float(D.overnight.sum()), 2), aw_1c=round(float(D.aw_1c.sum()), 2), total=round(float(D.total.sum()), 2)),
           closed_dd=dict(overnight=round(dd(D.overnight), 2), aw_1c=round(dd(D.aw_1c), 2), total=round(dd(D.total), 2)), worst_day=dict(total=round(float(D.total.min()), 2), date=str(D.total.idxmin())), overlap_violations=int(viol),
           mc=dict(total_1y=mc(D.total, int(per_year)), ex2020_22_1y=mc(D.total[sel], int(per_year)), aw_1c_alone_1y=mc(D.aw_1c, int(per_year)), overnight_alone_1y=mc(D.overnight, int(per_year))))
out["decision_ok"] = bool(out["closed_dd"]["total"] < 2000 and out["mc"]["total_1y"]["p_dd_2000"] <= 0.10)
print(yr.to_string()); print({k: v for k, v in out.items() if k != "by_year"}, flush=True)
json.dump(out, open(ROOT / "reports/PORTFOLIO_4_TRAINING.json", "w"), indent=1, default=str); print("DONE")

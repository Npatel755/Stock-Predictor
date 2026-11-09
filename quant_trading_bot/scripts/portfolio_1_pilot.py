"""portfolio_1 (research/portfolio_1/PROTOCOL.md): overnight_dip_v2 + ag_arch_c combined, training 2010-2023, no parameter changes."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
rng = np.random.default_rng(83)
# --- overnight v2 nightly P&L
src3 = (ROOT / "scripts/overnight_3_pilot.py").read_text().split("out = {")[0]; ns3 = {"__file__": str(ROOT / "scripts/overnight_3_pilot.py")}; exec(src3, ns3)
mn, ms = ns3["nights"]("MNQ"), ns3["nights"]("MES"); mg, msd = ms.gap.reindex(mn.index), ms.sd20.reindex(mn.index)
mask = ((mn.gap <= -0.5 * mn.sd20) & (mg <= -0.5 * msd)).fillna(False); p_on = ns3["pnl"](mn, "MNQ", ex="x0945"); p_on = p_on[mask & p_on.notna()]
s = ns3["SPEC"]["MNQ"]; worst_on = ((mn.low_night - mn.e1805) / s["tick"] * s["tv"] - ((s["spread"] + 2) * s["tv"] + 2 * ns3["COMM"])).loc[p_on.index]
# the overnight P&L is booked on the EXIT day (next trading day); map entry date -> exit date via the 09:45 bar date
exit_day = pd.Series({d: (pd.Timestamp(d) + pd.Timedelta(days=1)).date() for d in p_on.index})
# --- arch c trades
srcc = (ROOT / "scripts/replicate_antigravity_arch_c.py").read_text().split('out["sender_claim_2010_23"]')[0]; nsc = {"__file__": str(ROOT / "scripts/replicate_antigravity_arch_c.py")}; exec(srcc, nsc)
acc = nsc["acc"]; tc = pd.DataFrame(acc); tc["day"] = pd.to_datetime(tc.entry_ts).dt.tz_convert("America/New_York").dt.date; tc["exit_day"] = pd.to_datetime(tc.exit_ts).dt.tz_convert("America/New_York").dt.date
d_arch = tc.groupby("exit_day").net.sum()
# daily series on the union calendar
on_daily = pd.Series(p_on.values, index=[exit_day[d] for d in p_on.index]).groupby(level=0).sum()
cal = sorted(set(on_daily.index) | set(d_arch.index)); D = pd.DataFrame(index=cal); D["overnight"] = on_daily.reindex(cal).fillna(0); D["arch_c"] = d_arch.reindex(cal).fillna(0); D["total"] = D.overnight + D.arch_c
D["year"] = [d.year for d in D.index]; D["month"] = [f"{d.year}-{d.month:02d}" for d in D.index]
out = {}
yr = D.groupby("year")[["overnight", "arch_c", "total"]].sum().round(2); out["by_year"] = {int(y): r.to_dict() for y, r in yr.iterrows()}; print(yr.to_string(), flush=True)
mo = D.groupby("month")[["overnight", "arch_c"]].sum(); out["monthly_corr"] = round(float(mo.overnight.corr(mo.arch_c)), 3)
out["years_both_negative"] = int(((yr.overnight < 0) & (yr.arch_c < 0)).sum())
def dd(x): e = x.cumsum(); return float((e.cummax() - e).max())
out["closed_dd"] = dict(overnight=round(dd(D.overnight), 2), arch_c=round(dd(D.arch_c), 2), total=round(dd(D.total), 2))
out["net"] = dict(overnight=round(float(D.overnight.sum()), 2), arch_c=round(float(D.arch_c.sum()), 2), total=round(float(D.total.sum()), 2))
out["worst_day"] = dict(total=round(float(D.total.min()), 2), date=str(D.total.idxmin()))
# overlap check: overnight position open at an intraday fill -> overnight entry date == trade day - 1 and overnight exit after the fill (never, exit 09:45 < 10:00)
fills = pd.to_datetime(tc.entry_ts).dt.tz_convert("America/New_York"); viol = 0
on_exit_ts = {exit_day[d]: pd.Timestamp(f"{exit_day[d]} 09:45", tz="America/New_York") for d in p_on.index}
for f in fills:
    x = on_exit_ts.get(f.date())
    if x is not None and f < x: viol += 1
out["overlap_violations"] = viol
# breach MC on combined daily P&L with intrabar-approximate worst (overnight marked at the night low on its exit day)
worst_daily = pd.Series(worst_on.values, index=[exit_day[d] for d in p_on.index]).groupby(level=0).sum().reindex(cal).fillna(0) + D.arch_c
def mc(x, w, n_days, paths=5000, L=10):
    x = x.to_numpy(); w = w.to_numpy(); n = len(x); closed = intra = 0; nets = []
    for _ in range(paths):
        idx = []
        while len(idx) < n_days:
            st = rng.integers(n); ln = rng.geometric(1 / L); idx.extend(((st + np.arange(ln)) % n).tolist())
        idx = np.array(idx[:n_days]); e = np.cumsum(x[idx]); pk = np.maximum.accumulate(np.concatenate([[0], e]))[:-1]
        closed += int((pk - e).max() >= 2000); intra += int((pk - (e - x[idx] + w[idx])).max() >= 2000); nets.append(float(e[-1]))
    nets = np.array(nets); return dict(p_closed_dd_2k=round(closed / paths, 3), p_intrabar_dd_2k=round(intra / paths, 3), net_p5=round(float(np.percentile(nets, 5))), net_p50=round(float(np.percentile(nets, 50))), net_p95=round(float(np.percentile(nets, 95))))
per_year = len(D) / 14
out["mc"] = {"total_1y": mc(D.total, worst_daily, int(per_year)), "total_2y": mc(D.total, worst_daily, int(2 * per_year))}
sel = ~D.year.isin([2020, 2021, 2022]); out["mc"]["ex2020_22_1y"] = mc(D.total[sel], worst_daily[sel], int(per_year))
out["mc"]["arch_c_alone_1y"] = mc(D.arch_c, D.arch_c, int(per_year)); out["mc"]["overnight_alone_1y"] = mc(D.overnight, worst_daily - D.arch_c, int(per_year))
out["decision_ok"] = bool(out["closed_dd"]["total"] < 2000 and out["mc"]["total_1y"]["p_intrabar_dd_2k"] <= 0.10 and out["monthly_corr"] <= 0.3)
print({k: v for k, v in out.items() if k != "by_year"}, flush=True)
json.dump(out, open(ROOT / "reports/PORTFOLIO_1_TRAINING.json", "w"), indent=1, default=str); print("DONE")

"""dplus_7: size-scaled engine gates for 4-micro gap-sized D+ (research/dplus_7/PROTOCOL.md), training only."""
import json
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
F = (ROOT / "scripts/funded_1_pilot.py").read_text(); nf = {"np": np, "pd": pd}; exec(F[F.index("def sim("):F.index("starts = ")], nf); sim = nf["sim"]
src = (ROOT / "scripts/dplus_1_pilot.py").read_text().split("\nout = {}")[0]; ns = {"__file__": str(ROOT / "scripts/dplus_1_pilot.py")}; exec(src, ns)
ep, run_sl, route, bars_for = ns["ep"], ns["run_sl"], ns["route"], ns["bars_for"]
eng = ep.engine(); _orig = eng["execution_cfg"]; OVR = {}
def _cfg(c):
    d = _orig(c); d.update(OVR); return d
eng["execution_cfg"] = _cfg
sls = ep.CANDIDATES["ag_arch_d_plus_v2"]["sleeves"]; cr = [s for s in sls if "CRABEL" in s["name"]][0]; gs = ep.gap_sign_by_day(bars_for(cr)[0]); NY = "America/New_York"
starts = pd.date_range("2010-01-01", "2023-01-01", freq="MS", tz=NY)
def measure(tr, gm=2):
    rows = []
    for t in tr:
        tin = pd.Timestamp(t["entry_ts"]).tz_convert(NY); tout = pd.Timestamp(t["exit_ts"]).tz_convert(NY)
        m = gm if ("CRABEL" in t["sleeve"] and int(t["side"]) * gs.get(tin.date(), 0) >= 0) else 1
        rows.append(dict(tin=tin, tout=tout, net=float(t["net"]) * m, worst=-float(t["stop_risk"]) * m, day=tout.date()))
    nets = np.array([r["net"] for r in rows]); wins = nets[nets > 0]; day = pd.Series(nets, index=[r["day"] for r in rows]).groupby(level=0).sum(); wd = day[day > 0]
    yrs = pd.Series(day.values, index=pd.to_datetime(day.index)); d150 = yrs[yrs >= 150].groupby(yrs[yrs >= 150].index.year).size().reindex(range(2010, 2024), fill_value=0)
    ev = []
    for r in rows: ev.append((r["tin"], 0, r["worst"], 0.0, r["day"])); ev.append((r["tout"], 1, 0.0, r["net"], r["day"]))
    ev.sort(key=lambda x: (x[0], x[1]))
    res = [sim([x for x in ev if s0 <= x[0] < s0 + pd.DateOffset(months=12)], "STATIC", 1000.0, horizon_end=s0 + pd.DateOffset(months=12)) for s0 in starts]
    oc = pd.Series([r["outcome"] for r in res]); ok = [r["closed"] for r in res if r["outcome"] == "open"]; eq = day.cumsum(); yr = day.groupby(pd.to_datetime(day.index).year).sum()
    return dict(trades=len(rows), net=round(float(nets.sum()), 2), per=round(float(nets.mean()), 2), pos_years=int((yr > 0).sum()), closed_dd=round(float((eq.cummax() - eq).max()), 2),
                median_win_trade=round(float(np.median(wins)), 2), share_win_ge150=round(float((wins >= 150).mean()), 3), median_win_day=round(float(np.median(wd)), 2),
                share_win_days_ge150=round(float((wd >= 150).mean()), 3), days150_per_year=round(float(d150.mean()), 1), worst_day=round(float(day.min()), 2),
                p_breach_static=round(float((oc == "fail_floor").mean()), 3), p_dll=round(float((oc == "fail_dll").mean()), 3), median_net_12m=round(float(np.median(ok)), 2) if ok else None)
CELLS = {"k3_hdd6000_dl1200": (3, dict(hard_drawdown=6000.0)), "k4_hdd8000_dl1600": (4, dict(hard_drawdown=8000.0)), "k4_hdd8000_dl800": (4, dict(hard_drawdown=8000.0, daily_loss=800.0)),
         "k4_hdd8000_dl600": (4, dict(hard_drawdown=8000.0, daily_loss=600.0)), "k4_hdd8000_dl400": (4, dict(hard_drawdown=8000.0, daily_loss=400.0))}
out = {}
for name, (k, o) in CELLS.items():
    OVR.clear(); OVR.update(o)
    sk = [dict(sl, name=sl["name"] + f"_{k}c", max_contracts=k, risk_per_trade=150.0 * k, max_open_risk=150.0 * k) for sl in sls]
    tr = route(sum((run_sl(sl, i) for i, sl in enumerate(sk)), []))
    out[name] = measure(tr); r = out[name]
    r["gate"] = bool(r["median_win_trade"] >= 150 and r["median_win_day"] >= 150 and r["p_breach_static"] <= 0.02 and r["p_dll"] <= 0.02 and r["per"] >= 40.72 and r["pos_years"] >= 11)
    print(name, r, flush=True)
json.dump(out, open(ROOT / "reports/DPLUS_7_TRAINING.json", "w"), indent=1, default=str); print("DONE", flush=True)

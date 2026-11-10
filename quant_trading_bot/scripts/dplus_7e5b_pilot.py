"""dplus_7e: account-level daily stop on the 3c v3 base with 4/5-micro continuation (research/dplus_7/PROTOCOL.md addendum 4)."""
import json
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
P = (ROOT / "scripts/dplus_7_pilot.py").read_text(); ns = {"__file__": str(ROOT / "scripts/dplus_7_pilot.py")}
exec(P.split("CELLS = {")[0], ns)
ep, run_sl, route, OVR, gs, NY, starts, sim = ns["ep"], ns["run_sl"], ns["route"], ns["OVR"], ns["gs"], ns["NY"], ns["starts"], ns["sim"]
sls = ep.CANDIDATES["ag_arch_d_plus_v2"]["sleeves"]
OVR.clear(); OVR.update(hard_drawdown=6000.0, daily_loss=600.0)
sk = [dict(sl, name=sl["name"] + "_3c", max_contracts=3, risk_per_trade=450.0, max_open_risk=450.0) for sl in sls]
tr = route(sum((run_sl(sl, i) for i, sl in enumerate(sk)), []))
def measure(cm, X):
    rows = []
    for t in tr:
        tin = pd.Timestamp(t["entry_ts"]).tz_convert(NY); tout = pd.Timestamp(t["exit_ts"]).tz_convert(NY)
        cont = "CRABEL" in t["sleeve"] and int(t["side"]) * gs.get(tin.date(), 0) >= 0; m = cm if cont else 1
        rows.append(dict(tin=tin, tout=tout, net=float(t["net"]) * m, worst=-float(t["stop_risk"]) * m, day=tout.date(), eday=tin.date()))
    rows.sort(key=lambda r: r["tin"])
    if X is not None:  # account-level daily stop: drop entries made after the day's realised P&L (trades exited earlier that day) <= -X
        kept = []; 
        for r in rows:
            realised = sum(x["net"] for x in kept if x["day"] == r["eday"] and x["tout"] <= r["tin"])
            if realised <= -X: continue
            kept.append(r)
        rows = kept
    nets = np.array([r["net"] for r in rows]); wins = nets[nets > 0]; day = pd.Series(nets, index=[r["day"] for r in rows]).groupby(level=0).sum(); wd = day[day > 0]
    yrs = pd.Series(day.values, index=pd.to_datetime(day.index)); d150 = yrs[yrs >= 150].groupby(yrs[yrs >= 150].index.year).size().reindex(range(2010, 2024), fill_value=0)
    ev = []
    for r in rows: ev.append((r["tin"], 0, r["worst"], 0.0, r["day"])); ev.append((r["tout"], 1, 0.0, r["net"], r["day"]))
    ev.sort(key=lambda x: (x[0], x[1]))
    res = [sim([x for x in ev if s0 <= x[0] < s0 + pd.DateOffset(months=12)], "STATIC", 1000.0, horizon_end=s0 + pd.DateOffset(months=12)) for s0 in starts]
    oc = pd.Series([r["outcome"] for r in res]); ok = [r["closed"] for r in res if r["outcome"] == "open"]; eq = day.cumsum(); yr = day.groupby(pd.to_datetime(day.index).year).sum()
    r = dict(trades=len(rows), net=round(float(nets.sum()), 2), per=round(float(nets.mean()), 2), pos_years=int((yr > 0).sum()), closed_dd=round(float((eq.cummax() - eq).max()), 2),
             median_win_trade=round(float(np.median(wins)), 2), share_win_ge150=round(float((wins >= 150).mean()), 3), median_win_day=round(float(np.median(wd)), 2), share_win_days_ge150=round(float((wd >= 150).mean()), 3),
             days150_per_year=round(float(d150.mean()), 1), worst_day=round(float(day.min()), 2), days_le_1000=int((day <= -1000).sum()), days_le_800=int((day <= -800).sum()),
             p_breach_static=round(float((oc == "fail_floor").mean()), 3), p_dll=round(float((oc == "fail_dll").mean()), 3), median_net_12m=round(float(np.median(ok)), 2) if ok else None)
    r["gate"] = bool(r["median_win_trade"] >= 150 and r["median_win_day"] >= 150 and r["p_breach_static"] <= 0.02 and r["p_dll"] <= 0.02 and r["per"] >= 40.72 and r["pos_years"] >= 11)
    return r
out = {}
for cm, cname in ((5/3, "5mic"),):
    for X in (600.0, 400.0):
        name = f"cont_{cname}_acct_stop_{int(X) if X else 'none'}"; out[name] = measure(cm, X); print(name, out[name], flush=True)
json.dump(out, open(ROOT / "reports/DPLUS_7E5B_TRAINING.json", "w"), indent=1, default=str); print("DONE", flush=True)

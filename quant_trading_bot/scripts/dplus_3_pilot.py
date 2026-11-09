"""dplus_3 (research/dplus_3/PROTOCOL.md): event-day stand-aside, execution stress and gate sensitivity for ag_arch_d_plus_v2, training only."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/dplus_1_pilot.py").read_text().split("\nout = {}")[0]; ns = {"__file__": str(ROOT / "scripts/dplus_1_pilot.py")}; exec(src, ns)
ep, run_sl, route, stats, marked = ns["ep"], ns["run_sl"], ns["route"], ns["stats"], ns["marked"]
sls = ep.CANDIDATES["ag_arch_d_plus_v2"]["sleeves"]
eng = ep.engine(); _orig = eng["execution_cfg"]; OVR = {}
def _cfg(c):
    d = _orig(c); d.update(OVR); return d
eng["execution_cfg"] = _cfg
def run_v2():
    return route(sum((run_sl(sl, i) for i, sl in enumerate(sls)), []))
def summ(tr):
    s = stats(tr); by = s.pop("by_year"); return dict(s, **marked(tr))
out = {}
base = run_v2(); out["base"] = summ(base); print("base", out["base"], flush=True)
for t in base: t["day"] = pd.Timestamp(t["entry_ts"]).tz_convert("America/New_York").date()
# A. event-day stand-aside, post-hoc on the routed list
cal = pd.read_csv(ROOT / "research/news/official_calendar_2010_2026.csv"); cal = cal[cal.date_et < "2024-01-01"]
days = {f: set(pd.to_datetime(cal[cal.family == f].date_et).dt.date) for f in ("FOMC", "CPI", "EMPLOYMENT")}
cells = {"fomc_day": days["FOMC"], "cpi_nfp_day": days["CPI"] | days["EMPLOYMENT"], "all_event_days": days["FOMC"] | days["CPI"] | days["EMPLOYMENT"]}
rng = np.random.default_rng(3); trade_days = sorted(set(t["day"] for t in base)); out["A"] = {}
for name, ds in cells.items():
    keep = [t for t in base if t["day"] not in ds]; rem = [t for t in base if t["day"] in ds]
    n_days = len(set(t["day"] for t in rem)); k = summ(keep); r = stats(rem) if rem else dict(net=0, trades=0)
    worse = 0
    for _ in range(200):
        pick = set(rng.choice(len(trade_days), n_days, replace=False)); pd_ = {trade_days[i] for i in pick}
        pn = sum(t["net"] for t in base if t["day"] not in pd_); worse += pn < k["net"]
    adopt = r["net"] < 0 and worse >= 190 and k["pos_years"] >= 11
    out["A"][name] = dict(kept=k, removed_net=r["net"], removed_trades=r["trades"], removed_days=n_days, placebo_worse_of_200=int(worse), adopt=bool(adopt))
    print("A", name, out["A"][name], flush=True)
# B. execution stress
out["B"] = {}
for name, o in (("slip2", dict(slippage_ticks=2)), ("spread2", dict(spread_ticks=2)), ("both", dict(slippage_ticks=2, spread_ticks=2))):
    OVR.clear(); OVR.update(o); r = summ(run_v2()); r["net_retention"] = round(r["net"] / out["base"]["net"], 3); out["B"][name] = r; print("B", name, r, flush=True)
# C. gate sensitivity
out["C"] = {}
for name, o in (("daily_200", dict(daily_loss=200.0)), ("daily_off", dict(daily_loss=1e9)), ("hard_1000", dict(hard_drawdown=1000.0)), ("hard_off", dict(hard_drawdown=1e9))):
    OVR.clear(); OVR.update(o); r = summ(run_v2()); out["C"][name] = r; print("C", name, r, flush=True)
json.dump(out, open(ROOT / "reports/DPLUS_3_TRAINING.json", "w"), indent=1, default=str); print("DONE", flush=True)

"""funded_1: prop-firm rule model on the frozen training legs (research/funded_1/PROTOCOL.md)."""
import json
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
S2 = (ROOT / "scripts/staging_2_pilot.py").read_text().split('ns["trades"] = trades')[0]; n2 = {"__file__": str(ROOT / "scripts/staging_2_pilot.py")}; exec(S2, n2)
trades, NY = n2["trades"], n2["NY"]
CONF = {"L1_overnight_v2": lambda t: 1 if t["leg"] == "L1" else 0, "L2_allweather_1c": lambda t: 1 if t["leg"] == "L2" else 0,
        "L3_dplus_v2": lambda t: 1 if t["leg"] == "L3" else 0, "L3G_dplus_gapsized": lambda t: (2 if t["gap2"] else 1) if t["leg"] == "L3" else 0,
        "BookA": lambda t: 1 if t["leg"] in ("L1", "L2") else 0, "BookA_skew": lambda t: (2 if t["skew"] else 1) if t["leg"] in ("L1", "L2") else 0}
def events(mult, k):
    ev = []
    for t in trades:
        m = mult(t) * k
        if m: ev.append((t["t_in"], 0, t["worst"] * m, 0.0, t["t_out"].date())); ev.append((t["t_out"], 1, 0.0, t["net"] * m, t["t_out"].date()))
    ev.sort(key=lambda x: (x[0], x[1])); return ev
def sim(ev, floor_kind, dll, target=None, cons=None, horizon_end=None):
    """Walk events; returns dict(outcome, days, closed, best_day, n_win150, worst_day, dll_hit). Floor breach / DLL -> 'fail'; target+consistency -> 'pass'."""
    closed = hwm = 0.0; floor = -2000.0; day_pnl = {}; worst_day = 0.0; cur_day = None; cur = 0.0; days = 0
    def day_close():
        nonlocal hwm, floor, cur, worst_day
        if cur_day is None: return None
        day_pnl[cur_day] = cur; worst_day = min(worst_day, cur)
        if floor_kind == "TRAIL_EOD": hwm = max(hwm, closed); floor = min(0.0, hwm - 2000.0) if hwm < 2000 else 0.0
        if dll and cur <= -dll: return "fail_dll"
        cur = 0.0; return None
    for ts, kind, unreal, real, d in ev:
        if horizon_end is not None and ts >= horizon_end: break
        if d != cur_day:
            r = day_close()
            if r: return dict(outcome=r, days=days, closed=closed, day_pnl=day_pnl, worst_day=worst_day)
            cur_day = d; days += 1
        if kind == 0:
            if floor_kind == "TRAIL_MARK" and closed + unreal <= floor: return dict(outcome="fail_floor", days=days, closed=closed + unreal, day_pnl=day_pnl, worst_day=worst_day)
            if floor_kind == "STATIC" and closed + unreal <= -2000.0: return dict(outcome="fail_floor", days=days, closed=closed + unreal, day_pnl=day_pnl, worst_day=worst_day)
            if floor_kind == "TRAIL_EOD" and closed + unreal <= floor: return dict(outcome="fail_floor", days=days, closed=closed + unreal, day_pnl=day_pnl, worst_day=worst_day)
        else:
            closed += real; cur += real
            if floor_kind == "TRAIL_MARK":
                hwm = max(hwm, closed); floor = min(100.0, hwm - 2000.0) if hwm < 2100 else 100.0
            if closed <= floor and floor_kind != "STATIC": return dict(outcome="fail_floor", days=days, closed=closed, day_pnl=day_pnl, worst_day=worst_day)
            if floor_kind == "STATIC" and closed <= -2000.0: return dict(outcome="fail_floor", days=days, closed=closed, day_pnl=day_pnl, worst_day=worst_day)
            if target is not None and closed >= target:
                best = max(list(day_pnl.values()) + [cur]) if (day_pnl or cur) else 0.0
                if cons is None or best <= cons * closed: return dict(outcome="pass", days=days, closed=closed, day_pnl=day_pnl, worst_day=worst_day)
    r = day_close()
    return dict(outcome=r or "open", days=days, closed=closed, day_pnl=day_pnl, worst_day=worst_day)
starts = pd.date_range("2010-01-01", "2023-01-01", freq="MS", tz=NY); out = {}
EVAL = {"topstep_trailing": dict(floor="TRAIL_EOD", dll=1000.0, target=3000.0, cons=0.55), "topstep_static": dict(floor="STATIC", dll=1000.0, target=4000.0, cons=0.55),
        "tradeify_select": dict(floor="TRAIL_EOD", dll=None, target=3000.0, cons=0.40)}
FUNDED = {"static_dll1000": dict(floor="STATIC", dll=1000.0), "trail_eod_dll1000": dict(floor="TRAIL_EOD", dll=1000.0), "trail_eod_nodll": dict(floor="TRAIL_EOD", dll=None), "trail_mark_nodll": dict(floor="TRAIL_MARK", dll=None)}
for cname, mult in CONF.items():
    out[cname] = {"evaluation": {}, "funded": {}}
    for k in (1, 2, 3, 4):
        ev = events(mult, k)
        for ename, e in EVAL.items():
            res = []
            for s0 in starts:
                e0 = s0 + pd.DateOffset(months=12); sub = [x for x in ev if s0 <= x[0] < e0]
                res.append(sim(sub, e["floor"], e["dll"], e["target"], e["cons"], horizon_end=e0))
            oc = pd.Series([r["outcome"] for r in res]); dp = [r["days"] for r in res if r["outcome"] == "pass"]
            p_pass = float((oc == "pass").mean()); p_fail = float(oc.str.startswith("fail").mean())
            out[cname]["evaluation"][f"{ename}_{k}c"] = dict(p_pass=round(p_pass, 3), p_fail=round(p_fail, 3), p_open_12m=round(1 - p_pass - p_fail, 3),
                                                             median_days_to_pass=int(np.median(dp)) if dp else None, resets_per_pass=round(p_fail / p_pass, 2) if p_pass else None)
    for k in (1, 2):
        ev = events(mult, k)
        for fname, f in FUNDED.items():
            res = []
            for s0 in starts:
                e0 = s0 + pd.DateOffset(months=12); sub = [x for x in ev if s0 <= x[0] < e0]
                res.append(sim(sub, f["floor"], f["dll"], horizon_end=e0))
            oc = pd.Series([r["outcome"] for r in res]); ok = [r for r in res if r["outcome"] == "open"]
            win = [sum(1 for v in r["day_pnl"].values() if v >= 150) for r in res]; best = [max(r["day_pnl"].values()) if r["day_pnl"] else 0 for r in res]
            cons = [b / r["closed"] if r["closed"] > 0 else None for b, r in zip(best, res)]; cons = [c for c in cons if c is not None]
            out[cname]["funded"][f"{fname}_{k}c"] = dict(p_breach_floor=round(float((oc == "fail_floor").mean()), 3), p_dll_hit=round(float((oc == "fail_dll").mean()), 3),
                                                        median_net_12m=round(float(np.median([r["closed"] for r in ok])), 2) if ok else None,
                                                        median_win150_days_per_year=int(np.median(win)), p_at_least_5_win_days=round(float(np.mean([w >= 5 for w in win])), 3),
                                                        median_bestday_over_net=round(float(np.median(cons)), 2) if cons else None, p_consistency40_ok=round(float(np.mean([c <= 0.4 for c in cons])), 3) if cons else None,
                                                        worst_day=round(float(min(r["worst_day"] for r in res)), 2))
    print(cname, "eval", {k: (v["p_pass"], v["p_fail"], v["median_days_to_pass"]) for k, v in out[cname]["evaluation"].items()}, flush=True)
    print(cname, "funded", {k: (v["p_breach_floor"], v["p_dll_hit"], v["median_win150_days_per_year"], v["median_bestday_over_net"]) for k, v in out[cname]["funded"].items()}, flush=True)
json.dump(out, open(ROOT / "reports/FUNDED_1_TRAINING.json", "w"), indent=1, default=str); print("DONE", flush=True)

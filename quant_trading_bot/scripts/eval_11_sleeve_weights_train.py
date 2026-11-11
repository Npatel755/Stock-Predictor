"""eval_11 (Claude, 2026-11-10): size each sleeve by its own edge instead of equally, for the $50K Static Combine. TRAINING 2010-23 only.

PRE-DECLARED (written before any result). Book, simulator, starts and incumbent as eval_9 (SLEEVES + DEF + ENDGAME, 60.0% = 54.5 / 65.6).
Sleeve groups: CRABEL_CONT (Crabel on gap-continuation, 2 micros base), CRABEL_FADE, TRD60, MES_TRD30, BRK_E, MES_MOM, NIGHT.
Weight w_s from the FIT fold's trades (per micro, after costs, today's prices), normalised so the trade-weighted mean weight is 1:
  KELLY  w ~ mean / variance        SHARPE  w ~ mean / st.dev.        HALF  w = 0.5 + 0.5 x KELLY weight (shrunk toward equal).
Size per trade = min(clip(round(m x w_s), 1, 6) x base, floor($900 / stop risk)), m = the incumbent's multiplier (3; 2 at <= -$500;
1 at <= -$1,000; 5 late when short). $400 daily stop when no trade is above its base, else $700 (as before).
Protocol: fit weights on fold A trades (exits before 2017) and run on fold-B starts; fit on B, run on A. Pick on A / pick on B among the
3 cells by in-fold pass share. ADOPT only if both out-of-fold halves >= incumbent's same half + 1.0 point.
"""
import json
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/eval_9_optimal_sizing_train.py").read_text(encoding="utf-8").split("\nout = {}\n")[0]
E9 = {"__name__": "e11", "__file__": str(ROOT / "scripts/eval_9_optimal_sizing_train.py")}; exec(src, E9)
pl, A, B, DEF_END, SLV, variant = (E9[k] for k in ("pl", "A", "B", "DEF_END", "SLV", "variant"))
E5 = E9["E"]; NIGHTS, NIGHT_RISK = E5["NIGHTS"], E5["NIGHT_RISK"]
FA_END = pd.Timestamp("2017-01-01").date()


def group(name, n):
    if "CRABEL" in name: return "CRABEL_CONT" if n >= 2 else "CRABEL_FADE"
    for g in ("TRD60", "MES_TRD30", "BRK_E", "MES_MOM"):
        if g in name: return g
    raise ValueError(name)


d = pd.concat([variant("A")] + SLV, ignore_index=True)
r = pl.route(d[d.risk_today <= 300.0]).copy(); r["per_micro"] = r.net_today / r.n_contracts
r["g"] = [group(s, n) for s, n in zip(r.sleeve, r.n_contracts)]
t = pd.concat([r[["tin", "tout", "per_micro", "mae_per_micro", "n_contracts", "risk_today", "g"]],
               NIGHTS.assign(n_contracts=1.0, risk_today=NIGHT_RISK, g="NIGHT")[["tin", "tout", "per_micro", "mae_per_micro", "n_contracts", "risk_today", "g"]]],
              ignore_index=True)
t["day"] = t.tout.dt.date; t = t.sort_values("tin"); GROUPS = sorted(t.g.unique()); t["gi"] = t.g.map({g: i for i, g in enumerate(GROUPS)})
BY = {k: (g.per_micro.to_numpy(), g.mae_per_micro.to_numpy(), g.n_contracts.to_numpy(), g.risk_today.to_numpy(), g.gi.to_numpy()) for k, g in t.groupby("day")}
TD = sorted(BY); TIX = pd.to_datetime(pd.Series(TD).astype(str)).to_numpy()


def weights(fold, kind):
    f = t[(t.day < FA_END) if fold == "A" else (t.day >= FA_END)]
    st = f.groupby("g").per_micro.agg(["mean", "std", "count"])
    raw = st["mean"] / (st["std"] ** 2) if kind in ("KELLY", "HALF") else st["mean"] / st["std"]
    w = raw / float((raw * st["count"]).sum() / st["count"].sum())
    if kind == "HALF": w = 0.5 + 0.5 * w
    return np.array([float(w.get(g, 1.0)) for g in GROUPS]), st.round(2).to_dict()


def evaluate(wv, starts, rule=DEF_END):
    res = []
    for s in starts:
        end = (pd.Timestamp(s) + pd.Timedelta(days=90)).date(); i = int(np.searchsorted(TIX, np.datetime64(pd.Timestamp(s))))
        bal = 0.0; best = 0.0; out_ = "timeout"
        for dd in TD[i:]:
            if dd >= end: break
            m = rule(bal, (dd - s).days, max(4000.0, best / 0.55), int(np.busday_count(dd, end)))
            per, mae, n, risk, gi = BY[dd]
            q = np.minimum(np.clip(np.round(m * wv[gi]), 1, 6) * n, np.floor(900.0 / risk)); stop = 400.0 if np.all(q <= n) else 700.0
            day = 0.0; w = 0.0
            for j in range(len(per)):
                if q[j] < 1: continue
                if day <= -stop or day <= -1000.0: break
                w = min(w, day + mae[j] * q[j])
                if day + mae[j] * q[j] <= -1000.0: day = -1000.0; break
                day += per[j] * q[j]
            p = max(day, -1000.0)
            if bal + min(w, p) <= -2000.0: out_ = "fail"; break
            bal += p; best = max(best, p)
            if bal >= max(4000.0, best / 0.55): out_ = "pass"; break
        res.append(out_)
    x = pd.Series(res)
    return dict(pass_=round(100 * float((x == "pass").mean()), 1), fail=round(100 * float((x == "fail").mean()), 1),
                timeout=round(100 * float((x == "timeout").mean()), 1), n=len(x))


ones = np.ones(len(GROUPS)); out = {"groups": GROUPS}
inc = out["incumbent"] = dict(h1=evaluate(ones, A), h2=evaluate(ones, B)); print("incumbent (equal weights)", inc, flush=True)
assert abs(inc["h1"]["pass_"] - 54.5) <= 0.1 and abs(inc["h2"]["pass_"] - 65.6) <= 0.1, "does not reproduce the incumbent"
cells = {}
for kind in ("KELLY", "SHARPE", "HALF"):
    wA, sA = weights("A", kind); wB, sB = weights("B", kind)
    cells[kind] = dict(w_fit_A=dict(zip(GROUPS, wA.round(2))), w_fit_B=dict(zip(GROUPS, wB.round(2))), stats_A=sA, stats_B=sB,
                       insample_A=evaluate(wA, A), oof_B=evaluate(wA, B), insample_B=evaluate(wB, B), oof_A=evaluate(wB, A))
    print(kind, {k: v for k, v in cells[kind].items() if not k.startswith("stats")}, flush=True)
pA = max(cells, key=lambda k: cells[k]["insample_A"]["pass_"]); pB = max(cells, key=lambda k: cells[k]["insample_B"]["pass_"])
onB, onA = cells[pA]["oof_B"], cells[pB]["oof_A"]
out["cells"] = cells
out["result"] = dict(picked_on_A=pA, picked_on_B=pB, oof_h1=onA, oof_h2=onB,
                     oof_all=round((onA["pass_"] * onA["n"] + onB["pass_"] * onB["n"]) / (onA["n"] + onB["n"]), 1),
                     adopt=bool(onA["pass_"] >= inc["h1"]["pass_"] + 1.0 and onB["pass_"] >= inc["h2"]["pass_"] + 1.0))
print("result", out["result"], flush=True)
(ROOT / "reports/EVAL_11_SLEEVE_WEIGHTS_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))

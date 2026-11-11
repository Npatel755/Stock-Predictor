"""eval_33 (Claude, 2026-11-11): re-tune SIZE and DAY RULES on the STRICT book (one position at a time), v2 semantics, filled 2019 data.
TRAINING 2010-23 only.

Why (written before results): STRICT (eval_30-32) fails ~19% instead of ~26% and times out more (28% / 19%). The ladder, daily stops and
risk cap were all tuned on the overlapping book under the look-ahead simulator; with a thinner left tail the best size is likely larger or
the endgame earlier. Base = STRICT + DEF_END = 54.4 / 61.1.
PRE-DECLARED cells (one family, 2-fold):
  ladders  INC (DEF_END) | K3 | NOLATE | K4BASE (k4 top) | K4LAD (k4; k3 <= -300; k2 <= -700; k1 <= -1,200; late k5) | TIGHT (k2 <= -300,
           k1 <= -700) | LOOSE (k2 <= -800, k1 <= -1,300) | LATE45 | LATE6 (late k6) | K2BASE (k2 top, late k5)
  day rules on INC: LOCKCAP (eval_25: no new entry once passed intraday or once the day >= max($2,200, best day)) | STOP5_10 (daily stop
           $500 at base size / $1,000 above, was $400 / $700) | STOP3_6 ($300 / $600) | CAP1200 (per-trade risk cap $1,200, was $900)
2-fold: pick the best cell on 2010-16 starts and report it on 2017-23, and vice versa. ADOPT only if both out-of-fold halves >= INC + 1.0.
If the two halves pick the same cell and it clears the bar, that cell is the new rule.
"""
import os, json
os.environ["TRAIN_MINI_UNTIL"] = "2019-05-06"
import numpy as np, pandas as pd
from pathlib import Path
import eval_harness as eh

ROOT = Path(__file__).resolve().parents[1]
H = eh.Harness()
BOOK = H.build_book(H.PRE, strict=True)
f = BOOK[H.COLS].assign(noise=False).sort_values(["tin", "tout", "per_micro"], kind="stable").reset_index(drop=True)
PD = H._per_day(f); TD = sorted(PD); TIX = pd.to_datetime(pd.Series(TD).astype(str)).to_numpy()


def sim(x, k, bal=0.0, best=0.0, lock=False, stop_lo=400.0, stop_hi=700.0, cap_usd=900.0):
    a, b, per, mae, n, risk, nz = x
    mae = np.minimum(mae, per); q = np.minimum(k * n, np.floor(cap_usd / risk))
    stop = stop_lo if np.all(q <= n) else stop_hi; acc = []; w = 0.0; dll = False
    for j in range(len(per)):
        if q[j] < 1: continue
        done = [i for i in acc if b[i] < a[j] or (b[i] == a[j] and a[i] < a[j])]
        realised = sum(per[i] * q[i] for i in done); opn = sum(min(0.0, mae[i] * q[i]) for i in acc if i not in done)
        if realised <= -stop or realised <= -1000.0: break
        if lock and (bal + realised >= max(4000.0, max(best, realised) / 0.55) or realised >= max(2200.0, best)): break
        worst = realised + mae[j] * q[j] + opn; w = min(w, worst)
        if worst <= -1000.0: dll = True; break
        acc.append(j)
    p = -1000.0 if dll else max(sum(per[i] * q[i] for i in acc), -1000.0)
    return p, min(w, p)


def ladder(top=3, k3=None, k2=-500.0, k1=-1000.0, late=5, late_day=60):
    def r(bal, day, tgt):
        if late and day >= late_day and bal < tgt - 1000.0 and bal > -500.0: return late
        if bal <= k1: return 1
        if bal <= k2: return 2
        if k3 is not None and bal <= k3: return 3
        return top
    return r


RULES = {"INC": ladder(), "K3": lambda b, d, t: 3, "NOLATE": ladder(late=None), "K4BASE": ladder(top=4),
         "K4LAD": ladder(top=4, k3=-300.0, k2=-700.0, k1=-1200.0), "TIGHT": ladder(k2=-300.0, k1=-700.0), "LOOSE": ladder(k2=-800.0, k1=-1300.0),
         "LATE45": ladder(late_day=45), "LATE6": ladder(late=6), "K2BASE": ladder(top=2, k2=-1e9)}
DAYRULES = {"LOCKCAP": dict(lock=True), "STOP5_10": dict(stop_lo=500.0, stop_hi=1000.0), "STOP3_6": dict(stop_lo=300.0, stop_hi=600.0),
            "CAP1200": dict(cap_usd=1200.0)}
CACHE = {}


def day(d, k, bal, best, kw):
    if kw.get("lock"): return sim(PD[d], float(k), bal, best, **kw)
    key = (d, k, tuple(sorted(kw.items())))
    if key not in CACHE: CACHE[key] = sim(PD[d], float(k), **kw)
    return CACHE[key]


def evaluate(starts, rule, kw):
    res = []
    for s in starts:
        end = (pd.Timestamp(s) + pd.Timedelta(days=90)).date(); i = int(np.searchsorted(TIX, np.datetime64(pd.Timestamp(s))))
        bal = 0.0; best = 0.0; o = "timeout"
        for d in TD[i:]:
            if d >= end: break
            k = rule(bal, (d - s).days, max(4000.0, best / 0.55)); p, w = day(d, k, bal, best, kw)
            if bal + min(w, p) <= -2000.0: o = "fail"; break
            bal += p; best = max(best, p)
            if bal >= max(4000.0, best / 0.55): o = "pass"; break
        res.append(o)
    x = pd.Series(res)
    return dict(pass_=round(100 * float((x == "pass").mean()), 1), fail=round(100 * float((x == "fail").mean()), 1),
                timeout=round(100 * float((x == "timeout").mean()), 1), n=len(x))


out = {"cells": {}}
for nm, r in RULES.items():
    out["cells"][nm] = dict(h1=evaluate(H.A, r, {}), h2=evaluate(H.B, r, {})); print(nm, out["cells"][nm], flush=True)
assert (out["cells"]["INC"]["h1"]["pass_"], out["cells"]["INC"]["h2"]["pass_"]) == (54.4, 61.1), "STRICT base does not reproduce eval_30"
for nm, kw in DAYRULES.items():
    out["cells"][nm] = dict(h1=evaluate(H.A, RULES["INC"], kw), h2=evaluate(H.B, RULES["INC"], kw)); print(nm, out["cells"][nm], flush=True)
C = out["cells"]; I = (C["INC"]["h1"]["pass_"], C["INC"]["h2"]["pass_"])
pA = max(C, key=lambda c: C[c]["h1"]["pass_"]); pB = max(C, key=lambda c: C[c]["h2"]["pass_"])
oA, oB = C[pB]["h1"]["pass_"], C[pA]["h2"]["pass_"]
out["result"] = dict(pick_h1=pA, pick_h2=pB, oof_h1=oA, oof_h2=oB, inc=I, adopt=bool(oA >= I[0] + 1.0 and oB >= I[1] + 1.0),
                     same_pick=pA == pB)
print("result", out["result"], flush=True)
(ROOT / "reports/EVAL_33_STRICT_SIZING_RULES_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
print("saved", flush=True)

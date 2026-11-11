"""eval_29 (Claude, 2026-11-11): re-check the evaluation size ladder under CORRECTED day semantics (sim_day_v2) and the filled 2019 data.
TRAINING 2010-23 only.

Why: eval_28 showed the v1 day simulator (eval_5 -> eval_9 -> harness) had a look-ahead (an open trade's final P&L could block the next
entry) and an unstable tie order; corrected, the eval_8 plan passes 49.7 / 59.4 (filled data) instead of 54.5 / 65.6, and fails 26% not
20%. The ladder was selected under v1, so re-check it with a small PRE-DECLARED set (before any result):
  INC      eval_8 DEF_END: k3; k2 at bal <= -500; k1 at <= -1,000; k5 from day 60 if > $1,000 short and bal > -500
  K3       flat k3
  NOLATE   INC without the late k5
  K4BASE   k4 instead of k3 at the top of INC's ladder
  TIGHT    k2 at <= -300, k1 at <= -700 (else INC)
  LOOSE    k2 at <= -800, k1 at <= -1,300 (else INC)
  LATE45   late k5 from day 45 (else INC)
  LATE4    late k4 instead of k5 (else INC)
  K2BASE   k2 at the top (k1 at <= -1,000; late k5 as INC)
2-fold: pick the best cell on 2010-16 starts and report it on 2017-23, and vice versa. ADOPT a change only if both out-of-fold halves >=
INC's same half + 1.0. Also (information): the attempt budget under v2 (sequential purchases, up to 5) for the adopted rule or INC.
"""
import os, json
os.environ["TRAIN_MINI_UNTIL"] = "2019-05-06"
import numpy as np, pandas as pd
from pathlib import Path
import eval_harness as eh

ROOT = Path(__file__).resolve().parents[1]
H = eh.Harness()


def ladder(top=3, k2=-500.0, k1=-1000.0, late=5, late_day=60):
    def r(bal, day, tgt, s):
        if late and day >= late_day and bal < tgt - 1000.0 and bal > -500.0: return late
        return 1 if bal <= k1 else (2 if bal <= k2 else top)
    return r


CELLS = {"INC": ladder(), "K3": lambda b, d, t, s: 3, "NOLATE": ladder(late=None), "K4BASE": ladder(top=4), "TIGHT": ladder(k2=-300.0, k1=-700.0),
         "LOOSE": ladder(k2=-800.0, k1=-1300.0), "LATE45": ladder(late_day=45), "LATE4": ladder(late=4), "K2BASE": ladder(top=2, k2=-1e9)}
out = {"cells": {}}
for nm, f in CELLS.items():
    out["cells"][nm] = H.pass_rate(rule=f, v2=True, ks=(1, 2, 3, 4, 5)); print(nm, out["cells"][nm], flush=True)
C = out["cells"]
pA = max(C, key=lambda c: C[c]["h1"]["pass_"]); pB = max(C, key=lambda c: C[c]["h2"]["pass_"])
oA, oB = C[pB]["h1"]["pass_"], C[pA]["h2"]["pass_"]
adopt = bool(pA == pB and pA != "INC" and oA >= C["INC"]["h1"]["pass_"] + 1.0 and oB >= C["INC"]["h2"]["pass_"] + 1.0) or bool(
    pA != pB and oA >= C["INC"]["h1"]["pass_"] + 1.0 and oB >= C["INC"]["h2"]["pass_"] + 1.0)
out["result"] = dict(pick_h1=pA, pick_h2=pB, oof_h1=oA, oof_h2=oB, inc=dict(h1=C["INC"]["h1"]["pass_"], h2=C["INC"]["h2"]["pass_"]), adopt=adopt)
print("result", out["result"], flush=True)

# ---------------- attempt budget under v2 (INC unless a change was adopted and both halves picked the same cell)
rule = CELLS[pA] if (adopt and pA == pB) else CELLS["INC"]
frame = H.BOOK[H.COLS].assign(noise=False).sort_values(["tin", "tout", "per_micro"], kind="stable").reset_index(drop=True)
PD = H._per_day(frame); TD = sorted(PD); TIX = pd.to_datetime(pd.Series(TD).astype(str)).to_numpy()
DAY = {k: {d: H.sim_day_v2(PD[d], float(k)) for d in TD} for k in (1, 2, 3, 4, 5)}
LAST = TD[-1]; SESS = list(H.SESS); SIX = np.array(SESS, dtype=object)


def run(start):
    end = (pd.Timestamp(start) + pd.Timedelta(days=90)).date(); i = int(np.searchsorted(TIX, np.datetime64(pd.Timestamp(start))))
    bal = 0.0; best = 0.0
    for d in TD[i:]:
        if d >= end: return "timeout", end
        k = rule(bal, (d - start).days, max(4000.0, best / 0.55), 0); p, w = DAY[k][d]
        if bal + min(w, p) <= -2000.0: return "fail", d
        bal += p; best = max(best, p)
        if bal >= max(4000.0, best / 0.55): return "pass", d
    return "timeout", end


CACHE = {}
def plain(s):
    if s not in CACHE: CACHE[s] = run(s)
    return CACHE[s]


chk = {h: round(100 * float(np.mean([plain(s)[0] == "pass" for s in st])), 1) for h, st in (("h1", H.A), ("h2", H.B))}
print("budget rule single-attempt check", chk, flush=True)
rows = []
for s0 in [s for s in SESS if (pd.Timestamp(s) + pd.Timedelta(days=450)).date() <= LAST and s >= H.A[0]]:
    s = s0; n = 0; at = None; days = None
    while s is not None and n < 5:
        n += 1; o, e = plain(s)
        if o == "pass": at = n; days = (e - s0).days; break
        j = int(np.searchsorted(SIX, e, side="right")); s = SESS[j] if j < len(SESS) else None
    rows.append(dict(h1=s0 < eh.H1_END, att=at, buys=n, days=days))
R = pd.DataFrame(rows)


def table(x):
    d = {f"by_{k}": round(100 * float(((x.att.notna()) & (x.att <= k)).mean()), 1) for k in range(1, 6)}
    dd = x.days.dropna()
    d.update(n=len(x), mean_purchases=round(float(x.buys.mean()), 2), mean_spend_usd=round(149 * float(x.buys.mean()), 0),
             median_days=float(dd.median()), p90_days=float(dd.quantile(0.9)))
    return d


out["budget_v2"] = dict(rule=pA if (adopt and pA == pB) else "INC", single=chk, h1=table(R[R.h1]), h2=table(R[~R.h1]), all=table(R))
print("budget", out["budget_v2"], flush=True)
(ROOT / "reports/EVAL_29_LADDER_RECHECK_V2_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))

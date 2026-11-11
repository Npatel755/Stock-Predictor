"""eval_15 (Claude, 2026-11-11): does waiting after a failed attempt raise the chance that the NEXT attempt passes? TRAINING 2010-23.

Motivation (bookx_1): 702 failed starts land on only 117 distinct days (2020, 2023, 2011, 2015 clusters) - fails are regime-clustered,
so an attempt bought right after a fail may start inside the same bad stretch. eval_3 rejected market-state start filters (they flipped
between halves); this tests only a fixed waiting period, which needs no market signal.

PRE-DECLARED (before results). eval_8 plan (DEF_END) on the harness book; first attempt starts every session 2010-06..2023-09.
  If attempt 1 FAILS, attempt 2 starts W sessions after the fail day, W in {0 (next session), 10, 20, 40}. After a TIMEOUT attempt 2
  starts the next session in every cell (a timeout is not a regime signal).
  Metrics: P(pass within two attempts); P(attempt 2 passes | attempt 1 failed); median calendar days from first start to pass.
  2-fold: pick W on 2010-16 first starts, report on 2017-23, and vice versa. ADOPT a wait only if both out-of-fold halves of
  P(pass within two) >= W=0's same half + 1.0 point. Attempts that would run past the data end count as not passed (same for all W).
"""
import json
import numpy as np, pandas as pd
from pathlib import Path
import eval_harness as eh

ROOT = Path(__file__).resolve().parents[1]
H = eh.Harness(); DEF = H.DEF_END
PD = H._per_day(H.BOOK[H.COLS].assign(noise=False)); TD = sorted(PD); TIX = pd.to_datetime(pd.Series(TD).astype(str)).to_numpy()
DAY = {k: {d: H.sim_day(PD[d], float(k)) for d in TD} for k in (1, 2, 3, 5)}
ALL = sorted(set(H.SESS) | set(d for d in TD if d.weekday() < 5)); AIX = {d: i for i, d in enumerate(ALL)}
LAST = TD[-1]


def attempt(start):
    end = (pd.Timestamp(start) + pd.Timedelta(days=90)).date()
    if end > LAST: return "nodata", None
    i = int(np.searchsorted(TIX, np.datetime64(pd.Timestamp(start)))); bal = 0.0; best = 0.0
    for d in TD[i:]:
        if d >= end: return "timeout", end
        k = DEF(bal, (d - start).days, max(4000.0, best / 0.55), 0); p, w = DAY[k][d]
        if bal + min(w, p) <= -2000.0: return "fail", d
        bal += p; best = max(best, p)
        if bal >= max(4000.0, best / 0.55): return "pass", d
    return "timeout", end


def after(d, n):
    j = int(np.searchsorted(np.array(ALL, dtype=object), d, side="right")) + n
    return ALL[j] if j < len(ALL) else None


CACHE = {}
def att(s):
    if s not in CACHE: CACHE[s] = attempt(s)
    return CACHE[s]


out = {"cells": {}}
for W in (0, 10, 20, 40):
    c = {}
    for nm, st in (("h1", H.A), ("h2", H.B)):
        two = []; cond = []; days = []
        for s in st:
            o, e = att(s)
            if o == "pass": two.append(True); days.append((e - s).days); continue
            if o == "nodata": two.append(False); continue
            s2 = after(e, W if o == "fail" else 0)
            o2, e2 = att(s2) if s2 else ("nodata", None)
            two.append(o2 == "pass")
            if o2 == "pass": days.append((e2 - s).days)
            if o == "fail": cond.append(o2 == "pass")
        c[nm] = dict(pass_within_two=round(100 * float(np.mean(two)), 1), attempt2_pass_after_fail=round(100 * float(np.mean(cond)), 1),
                     n_fail_first=len(cond), median_days_to_pass=float(np.median(days)))
    out["cells"][W] = c; print("W", W, c, flush=True)
C = out["cells"]; pA = max(C, key=lambda w: C[w]["h1"]["pass_within_two"]); pB = max(C, key=lambda w: C[w]["h2"]["pass_within_two"])
out["result"] = dict(picked_on_h1=pA, picked_on_h2=pB, oof_h1=C[pB]["h1"]["pass_within_two"], oof_h2=C[pA]["h2"]["pass_within_two"],
                     adopt=bool(C[pB]["h1"]["pass_within_two"] >= C[0]["h1"]["pass_within_two"] + 1.0 and
                                C[pA]["h2"]["pass_within_two"] >= C[0]["h2"]["pass_within_two"] + 1.0))
print("result", out["result"], flush=True)
(ROOT / "reports/EVAL_15_COOLING_OFF_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))

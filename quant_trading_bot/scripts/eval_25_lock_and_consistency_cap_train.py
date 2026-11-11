"""eval_25 (Claude, 2026-11-11): two parameter-free in-day rules that follow from the Combine's own rules. TRAINING 2010-23 only.

Why (written before results): the simulator trades every signal of a day and checks the target only at the close. Two things a trader
would do are not modelled:
  LOCK    no new entries once the account has passed intraday: bal + day's realised P&L >= max(4000, max(best, day) / 0.55).
          Per path this can only turn a later give-back into a pass.
  CAPDYN  no new entries once the day's realised P&L >= max(2200, best) = 0.55 x the current target, i.e. the most a day can make without
          raising the target under the 55% consistency rule. Past it, a win raises the target by 1/0.55 = 1.82x the win (distance to
          target +0.82x) and a loss lowers the balance, so every further trade that day lengthens the way to the target.
eval_9 tested only a FIXED $1,500 / $2,200 daily profit stop (PSTOP 2200: +1.1 out-of-fold, below the bar); neither rule above was tested.

PRE-DECLARED (before any result). eval_8 plan (DEF_END) on the harness book, harness day logic (sequential book trades, $400 / $700 daily
stop, DLL, floor on MAE). Cells: INC (must reproduce 54.5 / 65.6), LOCK, CAPDYN, BOTH. The entry check uses only trades CLOSED before the
next entry (the trade that crosses a threshold is not cut short). PRIMARY = BOTH vs INC: ADOPT if both halves >= INC + 1.0. No parameters
are chosen, so there is no 2-fold pick; LOCK and CAPDYN alone are reported for attribution.
"""
import json
import numpy as np, pandas as pd
from pathlib import Path
import eval_harness as eh

ROOT = Path(__file__).resolve().parents[1]
H = eh.Harness(); DEF = H.DEF_END
PD = H._per_day(H.BOOK[H.COLS].assign(noise=False)); TD = sorted(PD); TIX = pd.to_datetime(pd.Series(TD).astype(str)).to_numpy()


def sim_day(x, k, bal, best, lock, cap):
    a, b, per, mae, n, risk, nz = x
    q = np.minimum(k * n, np.floor(900.0 / risk)); stop = 400.0 if np.all(q <= n) else 700.0
    acc = []; w = 0.0; dll = False
    for j in range(len(per)):
        if q[j] < 1: continue
        realised = sum(per[i] * q[i] for i in acc if b[i] <= a[j]); opn = sum(min(0.0, mae[i] * q[i]) for i in acc if b[i] > a[j])
        settled = sum(per[i] * q[i] for i in acc)          # harness semantics: book trades are sequential
        if settled <= -stop or settled <= -1000.0: break
        if lock and bal + realised >= max(4000.0, max(best, realised) / 0.55): break
        if cap and realised >= max(2200.0, best): break
        worst = settled + mae[j] * q[j]
        w = min(w, worst)
        if worst <= -1000.0: dll = True; break
        acc.append(j)
    p = -1000.0 if dll else max(sum(per[i] * q[i] for i in acc), -1000.0)
    return p, w


def evaluate(starts, lock, cap):
    res = []; days = []
    for s in starts:
        end = (pd.Timestamp(s) + pd.Timedelta(days=90)).date(); i = int(np.searchsorted(TIX, np.datetime64(pd.Timestamp(s))))
        bal = 0.0; best = 0.0; out = "timeout"
        for d in TD[i:]:
            if d >= end: break
            k = DEF(bal, (d - s).days, max(4000.0, best / 0.55), 0); p, w = sim_day(PD[d], float(k), bal, best, lock, cap)
            if bal + min(w, p) <= -2000.0: out = "fail"; break
            bal += p; best = max(best, p)
            if bal >= max(4000.0, best / 0.55): out = "pass"; days.append((d - s).days); break
        res.append(out)
    x = pd.Series(res)
    return dict(pass_=round(100 * float((x == "pass").mean()), 1), fail=round(100 * float((x == "fail").mean()), 1),
                timeout=round(100 * float((x == "timeout").mean()), 1), n=len(x), median_days=float(np.median(days)) if days else None)


out = {}
for nm, lk, cp in (("INC", False, False), ("LOCK", True, False), ("CAPDYN", False, True), ("BOTH", True, True)):
    out[nm] = dict(h1=evaluate(H.A, lk, cp), h2=evaluate(H.B, lk, cp)); print(nm, out[nm], flush=True)
    if nm == "INC": assert out[nm]["h1"]["pass_"] == 54.5 and out[nm]["h2"]["pass_"] == 65.6, "does not reproduce the incumbent"
I, B = out["INC"], out["BOTH"]
out["result"] = dict(both_h1=B["h1"]["pass_"], both_h2=B["h2"]["pass_"], inc_h1=I["h1"]["pass_"], inc_h2=I["h2"]["pass_"],
                     adopt=bool(B["h1"]["pass_"] >= I["h1"]["pass_"] + 1.0 and B["h2"]["pass_"] >= I["h2"]["pass_"] + 1.0))
print("result", out["result"], flush=True)
(ROOT / "reports/EVAL_25_LOCK_CONSISTENCY_CAP_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))

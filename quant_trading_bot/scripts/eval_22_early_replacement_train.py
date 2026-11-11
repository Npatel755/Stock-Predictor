"""eval_22 (Claude, 2026-11-11): buy the second attempt EARLY, when the first is nearly dead, instead of after it fails or expires.
TRAINING 2010-23 only. eval_8 plan (DEF_END) on the harness book.

Why (written before results): eval_14 / eval_15 showed the lever is a second attempt (~82% within two) and that a fail does not predict
the next attempt. But a sequential second attempt only starts when the first FAILS or TIMES OUT (up to day 90), and bookx_1 / eval_20 show
the dead time: fails come from slow bleeds at 1x near -$1,850, and 19% of attempts time out. Buying the next attempt as soon as the first is
unlikely to pass gets the second attempt running sooner with the same purchase budget. The first account keeps trading (it is paid for);
same-direction trading across own accounts is allowed by Topstep, and this is not "account stacking" (no aggressive switching).

PRE-DECLARED (before any result). Budget = at most 2 purchases. First start = every session 2010-06..2023-06 whose first start + 180 days
falls inside the data (both policies judged on the same starts).
  SEQ (baseline): attempt 2 starts the session after attempt 1 fails or times out (none if attempt 1 passes).
  Early triggers (attempt 2 starts the session after the FIRST of: the trigger firing at a session close, or attempt 1 ending):
    T_DEAD   attempt-1 balance <= -$1,500 at a close
    T_LATE   calendar day >= 60 and attempt-1 balance < +$1,500
    T_BOTH   either of the two
  PRIMARY metric: P(at least one pass within 120 calendar days of the first purchase). Also reported: within 90 and 180 days, purchases
  used, "wasted" second purchases (attempt 1 passed after attempt 2 was bought), and P(attempt 1 passes | trigger fired).
  2-fold: pick the trigger on 2010-16 first starts, report on 2017-23, and vice versa; ADOPT only if both out-of-fold halves of the
  primary metric are >= SEQ's same half + 1.0 point.
"""
import json
import numpy as np, pandas as pd
from pathlib import Path
import eval_harness as eh

ROOT = Path(__file__).resolve().parents[1]
H = eh.Harness(); DEF = H.DEF_END
PD = H._per_day(H.BOOK[H.COLS].assign(noise=False)); TD = sorted(PD); TIX = pd.to_datetime(pd.Series(TD).astype(str)).to_numpy()
DAY = {k: {d: H.sim_day(PD[d], float(k)) for d in TD} for k in (1, 2, 3, 5)}
LAST = TD[-1]; SESS = sorted(set(H.SESS) | set(d for d in TD if d.weekday() < 5)); SIX = np.array(SESS, dtype=object)
TRIG = {"T_DEAD": lambda bal, day: bal <= -1500.0, "T_LATE": lambda bal, day: day >= 60 and bal < 1500.0,
        "T_BOTH": lambda bal, day: bal <= -1500.0 or (day >= 60 and bal < 1500.0)}


def run(start, trig=None):
    """-> outcome, end date, first trigger date (session close) or None"""
    end = (pd.Timestamp(start) + pd.Timedelta(days=90)).date(); i = int(np.searchsorted(TIX, np.datetime64(pd.Timestamp(start))))
    bal = 0.0; best = 0.0; fired = None
    for d in TD[i:]:
        if d >= end: return "timeout", end, fired
        k = DEF(bal, (d - start).days, max(4000.0, best / 0.55), 0); p, w = DAY[k][d]
        if bal + min(w, p) <= -2000.0: return "fail", d, fired
        bal += p; best = max(best, p)
        if bal >= max(4000.0, best / 0.55): return "pass", d, fired
        if fired is None and trig is not None and trig(bal, (d - start).days): fired = d
    return "timeout", end, fired


def nxt(d):
    j = int(np.searchsorted(SIX, d, side="right")); return SESS[j] if j < len(SESS) else None


CACHE = {}
def plain(s):
    if s not in CACHE: CACHE[s] = run(s)
    return CACHE[s]


firsts = [s for s in H.SESS if (pd.Timestamp(s) + pd.Timedelta(days=180)).date() <= LAST]
h1 = np.array([s < eh.H1_END for s in firsts])


def policy(name):
    rows = []
    for s in firsts:
        if name == "SEQ": o1, e1, f = plain(s)
        else: o1, e1, f = run(s, TRIG[name])
        when = e1 if (f is None or f >= e1) else f
        p_days = [(e1 - s).days] if o1 == "pass" else []
        bought2 = o1 != "pass" or (f is not None and f < e1)
        wasted = o1 == "pass" and bought2
        if bought2:
            s2 = nxt(when)
            if s2 is not None:
                o2, e2, _ = plain(s2)
                if o2 == "pass": p_days.append((e2 - s).days)
        first = min(p_days) if p_days else None
        rows.append(dict(w90=first is not None and first <= 90, w120=first is not None and first <= 120, w180=first is not None and first <= 180,
                         buys=1 + int(bought2), wasted=wasted, fired=f is not None and f < e1, a1_pass=o1 == "pass"))
    r = pd.DataFrame(rows)
    def half(m):
        x = r[m]; fx = x[x.fired]
        return dict(w90=round(100 * x.w90.mean(), 1), w120=round(100 * x.w120.mean(), 1), w180=round(100 * x.w180.mean(), 1),
                    purchases=round(float(x.buys.mean()), 2), wasted_2nd=round(100 * x.wasted.mean(), 1),
                    trigger_rate=round(100 * x.fired.mean(), 1), a1_pass_given_trigger=round(100 * fx.a1_pass.mean(), 1) if len(fx) else None)
    return dict(h1=half(h1), h2=half(~h1), n=len(r))


out = {"cells": {}}
for nm in ("SEQ", "T_DEAD", "T_LATE", "T_BOTH"):
    out["cells"][nm] = policy(nm); print(nm, out["cells"][nm], flush=True)
C = out["cells"]; cand = ["T_DEAD", "T_LATE", "T_BOTH"]
pA = max(cand, key=lambda k: C[k]["h1"]["w120"]); pB = max(cand, key=lambda k: C[k]["h2"]["w120"])
oA, oB = C[pB]["h1"]["w120"], C[pA]["h2"]["w120"]
out["result"] = dict(pick_h1=pA, pick_h2=pB, oof_h1=oA, oof_h2=oB, seq=dict(h1=C["SEQ"]["h1"]["w120"], h2=C["SEQ"]["h2"]["w120"]),
                     adopt=bool(oA >= C["SEQ"]["h1"]["w120"] + 1.0 and oB >= C["SEQ"]["h2"]["w120"] + 1.0))
print("result", out["result"], flush=True)
(ROOT / "reports/EVAL_22_EARLY_REPLACEMENT_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))

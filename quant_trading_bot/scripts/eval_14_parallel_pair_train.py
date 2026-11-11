"""eval_14 (Claude, 2026-11-11): two Static Combines bought the same day vs one, with the eval_8 plan. TRAINING 2010-23 only.

Decision support, not a strategy change. Nick's constraint is "pass within the 90-day limit"; the levers left after eval_9..13 are more
attempts. eval_6 measured parallel pairs on the OLD base book (k2 + k5: 60.1% at least one pass vs 53.4% single); eval_4 measured two
sequential attempts (~78% within two). This re-measures both for the eval_8 plan (incumbent single attempt 60.0% = 54.5 / 65.6).

PRE-DECLARED (before results). Same harness simulator (scripts/eval_harness.py), same book, same starts.
  Account 1 always runs the incumbent rule DEF_END (k3; k2 <= -$500; k1 <= -$1,000; k5 from day 60 if > $1,000 short and above -$500).
  Account 2 (same trades, same direction - Topstep allows same-direction trading across own accounts; opposite positions are prohibited):
    K2 fixed k2 | K4 fixed k4 | K5 fixed k5 | AGG ladder k5; k3 <= -$500; k1 <= -$1,000 (no endgame).
  Metric: P(at least one of the two passes within 90 days of the shared start). Both purchases are spent either way.
  Protocol: pick the account-2 rule on 2010-16 starts, report on 2017-23, and vice versa (2-fold); report the out-of-fold number.
  Comparators reported: one attempt (incumbent); two SEQUENTIAL attempts (attempt 2 bought the next session after attempt 1 fails or
  times out; pass within 180 days of the first start).
Caution: Topstep prohibits "account stacking" (repeatedly trading aggressively, hitting the limit and switching accounts). A deliberately
aggressive second account is close to that line; the K2 / K4 cells are the defensible ones. Purchases are capped at 5 per trader in total.
"""
import json
import numpy as np, pandas as pd
from pathlib import Path
import eval_harness as eh

ROOT = Path(__file__).resolve().parents[1]
H = eh.Harness(); DEF = H.DEF_END
PD = H._per_day(H.BOOK[H.COLS].assign(noise=False)); TD = sorted(PD); TIX = pd.to_datetime(pd.Series(TD).astype(str)).to_numpy()
DAY = {k: {d: H.sim_day(PD[d], float(k)) for d in TD} for k in (1, 2, 3, 4, 5)}
RULES = {"K2": lambda b, d, t, s: 2, "K4": lambda b, d, t, s: 4, "K5": lambda b, d, t, s: 5,
         "AGG": lambda b, d, t, s: 1 if b <= -1000.0 else (3 if b <= -500.0 else 5)}


def attempt(start, rule):
    """-> ('pass' | 'fail' | 'timeout', date the attempt ended)"""
    end = (pd.Timestamp(start) + pd.Timedelta(days=90)).date(); i = int(np.searchsorted(TIX, np.datetime64(pd.Timestamp(start))))
    bal = 0.0; best = 0.0; last = start
    for d in TD[i:]:
        if d >= end: return "timeout", end
        k = rule(bal, (d - start).days, max(4000.0, best / 0.55), 0); p, w = DAY[k][d]; last = d
        if bal + min(w, p) <= -2000.0: return "fail", d
        bal += p; best = max(best, p)
        if bal >= max(4000.0, best / 0.55): return "pass", d
    return "timeout", end


def share(x): return round(100 * float(np.mean(x)), 1)


SESS = H.SESS; out = {"single": {}, "sequential": {}, "pair": {}}
single = {s: attempt(s, DEF) for s in SESS}
for nm, st in (("h1", H.A), ("h2", H.B)):
    out["single"][nm] = share([single[s][0] == "pass" for s in st])
    seq = []
    for s in st:
        o, e = single[s]
        if o == "pass": seq.append(True); continue
        nxt = next((x for x in SESS if x > e), None)
        seq.append(nxt is not None and attempt(nxt, DEF)[0] == "pass")
    out["sequential"][nm] = share(seq)
for r, f in RULES.items():
    second = {s: attempt(s, f) for s in SESS}
    out["pair"][r] = {nm: dict(at_least_one=share([single[s][0] == "pass" or second[s][0] == "pass" for s in st]),
                               acct2_alone=share([second[s][0] == "pass" for s in st]),
                               both=share([single[s][0] == "pass" and second[s][0] == "pass" for s in st])) for nm, st in (("h1", H.A), ("h2", H.B))}
    print(r, out["pair"][r], flush=True)
pA = max(RULES, key=lambda r: out["pair"][r]["h1"]["at_least_one"]); pB = max(RULES, key=lambda r: out["pair"][r]["h2"]["at_least_one"])
oA, oB = out["pair"][pB]["h1"]["at_least_one"], out["pair"][pA]["h2"]["at_least_one"]
out["result"] = dict(picked_on_h1=pA, picked_on_h2=pB, oof_h1=oA, oof_h2=oB, oof_all=round((oA * len(H.A) + oB * len(H.B)) / len(SESS), 1))
print("single", out["single"], "sequential (2 attempts, <=180 days)", out["sequential"], "pair result", out["result"], flush=True)
(ROOT / "reports/EVAL_14_PARALLEL_PAIR_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))

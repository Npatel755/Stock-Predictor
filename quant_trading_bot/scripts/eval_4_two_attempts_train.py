"""eval_4 (Claude, 2026-11-10): what do two (or three) $149 Static Combine attempts really buy? TRAINING 2010-23 only. Measurement, no selection.

Checks Antigravity's "Solution 2" (reports/RESEARCH_MAXIMIZE_EVAL_PASS_RATE.json): 55.2% pass per attempt with the defensive policy
(k3, k2 at <= -$500, k1 at <= -$1,000) and 1 - (1 - 0.552)^2 = 80% for two attempts, which assumes the attempts are independent.
Uses Antigravity's own book and simulator (scripts/research_maximize_eval_pass_rate.py: CRABEL15_D + TRD60_D + MES_TRD30_D + overnight dip,
integer micros, 1-minute MAE floor check, DLL $1,000, 55% consistency, 90 calendar days), exec'd up to its policy list.
SEQUENTIAL: attempt 2 starts the session after attempt 1 fails or expires (how a trader would do it). PARALLEL: both bought on the same day
(identical trades, so identical outcomes). Starts: every session 2010-06..2022-12 (room for three attempts). Reported per policy: pass within
1 / 2 / 3 attempts, expected attempts bought, median calendar days from the first purchase to a pass, both halves.
"""
import json
import numpy as np, pandas as pd
import payout_lib as pl

src = (pl.ROOT / "scripts/research_maximize_eval_pass_rate.py").read_text(encoding="utf-8").split("\npolicies = {}")[0]
src = src.split("\ndef evaluate_policy(")[0]
AG = {"__name__": "ag", "__file__": str(pl.ROOT / "scripts/research_maximize_eval_pass_rate.py")}; exec(src, AG)
BY, TDAYS, TIX, SESS = AG["BY"], AG["TDAYS"], AG["TIX"], AG["SESS"]
SIDX = {d: i for i, d in enumerate(SESS)}


def attempt(s, rule):
    """One 90-day attempt starting at session s. Returns (outcome, end date)."""
    end = (pd.Timestamp(s) + pd.Timedelta(days=90)).date(); a = int(np.searchsorted(TIX, np.datetime64(pd.Timestamp(s)))); bal = 0.0; best = 0.0
    for d in TDAYS[a:]:
        if d >= end: return "timeout", end
        k = rule(bal); stop = min(400.0 * k, 700.0); day = 0.0
        g = BY[k].get(d)
        if g is not None:
            for r in g.itertuples():
                if day <= -stop or day <= -1000.0: break
                if bal + day + r.mae <= -2000.0: return "fail", d
                if day + r.mae <= -1000.0: day = -1000.0; break
                day += r.net
        bal += max(day, -1000.0); best = max(best, day)
        if bal <= -2000.0: return "fail", d
        if bal >= max(4000.0, best / 0.55): return "pass", d
    return "timeout", end


def chain(s, rule, max_attempts=3):
    cur = s; used = 0
    while used < max_attempts:
        used += 1; out, endd = attempt(cur, rule)
        if out == "pass": return used, (endd - s).days
        nxt = [d for d in SESS[SIDX.get(cur, 0):] if d > endd]
        if not nxt: return None, None
        cur = nxt[0]
    return 0, None


POL = {"fixed k3 (no TRD30PM)": lambda b: 3, "AG defensive: k3, k2 <= -500, k1 <= -1000": lambda b: 1 if b <= -1000 else (2 if b <= -500 else 3)}
starts = [d for d in SESS if d <= pd.Timestamp("2022-12-30").date()]
out = {}
for name, rule in POL.items():
    rows = []
    for s in starts:
        used, days = chain(s, rule)
        if used is None: continue
        rows.append((s, used, days))
    r = pd.DataFrame(rows, columns=["start", "used", "days"])
    def summ(m):
        x = r[m]; passed = x.used > 0
        return dict(starts=int(len(x)), pass_1=round(100 * float((x.used == 1).mean()), 1), pass_within_2=round(100 * float(((x.used >= 1) & (x.used <= 2)).mean()), 1),
                    pass_within_3=round(100 * float(passed.mean()), 1),
                    expected_attempts_bought=round(float(np.where(passed, x.used, 3).mean()), 2),
                    median_days_to_pass=float(x.days[passed].median()) if passed.any() else None)
    h1 = (r.start < pd.Timestamp("2017-01-01").date()).to_numpy()
    out[name] = dict(all=summ(np.ones(len(r), bool)), half1=summ(h1), half2=summ(~h1))
    print(name, out[name], flush=True)
out["independence_formula_for_comparison"] = {n: {"two": round(100 * (1 - (1 - v["all"]["pass_1"] / 100) ** 2), 1), "three": round(100 * (1 - (1 - v["all"]["pass_1"] / 100) ** 3), 1)}
                                              for n, v in out.items()}
print("if attempts were independent:", out["independence_formula_for_comparison"])
(pl.ROOT / "reports/EVAL_4_TWO_ATTEMPTS_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))

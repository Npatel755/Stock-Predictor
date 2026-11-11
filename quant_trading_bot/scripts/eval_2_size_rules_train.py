"""eval_2 (Claude, 2026-11-10): balance-dependent size rules for the 3x evaluation book. TRAINING 2010-23 only (2024-26 spent for this book).

PRE-DECLARED (before results). Base E0 = eval_1 selection: k = 3 (size min(k x base, floor($900 / risk))), overnight on, account stop $700;
same evaluation rules and MAE floor check as eval_1. Variants (k chosen each day from the balance at the prior close):
  E1 k 3, k 2 at or below -$1,000 | E2 k 3, k 1 at or below -$1,000 | E3 k 4, k 2 at or below -$1,000 | E4 k 3, k 2 at or above +$3,000.
ADOPT the variant with the highest pass share only if it beats E0 by >= 2 points overall AND beats E0 in both halves of the starts.
"""
import json
import numpy as np, pandas as pd
import payout_lib as pl

src = (pl.ROOT / "scripts/eval_1_scaled_payout_book_train.py").read_text(encoding="utf-8").split("\nout = {}\n")[0]
E1 = {"__name__": "e1"}; exec(src, E1)
trades, SESS = E1["trades"], E1["SESS"]
BY = {}
for k in (1, 2, 3, 4):
    t = trades(k, True); BY[k] = {d: g for d, g in t.groupby("day")}
TDAYS = sorted(set().union(*[set(v) for v in BY.values()])); TIX = pd.to_datetime(pd.Series(TDAYS).astype(str)).to_numpy()


def evaluate(rule):
    out = []
    for s in SESS:
        end = (pd.Timestamp(s) + pd.Timedelta(days=90)).date()
        a = int(np.searchsorted(TIX, np.datetime64(pd.Timestamp(s)))); bal = 0.0; best = 0.0; res = "timeout"
        for d in TDAYS[a:]:
            if d >= end: break
            k = rule(bal); stop = min(400.0 * k, 700.0); day = 0.0
            g = BY[k].get(d)
            if g is not None:
                for r in g.itertuples():
                    if day <= -stop or day <= -1000.0: break
                    if bal + day + r.mae <= -2000.0: res = "fail"; break
                    if day + r.mae <= -1000.0: day = -1000.0; break
                    day += r.net
            if res == "fail": break
            bal += max(day, -1000.0); best = max(best, day)
            if bal <= -2000.0: res = "fail"; break
            if bal >= max(4000.0, best / 0.55): res = "pass"; break
        out.append((s, res))
    r = pd.DataFrame(out, columns=["start", "res"]); h1 = (r.start < pd.Timestamp("2017-01-01").date()).to_numpy()
    def sh(m): return {o: round(100 * float((r.res[m] == o).mean()), 1) for o in ("pass", "fail", "timeout")}
    return dict(all=sh(np.ones(len(r), bool)), half1=sh(h1), half2=sh(~h1))


RULES = {"E0 k3": lambda b: 3, "E1 k3, k2 at <= -$1,000": lambda b: 2 if b <= -1000 else 3, "E2 k3, k1 at <= -$1,000": lambda b: 1 if b <= -1000 else 3,
         "E3 k4, k2 at <= -$1,000": lambda b: 2 if b <= -1000 else 4, "E4 k3, k2 at >= +$3,000": lambda b: 2 if b >= 3000 else 3}
out = {}
for name, rule in RULES.items():
    out[name] = evaluate(rule); c = out[name]
    print(f"{name:26s} {c['all']} | half1 {c['half1']['pass']} half2 {c['half2']['pass']}", flush=True)
b = out["E0 k3"]; cand = {k: v for k, v in out.items() if k != "E0 k3"}
best = max(cand, key=lambda k: cand[k]["all"]["pass"])
out["summary"] = dict(best=best, adopt=bool(cand[best]["all"]["pass"] >= b["all"]["pass"] + 2 and cand[best]["half1"]["pass"] > b["half1"]["pass"]
                                            and cand[best]["half2"]["pass"] > b["half2"]["pass"]))
print(out["summary"])
(pl.ROOT / "reports/EVAL_2_SIZE_RULES_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))

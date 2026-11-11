"""eval_17 (Claude, 2026-11-11): the eval_8 plan on the Daily Payouts+ Combine's OTHER drawdown option. TRAINING 2010-23. Information only.

The static $4k product is Nick's choice (the funded plans - Fortress 4X etc. - are built for its static floor). eval_7 A measured the
End-of-Day trailing version on the old base book only (k2 58.8% vs static k3 53.4%). This re-measures it with the eval_8 book.
PRE-DECLARED (before results). Harness book and day simulator; EOD rules as eval_7 A: target $3,000; floor = min($0, best end-of-day
balance - $2,000), checked against each day's intraday worst point (MAE); consistency 55% (target = max(3000, best day / 0.55)); 90 days.
Rules: K2 fixed, K3 fixed, DEF3 = the incumbent ladder measured from the trailing floor (k3; k2 when within $1,500 of the floor; k1 within
$1,000; k5 from day 60 if > $1,000 short and > $1,500 above the floor). 2-fold pick (2010-16 starts <-> 2017-23 starts); out-of-fold
number compared with the static product's incumbent 54.5 / 65.6.
"""
import json
import numpy as np, pandas as pd
from pathlib import Path
import eval_harness as eh

ROOT = Path(__file__).resolve().parents[1]
H = eh.Harness()
PD = H._per_day(H.BOOK[H.COLS].assign(noise=False)); TD = sorted(PD); TIX = pd.to_datetime(pd.Series(TD).astype(str)).to_numpy()
DAY = {k: {d: H.sim_day(PD[d], float(k)) for d in TD} for k in (1, 2, 3, 5)}


def DEF3(room, day, short):
    if day >= 60 and short > 1000.0 and room > 1500.0: return 5
    return 1 if room <= 1000.0 else (2 if room <= 1500.0 else 3)


RULES = {"K2": lambda room, day, short: 2, "K3": lambda room, day, short: 3, "DEF3": DEF3}


def run(starts, rule):
    res = []
    for s in starts:
        end = (pd.Timestamp(s) + pd.Timedelta(days=90)).date(); i = int(np.searchsorted(TIX, np.datetime64(pd.Timestamp(s))))
        bal = 0.0; peak = 0.0; best = 0.0; o = "timeout"
        for d in TD[i:]:
            if d >= end: break
            floor = min(0.0, peak - 2000.0); tgt = max(3000.0, best / 0.55)
            k = rule(bal - floor, (d - s).days, tgt - bal); p, w = DAY[k][d]
            if bal + min(w, p) <= floor: o = "fail"; break
            bal += p; best = max(best, p); peak = max(peak, bal)
            if bal >= max(3000.0, best / 0.55): o = "pass"; break
        res.append(o)
    x = pd.Series(res)
    return dict(pass_=round(100 * float((x == "pass").mean()), 1), fail=round(100 * float((x == "fail").mean()), 1),
                timeout=round(100 * float((x == "timeout").mean()), 1), n=len(x))


out = {r: dict(h1=run(H.A, f), h2=run(H.B, f)) for r, f in RULES.items()}
for r in out: print(r, out[r], flush=True)
pA = max(out, key=lambda r: out[r]["h1"]["pass_"]); pB = max(out, key=lambda r: out[r]["h2"]["pass_"])
oA, oB = out[pB]["h1"]["pass_"], out[pA]["h2"]["pass_"]
out["result"] = dict(pick_h1=pA, pick_h2=pB, oof_h1=oA, oof_h2=oB, oof_all=round((oA * len(H.A) + oB * len(H.B)) / (len(H.A) + len(H.B)), 1),
                     static_incumbent=dict(h1=54.5, h2=65.6, all=60.0))
print("result", out["result"], flush=True)
(ROOT / "reports/EVAL_17_EOD_PRODUCT_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))

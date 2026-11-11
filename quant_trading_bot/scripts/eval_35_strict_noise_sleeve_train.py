"""eval_35 (Claude, 2026-11-11): the noise-area MNQ momentum edge (eval_12: PF 1.14 / 1.32, real) as a ROUTED sleeve on the STRICT book.
TRAINING 2010-23 only.

Why (written before results): it was rejected as a concurrent stream (eval_13: stacked risk) and as a swap for TRD60 under posthoc routing
(eval_21: crowds out the book). Under STRICT routing it can only use a free slot and never stacks on a book position. Lowest priority
(ties in decision time go to the book). Ledgers: reports/EVAL_13_NOISE_MNQ_{P,R}_TRADES_TRAINING.csv (built on hole data: no Jan-May 2019).
PRE-DECLARED cells: ADD_NOISE_P, ADD_NOISE_R on STRICT + DEF_END (base 54.4 / 61.1). 2-fold pick; ADOPT only if both out-of-fold halves >=
base + 1.0.
"""
import os, json
os.environ["TRAIN_MINI_UNTIL"] = "2019-05-06"
import numpy as np, pandas as pd
from pathlib import Path
import eval_harness as eh

ROOT = Path(__file__).resolve().parents[1]
H = eh.Harness(); COLS = list(H.PRE.columns)
out = {"base": H.pass_rate(book=H.build_book(H.PRE, strict=True), v2=True)}; print("base", out["base"], flush=True)
for m in ("P", "R"):
    t = pd.read_csv(ROOT / f"reports/EVAL_13_NOISE_MNQ_{m}_TRADES_TRAINING.csv")
    for c in ("tin", "tout", "dec"): t[c] = pd.to_datetime(t[c], utc=True).dt.tz_convert("America/New_York")
    t = t.assign(sleeve=f"NOISE_{m}", prio=99, net_then=t.per_micro, net_today=t.per_micro, n_contracts=1.0)[COLS]
    bk = H.build_book(pd.concat([H.PRE, t], ignore_index=True), strict=True)
    r = H.pass_rate(book=bk, v2=True); r["noise_taken"] = int((bk.sleeve == f"NOISE_{m}").sum()); r["book_trades"] = int(len(bk))
    out[f"ADD_NOISE_{m}"] = r; print(m, r, flush=True)
C = {k: v for k, v in out.items() if k.startswith("ADD")}; b = (out["base"]["h1"]["pass_"], out["base"]["h2"]["pass_"])
pA = max(C, key=lambda c: C[c]["h1"]["pass_"]); pB = max(C, key=lambda c: C[c]["h2"]["pass_"])
oA, oB = C[pB]["h1"]["pass_"], C[pA]["h2"]["pass_"]
out["result"] = dict(pick_h1=pA, pick_h2=pB, oof_h1=oA, oof_h2=oB, base=b, adopt=bool(oA >= b[0] + 1.0 and oB >= b[1] + 1.0))
print("result", out["result"], flush=True)
(ROOT / "reports/EVAL_35_STRICT_NOISE_SLEEVE_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))

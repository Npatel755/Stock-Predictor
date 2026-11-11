"""eval_34 (Claude, 2026-11-11): re-screen the sleeve pool on the STRICT book (one position at a time), v2 semantics, filled 2019 data.
TRAINING 2010-23 only.

Why (written before results): every sleeve decision so far (v5.3, eval_7 greedy add, regx_1 screen) was made on the OVERLAPPING book
under the look-ahead simulator, where an extra sleeve stacked same-direction risk. Under STRICT routing a sleeve can only take a free slot
(earliest decision wins), so it adds trades on otherwise idle time instead of doubling size - the economics of adding a sleeve change.
PRE-DECLARED. Base = STRICT book + DEF_END = 54.4 / 61.1. Candidate ledgers = reports/regx_ledgers (regx_1, same columns and cost model as
the harness PRE; built on the hole data, so they have no Jan-May 2019 trades). NF (unfiltered) version when it exists, else F:
  ADD_x for x in AG_BRK30_1c, AG_CRABEL15_1c, AG_MES_TRD30_1c, AG_MORN30_1c, AG_TRD30C_1c(F), AG_TRD30PM_1c, AG_TRD30_D_1c, AG_TRD60C_1c(F),
  AG_TRD60Q_1c, MNQ_E57_1c, MNQ_HYB_C_1c, MNQ_VOL_1c   (12 additions; the gap add-on and overnight variants are excluded: already in the book)
  DROP_MES_MOM_3c, DROP_MNQ_BRK_E_2c   (eval_30: MES_MOM adds nothing, MNQ_BRK_E is era-split)
ROUND 1: 2-fold pick (best on 2010-16 starts reported on 2017-23 and vice versa); ADOPT only if both out-of-fold halves >= base + 1.0.
ROUND 2 (only if round 1 adopts the SAME cell from both halves): repeat all remaining single changes on top of it, same rule. Max 2 rounds.
"""
import os, json
os.environ["TRAIN_MINI_UNTIL"] = "2019-05-06"
import numpy as np, pandas as pd
from pathlib import Path
import eval_harness as eh

ROOT = Path(__file__).resolve().parents[1]; LED = ROOT / "reports/regx_ledgers"
H = eh.Harness(); COLS = list(H.PRE.columns)
ADDS = ["AG_BRK30_1c", "AG_CRABEL15_1c", "AG_MES_TRD30_1c", "AG_MORN30_1c", "AG_TRD30C_1c", "AG_TRD30PM_1c", "AG_TRD30_D_1c", "AG_TRD60C_1c",
        "AG_TRD60Q_1c", "MNQ_E57_1c", "MNQ_HYB_C_1c", "MNQ_VOL_1c"]
POOL = {}
for s in ADDS:
    p = LED / f"{s}_NF.csv"
    if not p.exists(): p = LED / f"{s}_F.csv"
    t = pd.read_csv(p)
    for c in ("tin", "tout", "dec"): t[c] = pd.to_datetime(t[c], utc=True).dt.tz_convert("America/New_York")
    t["sleeve"] = "X_" + s
    POOL[f"ADD_{s}"] = t[COLS]; print(s, p.name, len(t), flush=True)
DROPS = {"DROP_MES_MOM_3c": "MES_MOM_3c", "DROP_MNQ_BRK_E_2c": "MNQ_BRK_E_2c"}


def apply(pre, change):
    if change in POOL: return pd.concat([pre, POOL[change]], ignore_index=True)
    return pre[pre.sleeve != DROPS[change]]


def score(pre):
    r = H.pass_rate(book=H.build_book(pre, strict=True), v2=True); return r


out = {"rounds": []}; base_pre = H.PRE; base = score(base_pre); print("base", base, flush=True)
assert (base["h1"]["pass_"], base["h2"]["pass_"]) == (54.4, 61.1)
changes = list(POOL) + list(DROPS)
for rnd in (1, 2):
    C = {c: score(apply(base_pre, c)) for c in changes}
    for c in C: print(rnd, c, C[c]["h1"]["pass_"], C[c]["h2"]["pass_"], C[c]["h1"]["fail"], C[c]["h2"]["fail"], flush=True)
    pA = max(C, key=lambda c: C[c]["h1"]["pass_"]); pB = max(C, key=lambda c: C[c]["h2"]["pass_"])
    oA, oB = C[pB]["h1"]["pass_"], C[pA]["h2"]["pass_"]
    adopt = bool(oA >= base["h1"]["pass_"] + 1.0 and oB >= base["h2"]["pass_"] + 1.0)
    res = dict(round=rnd, base=dict(h1=base["h1"]["pass_"], h2=base["h2"]["pass_"]), cells=C, pick_h1=pA, pick_h2=pB, oof_h1=oA, oof_h2=oB,
               adopt=adopt, same_pick=pA == pB)
    out["rounds"].append(res); print("round", rnd, {k: v for k, v in res.items() if k != "cells"}, flush=True)
    if not (adopt and pA == pB): break
    base_pre = apply(base_pre, pA); base = C[pA]; changes = [c for c in changes if c != pA]
out["final_changes"] = [r["pick_h1"] for r in out["rounds"] if r["adopt"] and r["same_pick"]]
(ROOT / "reports/EVAL_34_STRICT_SLEEVE_POOL_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
print("saved", out["final_changes"], flush=True)

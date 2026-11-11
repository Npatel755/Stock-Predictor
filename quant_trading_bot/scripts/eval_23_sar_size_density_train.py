"""eval_23 (Claude, 2026-11-11): the eval_18 stop-and-reverse hedge at the size the screen preferred, and on every stop-out. TRAINING only.

NEW PHASE after eval_18 (whose F1 / k-sized cells were not adopted: out-of-fold 54.7 / 63.4). Written before any eval_23 result:
eval_18's screen put the best weight at 3 micros (combined daily Sharpe 0.1608 vs 0.1506), but only F1 and K were run in the simulator.
Exits = X2 (+1R target, 1R stop, 15:59 close), causal entry as eval_18. Cells (4): trigger {FIRST = first stop-out per instrument per day
(eval_18), ALL = every routed stop-out} x size {F2, F3 fixed micros, capped at floor($900 / risk)}.
2-fold: pick on 2010-16 starts, report 2017-23, and vice versa; ADOPT only if both out-of-fold halves >= 55.5 / 66.6 (incumbent + 1).
Selection count so far for this hedge family: eval_18 (3 exits x 2 sizes) + these 4 cells.
"""
import json
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/eval_18_stop_reverse_hedge_train.py").read_text(encoding="utf-8").split('\nout = {"stopouts"')[0]
E = {"__name__": "e23", "__file__": str(ROOT / "scripts/eval_18_stop_reverse_hedge_train.py")}; exec(src, E)
H, R0, stops, reversal = E["H"], E["R0"], E["stops"], E["reversal"]
allstops = R0[R0.ret <= -0.8 * R0.stop_pct].sort_values("tout")
LED = {"FIRST": pd.DataFrame([x for x in (reversal(r, "X2") for r in stops.itertuples()) if x is not None]),
       "ALL": pd.DataFrame([x for x in (reversal(r, "X2") for r in allstops.itertuples()) if x is not None])}
out = {"trades": {k: len(v) for k, v in LED.items()}, "cells": {}}; print("trades", out["trades"], flush=True)
for trig, t in LED.items():
    for ns in ("F2", "F3"):
        c = H.pass_rate(extra=t, nsize=ns); out["cells"][f"{trig}_{ns}"] = c; print(trig, ns, c, flush=True)
C = out["cells"]; pA = max(C, key=lambda k: C[k]["h1"]["pass_"]); pB = max(C, key=lambda k: C[k]["h2"]["pass_"])
oA, oB = C[pB]["h1"]["pass_"], C[pA]["h2"]["pass_"]
out["result"] = dict(pick_h1=pA, pick_h2=pB, oof_h1=oA, oof_h2=oB, adopt=bool(oA >= 55.5 and oB >= 66.6))
print("result", out["result"], flush=True)
(ROOT / "reports/EVAL_23_SAR_SIZE_DENSITY_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))

"""eval_28 (Claude, 2026-11-11): the eval_8 incumbent under CORRECTED day semantics, with and without the 2019 data hole. TRAINING only.

Found while checking eval_27: filling the Jan-May 2019 hole moved the 2010-16 pass rate 54.5 -> 51.4 although every 2010-16 trade is
identical. Cause: Harness._per_day sorts each day's trades with an unstable sort, so same-minute ties (269 days) change order with the
frame's row count, and sim_day (v1) lets the first trade's FINAL P&L stop the second through the $400 / $700 daily stop. v1 also counts the
final P&L of trades still open at the next entry (341 entries; a look-ahead) and trusts MAE values better than the trade's final loss (831
trades). Harness.sim_day_v2 fixes all three (see its docstring). Information only; nothing is chosen.
Usage: python eval_28_corrected_semantics_train.py 2019-01-01|2019-05-06   (TRAIN_MINI_UNTIL; the second fills the hole)
Reports, per half: v1 (as before), v2, v2 on a randomly shuffled frame (must equal v2: order invariance), and flat k3 under v2.
"""
import os, sys, json
os.environ["TRAIN_MINI_UNTIL"] = sys.argv[1]
import numpy as np, pandas as pd
from pathlib import Path
import eval_harness as eh

ROOT = Path(__file__).resolve().parents[1]
H = eh.Harness()
out = dict(mini_until=sys.argv[1], n_h1=len(H.A), n_h2=len(H.B))
out["v1"] = H.pass_rate(); print("v1", out["v1"], flush=True)
out["v2"] = H.pass_rate(v2=True); print("v2", out["v2"], flush=True)
shuf = H.BOOK.sample(frac=1.0, random_state=28).reset_index(drop=True)
out["v2_shuffled"] = H.pass_rate(book=shuf, v2=True); print("v2 shuffled", out["v2_shuffled"], flush=True)
out["v2_order_invariant"] = all(out["v2"][h]["pass_"] == out["v2_shuffled"][h]["pass_"] for h in ("h1", "h2"))
out["v2_flat_k3"] = H.pass_rate(v2=True, rule=lambda bal, day, tgt, s: 3); print("v2 flat k3", out["v2_flat_k3"], flush=True)
tag = "HOLE" if sys.argv[1] == "2019-01-01" else "FILLED"
(ROOT / f"reports/EVAL_28_CORRECTED_SEMANTICS_{tag}_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
print("saved", tag, flush=True)

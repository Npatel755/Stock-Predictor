"""eval_36 (Claude, 2026-11-11): re-measure STRICT routing with a CAUSAL implementation before any holdout or paper use. TRAINING only.

Found while preparing the paper card: eval_30-35's route_strict sorts by `dec` (decision-bar START label) and blocks a trade whose label is
earlier than the latest exit of any accepted trade. A 60m trade labelled 10:00 is only known at 11:00, yet it can block a 15m trade known at
10:15 - the live runner could not do that. Harness.route_strict_causal processes trades by tin (when the signal is known and filled), takes
a trade only if nothing accepted is still open then, one per entry minute.
PRE-DECLARED: report INC (posthoc), STRICT (label-sorted, eval_30) and STRICT_CAUSAL under v2 + filled data, plus E57 added to each strict
version (eval_34's near-miss), and how many trades the two strict rules disagree on. From now on STRICT_CAUSAL is THE strict rule (it is the
only live-feasible one); the evaluation plan uses it if it is >= INC in both halves (eval_32 priced INC at 49.8 / 60.0 with measured overlap
risk; v2 is 49.7 / 59.4).
"""
import os, json
os.environ["TRAIN_MINI_UNTIL"] = "2019-05-06"
import pandas as pd
from pathlib import Path
import eval_harness as eh

ROOT = Path(__file__).resolve().parents[1]
H = eh.Harness(); COLS = list(H.PRE.columns)
t = pd.read_csv(ROOT / "reports/regx_ledgers/MNQ_E57_1c_NF.csv")
for c in ("tin", "tout", "dec"): t[c] = pd.to_datetime(t[c], utc=True).dt.tz_convert("America/New_York")
E57 = t.assign(sleeve="X_MNQ_E57_1c")[COLS]
pre = H.PRE[H.PRE.risk_today <= 300.0]
a = set(H.route_strict(pre).index); b = set(H.route_strict_causal(pre).index)
out = dict(trades_label=len(a), trades_causal=len(b), only_label=len(a - b), only_causal=len(b - a))
print("disagreement", out, flush=True)
for nm, p, s in (("INC", H.PRE, False), ("STRICT", H.PRE, True), ("STRICT_CAUSAL", H.PRE, "causal"),
                 ("STRICT+E57", pd.concat([H.PRE, E57], ignore_index=True), True),
                 ("STRICT_CAUSAL+E57", pd.concat([H.PRE, E57], ignore_index=True), "causal")):
    out[nm] = H.pass_rate(book=H.build_book(p, strict=s), v2=True); print(nm, out[nm], flush=True)
(ROOT / "reports/EVAL_36_STRICT_CAUSAL_CHECK_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
print("saved", flush=True)

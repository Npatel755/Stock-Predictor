"""eval_19 (Claude, 2026-11-11): friction stress on the eval_8 plan. TRAINING 2010-23. Realism check, nothing to adopt.
PRE-DECLARED: add +1 and +2 ticks of adverse slippage PER SIDE to every fill of every book trade and the overnight leg (on top of the
book's 2 ticks per side + $1). Per micro round trip: MNQ +$1.00 / +$2.00, MES +$2.50 / +$5.00. MAE worsened by the same amount (cost is
paid on the entry and exit). Report the incumbent rule's pass rate per half.
"""
import json
import pandas as pd
from pathlib import Path
import eval_harness as eh

ROOT = Path(__file__).resolve().parents[1]
H = eh.Harness(); N0 = H.NIGHTS.copy(); out = {"base": H.pass_rate()}
print("base", out["base"], flush=True)
for t in (1, 2):
    tick = {"MNQ": 0.25 * t * 2 * 2.0, "MES": 0.25 * t * 2 * 5.0}         # ticks/side x 2 sides x $ per point
    pre = H.PRE.copy(); c = pre.inst.map(tick).fillna(tick["MNQ"])
    pre["net_today"] = pre.net_today - c * pre.n_contracts; pre["mae_per_micro"] = pre.mae_per_micro - c
    H.NIGHTS = N0.assign(per_micro=N0.per_micro - tick["MNQ"], mae_per_micro=N0.mae_per_micro - tick["MNQ"])
    out[f"plus_{t}_tick_per_side"] = H.pass_rate(book=H.build_book(pre)); H.NIGHTS = N0
    print(t, out[f"plus_{t}_tick_per_side"], flush=True)
(ROOT / "reports/EVAL_19_FRICTION_STRESS_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))

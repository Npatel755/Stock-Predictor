"""eval_8 (Claude, 2026-11-10): combinations of half-specific gains. TRAINING 2010-23 only. POST HOC - read with care.

Why post hoc: eval_5/eval_7 and Antigravity's research_maximize_eval_pass_rate showed that the endgame boost and the extra sleeves
(MNQ_BRK_E_2c + MES_MOM_3c) only help 2010-16, while the defensive ladder (k3; k2 at <= -$500; k1 at <= -$1,000) only helps 2017-23. These
combinations were chosen AFTER seeing both halves, so no half is clean any more; the forward paper ledger is the real test.
Fixed list (written before running): DEF | DEF + ENDGAME (from day 60, gap > $1,000 -> k5) | SLEEVES (v5.3 + BRK_E + MES_MOM, k3) |
SLEEVES + DEF | SLEEVES + DEF + ENDGAME. Bar for "robust": BOTH halves >= v5.3 k3 + 1.5 points AND overall >= + 2 points.
Same simulator and starts as eval_5 (Static $4,000, 90 days, 1-minute MAE floor check).
"""
import json
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/eval_5_pass_rate_train.py").read_text(encoding="utf-8").split("\nTAB = {")[0]
E = {"__name__": "e8", "__file__": str(ROOT / "scripts/eval_5_pass_rate_train.py")}; exec(src, E)
pl, variant, table, evaluate, size_k, mae_pct, base0 = (E[k] for k in ("pl", "variant", "table", "evaluate", "size_k", "mae_pct", "base0"))
P10 = E["P10"]; ep, bars_for, START = P10["ep"], P10["bars_for"], P10["START"]
SLV = []
for prio, (name, key) in enumerate((("MNQ_BRK_E_2c", "portfolio_e"), ("MES_MOM_3c", "portfolio_e")), start=10):
    sl = next(s for s in ep.CANDIDATES[key]["sleeves"] if s["name"] == name)
    x = pl.price_normalize(pl.sleeve_trades(ep, bars_for, START, dict(sl), prio, False)); x["n_contracts"] = 1.0
    x["mae_per_micro"] = [(mae_pct(r.inst, r.tin, r.tout, r.side, r.entry) * pl.TODAY[r.inst] - pl.ADV) * pl.MULT[r.inst] for r in x.itertuples()]
    SLV.append(x[base0.columns])
T_BASE = table(variant("A")); T_SLV = table(pd.concat([variant("A")] + SLV, ignore_index=True))
k3 = lambda bal, day, tgt: size_k(3)
DEF = lambda bal, day, tgt: size_k(1 if bal <= -1000 else (2 if bal <= -500 else 3))
DEF_END = lambda bal, day, tgt: size_k(5) if (day >= 60 and bal < tgt - 1000 and bal > -500) else DEF(bal, day, tgt)
cells = {"base v5.3 k3": (T_BASE, k3), "DEF": (T_BASE, DEF), "DEF + ENDGAME": (T_BASE, DEF_END), "SLEEVES": (T_SLV, k3),
         "SLEEVES + DEF": (T_SLV, DEF), "SLEEVES + DEF + ENDGAME": (T_SLV, DEF_END)}
out = {}
for name, (tab, rule) in cells.items():
    out[name] = evaluate(tab, rule); print(name, out[name], flush=True)
b = out["base v5.3 k3"]
for name in cells:
    if name == "base v5.3 k3": continue
    c = out[name]; c["robust"] = bool(c["h1"] >= b["h1"] + 1.5 and c["h2"] >= b["h2"] + 1.5 and c["all"] >= b["all"] + 2.0)
print({k: v.get("robust") for k, v in out.items()})
(ROOT / "reports/EVAL_8_COMBINATIONS_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))

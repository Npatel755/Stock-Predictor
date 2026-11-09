"""overnight_7 (research/overnight_7/PROTOCOL.md): expanding-window walk-forward of the v2 rule inside 2010-2023."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
src3 = (ROOT / "scripts/overnight_3_pilot.py").read_text().split("out = {")[0]; ns = {"__file__": str(ROOT / "scripts/overnight_3_pilot.py")}; exec(src3, ns)
nights, pnl = ns["nights"], ns["pnl"]
mn, ms = nights("MNQ"), nights("MES"); mg = ms.gap.reindex(mn.index)
def mask(k, w):
    sdq = mn.gap.rolling(w, min_periods=max(10, int(0.75 * w))).std().shift(1); sdm = ms.gap.rolling(w, min_periods=max(10, int(0.75 * w))).std().shift(1).reindex(mn.index)
    return ((mn.gap <= -k * sdq) & (mg <= -k * sdm)).fillna(False)
EXITS = {"x0930": "x0930", "x0935": "x0935", "x0945": "x0945", "x1000": "x1000"}
P = {ex: pnl(mn, "MNQ", ex=ex) for ex in EXITS}; M = {(k, w): mask(k, w) for k in (0.375, 0.5, 0.625, 0.75, 1.0) for w in (15, 20, 30)}
def score(sel):  # net / max(dd, 500)
    q = sel.dropna(); eq = q.cumsum(); dd = float((eq.cummax() - eq).max()) if len(q) else 0.0; return float(q.sum()) / max(dd, 500.0), float(q.sum())
years = mn.year; out = {"chain_params": {}, "chain_exit": {}, "wf_params_net": {}, "wf_exit_net": {}, "fixed_net": {}}
for Y in range(2014, 2024):
    past = years < Y; cur = years == Y
    best = max(M, key=lambda kw: score(P["x0945"][M[kw] & past])[0]); out["chain_params"][Y] = list(best); out["wf_params_net"][Y] = round(float(P["x0945"][M[best] & cur].dropna().sum()), 2)
    bex = max(EXITS, key=lambda ex: score(P[ex][M[(0.5, 20)] & past])[0]); out["chain_exit"][Y] = bex; out["wf_exit_net"][Y] = round(float(P[bex][M[(0.5, 20)] & cur].dropna().sum()), 2)
    out["fixed_net"][Y] = round(float(P["x0945"][M[(0.5, 20)] & cur].dropna().sum()), 2)
for k in ("wf_params_net", "wf_exit_net", "fixed_net"): out[k + "_total"] = round(sum(out[k].values()), 2)
out["stable_params"] = bool(sum(1 for v in out["chain_params"].values() if 0.375 <= v[0] <= 0.625) >= 7)
out["within_20pct"] = bool(out["wf_params_net_total"] >= 0.8 * out["fixed_net_total"] and out["wf_exit_net_total"] >= 0.8 * out["fixed_net_total"])
print(json.dumps(out, indent=0, default=str)); json.dump(out, open(ROOT / "reports/OVERNIGHT_7_WALKFORWARD.json", "w"), indent=1, default=str); print("DONE")

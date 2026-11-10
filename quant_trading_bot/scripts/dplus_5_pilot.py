"""dplus_5: gap-alignment state as sizing for D+ v2, training only (research/dplus_5/PROTOCOL.md)."""
import json
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/dplus_4_pilot.py").read_text().split("\ncrab = [")[0]; ns = {"__file__": str(ROOT / "scripts/dplus_4_pilot.py")}; exec(src, ns)
base, stats, marked = ns["base"], ns["stats"], ns["marked"]
def scaled(tr, pred):
    out = []
    for t in tr:
        q = 2 if pred(t) else 1; out.append(dict(t, net=t["net"] * q, stop_risk=t["stop_risk"] * q, qty=q))
    return out
def daily(tr):
    return pd.Series([x["net"] for x in tr], index=[x["exit_day"] for x in tr]).groupby(level=0).sum().sort_index()
def breach(d, paths=2000, floor=2000.0, block=20, seed=5):
    v = d.to_numpy(); rng = np.random.default_rng(seed); n = 252; hits = 0
    for _ in range(paths):
        idx = np.concatenate([np.arange(s, s + block) for s in rng.integers(0, len(v) - block, n // block + 1)])[:n]
        eq = np.cumsum(v[idx]); hits += bool(((np.maximum.accumulate(eq) - eq) >= floor).any() or (eq <= -floor).any())
    return hits / paths
def summ(tr):
    s = stats(tr); s.pop("by_year", None); m = marked(tr); return dict(s, **m, breach_1y=breach(daily(tr)), net_per_dd=round(s["net"] / m["marked_dd"], 2))
cells = {"v2_1c": base, "v2_2c_flat": scaled(base, lambda t: True), "S1_2c_on_continuation": scaled(base, lambda t: t["cont"]),
         "C1_2c_on_fades": scaled(base, lambda t: t["crabel"] and not t["cont"])}
out = {k: summ(v) for k, v in cells.items()}
for k, v in out.items(): print(k, v, flush=True)
s, c, r1, r2 = out["S1_2c_on_continuation"], out["C1_2c_on_fades"], out["v2_1c"], out["v2_2c_flat"]
g = dict(npd=s["net_per_dd"] > max(r1["net_per_dd"], r2["net_per_dd"]), dd=s["marked_dd"] < 1453 and s["touches"]["2000"] == 0 if "2000" in s["touches"] else s["touches"][2000] == 0,
         ctrl=s["net"] > c["net"] and s["marked_dd"] < c["marked_dd"], breach=s["breach_1y"] <= 0.01, years=s["pos_years"] >= 11)
out["gates"] = {k: bool(v) for k, v in g.items()}; out["pass"] = all(g.values()); print("gates", out["gates"], flush=True)
json.dump(out, open(ROOT / "reports/DPLUS_5_TRAINING.json", "w"), indent=1, default=str); print("DONE", flush=True)

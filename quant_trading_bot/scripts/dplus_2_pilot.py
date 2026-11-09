"""dplus_2 (research/dplus_2/PROTOCOL.md): ag_arch_d_plus without the MNQ 30m trend sleeve vs count-matched random-removal placebos. Training 2010-23 only."""
import json, sys, os
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
src = (ROOT / "scripts/dplus_1_pilot.py").read_text().split("\nout = {}")[0]; ns = {"__file__": str(ROOT / "scripts/dplus_1_pilot.py")}; exec(src, ns)
spec, run_sl, route, stats, marked = ns["spec"], ns["run_sl"], ns["route"], ns["stats"], ns["marked"]
by = {sl["name"]: run_sl(sl, i) for i, sl in enumerate(spec["sleeves"])}
B = route(sum(by.values(), [])); V1 = route(sum((v for k, v in by.items() if k != "AG_TRD30_D_1c"), []))
sB, sV = stats(B), stats(V1); mB, mV = marked(B), marked(V1)
yB, yV = pd.Series(sB.pop("by_year")), pd.Series(sV.pop("by_year")); inc = (yB - yV.reindex(yB.index).fillna(0.0))
rng = np.random.default_rng(202); k = len(B) - len(V1); worse = 0; dds = []
for _ in range(200):
    keep = sorted(rng.choice(len(B), len(B) - k, replace=False)); dd = marked([B[i] for i in keep])["marked_dd"]; dds.append(dd); worse += dd > mV["marked_dd"]
out = dict(B=dict(sB, **mB), V1=dict(sV, **mV), removed=k, incremental_by_year={int(a): round(float(b), 2) for a, b in inc.items()},
           V1_by_year={int(a): round(float(b), 2) for a, b in yV.items()},
           gates=dict(net_ratio=round(sV["net"] / sB["net"], 3), years=sV["pos_years"], dd_ratio=round(mV["marked_dd"] / mB["marked_dd"], 3), touches=mV["touches"],
                      placebo_worse=worse, placebo_median_dd=round(float(np.median(dds)), 2), inc_pos_years=int((inc > 0).sum()),
                      half1=round(float(yV[yV.index < 2017].sum()), 2), half2=round(float(yV[yV.index >= 2017].sum()), 2)))
g = out["gates"]; out["passes"] = bool(g["net_ratio"] >= 0.8 and g["years"] >= 11 and g["dd_ratio"] <= 0.6 and g["touches"][2000] == 0 and g["placebo_worse"] >= 190 and g["inc_pos_years"] < 10 and g["half1"] > 0 and g["half2"] > 0)
print(json.dumps(out, indent=1, default=str)); json.dump(out, open(ROOT / "reports/DPLUS_2_TRAINING.json", "w"), indent=1, default=str); print("DONE")

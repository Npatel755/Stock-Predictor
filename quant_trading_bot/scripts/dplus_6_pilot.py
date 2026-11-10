"""dplus_6: gap alignment on the D+ v2 trend sleeves, training only (research/dplus_6/PROTOCOL.md)."""
import json
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/dplus_5_pilot.py").read_text().split("\ncells = {")[0]; ns = {"__file__": str(ROOT / "scripts/dplus_5_pilot.py")}; exec(src, ns)
base, stats, marked, scaled, summ = ns["base"], ns["stats"], ns["marked"], ns["scaled"], ns["summ"]; ep, bars_for = ns["ns"]["ep"], ns["ns"]["bars_for"]
sls = ep.CANDIDATES["ag_arch_d_plus_v2"]["sleeves"]
gs = {}
for sl in sls:
    b, _, _ = bars_for(sl); gs[sl["name"]] = ep.gap_sign_by_day(b)
et = lambda ts: pd.Timestamp(ts).tz_convert("America/New_York").date()
for t in base:
    t["aligned"] = int(t["side"]) * gs[t["sleeve"]].get(et(t["entry_ts"]), 0) >= 0
out = {"base": summ(base)}; rng = np.random.default_rng(6)
def mini(tr):
    s = stats(tr); s.pop("by_year", None); return s
for name in ("AG_TRD60_D_1c", "AG_MES_TRD30_D_1c"):
    tr = [t for t in base if t["sleeve"] == name]; al = [t for t in tr if t["aligned"]]; op = [t for t in tr if not t["aligned"]]
    worse = sum(sum(t["net"] for t in rng.choice(tr, len(al), replace=False)) < sum(t["net"] for t in al) for _ in range(200))
    a, o = mini(al), mini(op)
    real = a["per"] > o["per"] and a["pos_years"] >= o["pos_years"] and worse >= 190
    out[name] = dict(aligned=a, opposed=o, placebo_worse_of_200=int(worse), real=bool(real)); print(name, out[name], flush=True)
S1 = lambda t: t["cont"]
cells = {"S1_gapsized_crabel": scaled(base, S1),
         "S2_plus_60m_aligned": scaled(base, lambda t: S1(t) or (t["sleeve"] == "AG_TRD60_D_1c" and t["aligned"])),
         "C2_plus_60m_opposed": scaled(base, lambda t: S1(t) or (t["sleeve"] == "AG_TRD60_D_1c" and not t["aligned"])),
         "S3_plus_mes_aligned": scaled(base, lambda t: S1(t) or (t["sleeve"] == "AG_MES_TRD30_D_1c" and t["aligned"])),
         "C3_plus_mes_opposed": scaled(base, lambda t: S1(t) or (t["sleeve"] == "AG_MES_TRD30_D_1c" and not t["aligned"])),
         "S4_all_aligned_2c": scaled(base, lambda t: S1(t) or (t["sleeve"] != "AG_CRABEL15_D_1c" and t["aligned"]))}
for k, v in cells.items():
    out[k] = summ(v); print(k, out[k], flush=True)
json.dump(out, open(ROOT / "reports/DPLUS_6_TRAINING.json", "w"), indent=1, default=str); print("DONE", flush=True)

"""Parity: paper runner run_overnight (overnight_dip_v2 spec) vs research nights()/pnl on train 2022-23 (training data only)."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import mass_1m_search as m1
from quant_futures import ensemble_paper as ep
spec = ep.CANDIDATES["overnight_dip_v2"]
bm = m1.load_bars("MNQ", 1, "2021-10-01", "2024-01-01", "train").reset_index(drop=True); be = m1.load_bars("MES", 1, "2021-10-01", "2024-01-01", "train").reset_index(drop=True)
res = ep.run_overnight(spec, bm, pd.Timestamp("2022-01-01", tz="UTC"), mes=be); tr = pd.DataFrame(res["trades"] if isinstance(res, dict) else res[0])
tr["night"] = pd.to_datetime(tr.entry_ts, utc=True).dt.tz_convert("America/New_York").dt.date
src3 = (ROOT / "scripts/overnight_3_pilot.py").read_text().split("out = {")[0]; n3 = {"__file__": str(ROOT / "scripts/overnight_3_pilot.py")}; exec(src3, n3)
mn, ms = n3["nights"]("MNQ"), n3["nights"]("MES"); mg, msd = ms.gap.reindex(mn.index), ms.sd20.reindex(mn.index)
mask = ((mn.gap <= -0.5 * mn.sd20) & (mg <= -0.5 * msd)).fillna(False); p = n3["pnl"](mn, "MNQ", ex="x0945"); p = p[mask & p.notna()]; p = p[[pd.Timestamp(d) >= pd.Timestamp("2022-01-01") for d in p.index]]
r_set, p_set = set(tr.night), set(p.index); both = sorted(r_set & p_set)
cmp = pd.DataFrame({"runner": tr.set_index("night").net.reindex(both), "research": p.reindex(both)}); cmp["diff"] = cmp.runner - cmp.research
print("runner nights", len(r_set), "research nights", len(p_set), "common", len(both)); print("runner only", sorted(r_set - p_set)[:10]); print("research only", sorted(p_set - r_set)[:10])
print("net runner", round(tr.net.sum(), 2), "research", round(p.sum(), 2), "max |diff| on common", round(cmp["diff"].abs().max(), 2), "mean diff", round(cmp["diff"].mean(), 3)); print(cmp[cmp["diff"].abs() > 1].head(10))

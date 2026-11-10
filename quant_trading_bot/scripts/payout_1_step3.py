"""payout_1 step 3: wider-target D+ v2 variants (cells declared in research/payout_1/PROTOCOL.md), training only."""
import json
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/dplus_1_pilot.py").read_text().split("\nout = {}")[0]; ns = {"__file__": str(ROOT / "scripts/dplus_1_pilot.py")}; exec(src, ns)
ep, run_sl, route, stats, marked = ns["ep"], ns["run_sl"], ns["route"], ns["stats"], ns["marked"]
base_sls = ep.CANDIDATES["ag_arch_d_plus_v2"]["sleeves"]
def run(mod):
    sls = [dict(sl, **mod.get(sl["name"], {})) for sl in base_sls]
    tr = route(sum((run_sl(sl, i) for i, sl in enumerate(sls)), []))
    nets = np.array([t["net"] for t in tr]); wins = nets[nets > 0]
    day = pd.Series(nets, index=[t["exit_day"] for t in tr]).groupby(level=0).sum(); wd = day[day > 0]
    s = stats(tr); s.pop("by_year", None); m = marked(tr)
    return dict(s, marked_dd=m["marked_dd"], median_win_trade=round(float(np.median(wins)), 2), share_win_ge150=round(float((wins >= 150).mean()), 3), win_rate=round(float((nets > 0).mean()), 3),
                median_win_day=round(float(np.median(wd)), 2), share_win_days_ge150=round(float((wd >= 150).mean()), 3), worst_day=round(float(day.min()), 2))
CELLS = {"base": {}, "crabel_t5": {"AG_CRABEL15_D_1c": dict(target_r=5.0)}, "crabel_t7": {"AG_CRABEL15_D_1c": dict(target_r=7.0)},
         "trd60_t6": {"AG_TRD60_D_1c": dict(target_r=6.0)}, "trd60_t8": {"AG_TRD60_D_1c": dict(target_r=8.0)},
         "crabel_t5_trd60_t6": {"AG_CRABEL15_D_1c": dict(target_r=5.0), "AG_TRD60_D_1c": dict(target_r=6.0)}}
out = {}
for k, mod in CELLS.items():
    out[k] = run(mod); print(k, out[k], flush=True)
json.dump(out, open(ROOT / "reports/PAYOUT_1_STEP3.json", "w"), indent=1, default=str); print("DONE", flush=True)

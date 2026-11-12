"""payout_34b (Claude, 2026-11-11): robustness DIAGNOSTICS for payout_34's adopted cell NC (noise sleeve, 1 micro at 4x). TRAINING only.
Nothing is selected here. (1) per-start-year gain vs F4X (S0 withdrawn); (2) the gain with the noise sleeve's 2018 trades removed (eval_12:
2018 is ~30% of its profit); (3) the gain with each calendar year's noise trades removed in turn (leave-one-year-out)."""
import json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/payout_34_noise_funded_sleeve_train.py").read_text(encoding="utf-8").split("\nout = dict(noise_trades")[0]
N = dict(__name__="payout_34b", __file__=str(ROOT / "scripts/payout_34_noise_funded_sleeve_train.py")); exec(src, N)
fc, PREP, STOP, tables_with, noise_book, NT, F4X = N["fc"], N["PREP"], N["STOP"], N["tables_with"], N["noise_book"], N["NT"], N["F4X"]
QC = {1: 0, 2: 0, 3: 0, 4: 1}
base = fc.replay({"base": fc.day_tables_path(*PREP["S0"][:3], STOP, PREP["S0"][3])}, **F4X)
REAL = noise_book(NT.side.to_numpy()); nc = fc.replay({"base": tables_with(REAL, "S0", QC)}, **F4X)
d = nc.usd - base.usd; yr = pd.to_datetime(base.start).dt.year
out = dict(per_start_year=d.groupby(yr).mean().round(0).to_dict(), windows_worse=int((d < -1).sum()), windows=len(d),
           mean_gain=round(float(d.mean()), 0), median_gain=round(float(d.median()), 0))
print(out, flush=True)
loo = {}
for y in sorted(set(NT.tout.dt.year)):
    keep = (NT.tout.dt.year != y).to_numpy()
    nb = REAL[keep].reset_index(drop=True)
    r = fc.summ(fc.replay({"base": tables_with(nb, "S0", QC)}, **F4X))
    loo[int(y)] = dict(usd=r["usd"], usd_h1=r["usd_h1"], usd_h2=r["usd_h2"])
    print("without", y, loo[int(y)], flush=True)
out["leave_one_year_out"] = loo
out["validation_accessed"] = False; out["test_accessed"] = False
(ROOT / "reports/PAYOUT_34B_NOISE_ROBUSTNESS_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
print("saved", flush=True)

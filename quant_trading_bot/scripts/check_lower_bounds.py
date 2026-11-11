import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/research_chameleon_fine_tune.py").read_text(encoding="utf-8")
V = {"__name__": "v55", "__file__": str(ROOT / "scripts/research_chameleon_fine_tune.py")}
exec(src.split("lad = ((0,1), (4000,2), (4600,3), (5400,4))")[0], V)
simulate = V["simulate"]
SER_BASE, RISK_BASE = V["SER_BASE"], V["RISK_BASE"]
SER_BOTH, RISK_BOTH = V["SER_BOTH"], V["RISK_BOTH"]
lad = ((0,1), (4000,2), (4600,3), (5400,4))

for k in [8000.0, 8100.0, 8200.0, 8300.0, 8350.0]:
    s3 = simulate(SER_BASE, RISK_BASE, SER_BOTH, RISK_BOTH, "S3", lad, k, k + 100.0, "sprint")
    s4 = simulate(SER_BASE, RISK_BASE, SER_BOTH, RISK_BOTH, "S4", lad, k, k + 100.0, "sprint")
    s0 = simulate(SER_BASE, RISK_BASE, SER_BOTH, RISK_BOTH, "S0", lad, k, k + 100.0, "sprint")
    print(f"K=${k:,.0f} Gate=${k+100:,.0f} -> USD: ${s0['usd']:,.0f} | S3: {s3['cons']*100:.1f}% | S4: {s4['cons']*100:.1f}%")

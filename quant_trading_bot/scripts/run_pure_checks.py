import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/research_chameleon_fine_tune.py").read_text(encoding="utf-8")
V = {"__name__": "v55", "__file__": str(ROOT / "scripts/research_chameleon_fine_tune.py")}
exec(src.split("lad = ((0,1), (4000,2), (4600,3), (5400,4))")[0], V)
simulate = V["simulate"]
SER_BASE = V["SER_BASE"]
RISK_BASE = V["RISK_BASE"]
SER_BOTH = V["SER_BOTH"]
RISK_BOTH = V["RISK_BOTH"]
lad = ((0,1), (4000,2), (4600,3), (5400,4))

for g in [8550.0, 8600.0, 8650.0, 8700.0]:
    s0 = simulate(SER_BASE, RISK_BASE, SER_BOTH, RISK_BOTH, "S0", lad, 8500.0, g, None, a0="2010-07-01", a1="2022-01-01")
    s3 = simulate(SER_BASE, RISK_BASE, SER_BOTH, RISK_BOTH, "S3", lad, 8500.0, g, None, a0="2010-07-01", a1="2022-01-01")
    s4 = simulate(SER_BASE, RISK_BASE, SER_BOTH, RISK_BOTH, "S4", lad, 8500.0, g, None, a0="2010-07-01", a1="2022-01-01")
    print(f"Pure Gate @ ${g:,.0f} -> USD: ${s0['usd']:,.0f} (H1: ${s0['usd_h1']:,.0f}, H2: ${s0['usd_h2']:,.0f}) | P1 Days: {s0['first_days']} | S3: {s3['cons']*100:.1f}% | S4: {s4['cons']*100:.1f}%")

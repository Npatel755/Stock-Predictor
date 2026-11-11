"""Audit Tier-3 threshold bounds between $9,000 and $10,000."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/research_chameleon_v3.py").read_text(encoding="utf-8")
V = {"__name__": "v3", "__file__": str(ROOT / "scripts/research_chameleon_v3.py")}
exec(src.split("tests = [")[0], V)

simulate_v3 = V["simulate_v3"]
lad_4x = V["lad_4x"]
SER_GAP = V["SER_GAP"]
RISK_GAP = V["RISK_GAP"]
base_h1, base_h2 = 18787.0, 33542.0

plateau = []
for g2 in [9200.0, 9400.0, 9500.0, 9600.0, 9700.0, 9800.0, 9900.0, 10000.0]:
    s0 = simulate_v3("S0", lad_4x, SER_GAP, RISK_GAP, 8400.0, 8500.0, g2)
    s3 = simulate_v3("S3", lad_4x, SER_GAP, RISK_GAP, 8400.0, 8500.0, g2)
    s4 = simulate_v3("S4", lad_4x, SER_GAP, RISK_GAP, 8400.0, 8500.0, g2)
    
    g1_p = (s0["usd_h1"] >= 1.05 * base_h1) and (s0["usd_h2"] >= 1.05 * base_h2)
    g2_p = (s0["closed"] <= 0.005)
    g3_p = (s3["cons"] <= 0.050) and (s4["cons"] <= 0.095)
    g4_p = (s0["near"] <= 0.007)
    
    passed = g1_p and g2_p and g3_p and g4_p
    status = "PASS" if passed else "FAIL"
    print(f"Tier-3 @ ${g2:,.0f} -> USD: ${s0['usd']:<7,.0f} | H1/H2: ${s0['usd_h1']:<6,.0f}/${s0['usd_h2']:<6,.0f} | S3: {s3['cons']*100:<4.1f}% | S4: {s4['cons']*100:<4.1f}% | {status}")
    plateau.append(dict(g2=g2, usd=s0["usd"], h1=s0["usd_h1"], h2=s0["usd_h2"], s3=s3["cons"], s4=s4["cons"], passed=passed))

(ROOT / "reports/RESEARCH_TIER3_PLATEAU.json").write_text(json.dumps(plateau, indent=2))

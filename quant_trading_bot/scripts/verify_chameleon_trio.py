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

candidates = [
    ("Baseline 2X (Keep $5.5k)", SER_BASE, RISK_BASE, ((0,1),(5000,2)), 5500.0, 1e9, None),
    ("Balanced 3X (Keep $6.5k)", SER_BASE, RISK_BASE, ((0,1),(4000,2),(5000,3)), 6500.0, 1e9, None),
    ("Base Fortress 4X (Keep $8.5k)", SER_BASE, RISK_BASE, ((0,1),(4000,2),(4800,3),(6000,4)), 8500.0, 1e9, None),
    ("Convex Pure 4X (Keep $8.5k)", SER_BASE, RISK_BASE, lad, 8500.0, 1e9, None),
    ("Convex Sprint 4X (Keep $8.5k, P1@$6k)", SER_BASE, RISK_BASE, lad, 8500.0, 1e9, "sprint"),
    ("Chameleon Crown Sprint ($8.4k K, Gate $8.5k)", SER_BASE, RISK_BASE, lad, 8400.0, 8500.0, "sprint"),
    ("Chameleon Fortified Sprint ($8.5k K, Gate $8.55k)", SER_BASE, RISK_BASE, lad, 8500.0, 8550.0, "sprint"),
    ("Chameleon Apex Pure ($8.5k K, Gate $8.55k)", SER_BASE, RISK_BASE, lad, 8500.0, 8550.0, None),
]

base_h1, base_h2 = 18787.0, 33542.0

final_rows = []
for name, sb, rb, ld, k_val, g_th, pacing in candidates:
    se, re = SER_BOTH, RISK_BOTH
    s0 = simulate(sb, rb, se, re, "S0", ld, k_val, g_th, pacing)
    s3 = simulate(sb, rb, se, re, "S3", ld, k_val, g_th, pacing)
    s4 = simulate(sb, rb, se, re, "S4", ld, k_val, g_th, pacing)
    
    g1 = (s0["usd_h1"] >= 1.05 * base_h1) and (s0["usd_h2"] >= 1.05 * base_h2)
    g2 = (s0["closed"] <= 0.005)
    g3 = (s3["cons"] <= 0.050) and (s4["cons"] <= 0.095)
    g4 = (s0["near"] <= 0.007)
    
    passed = g1 and g2 and g3 and g4
    
    final_rows.append(dict(
        name=name,
        usd=s0["usd"],
        usd_h1=s0["usd_h1"],
        usd_h2=s0["usd_h2"],
        usd_y1=s0["usd_y1"],
        y1_pays=s0["y1_pays"],
        p1_days=s0["first_days"],
        s0_ruin=s0["closed"],
        s3_cons=s3["cons"],
        s4_cons=s4["cons"],
        s0_near=s0["near"],
        passed=passed
    ))

out = ROOT / "reports/RESEARCH_FINAL_CHAMELEON_TRIO.json"
out.write_text(json.dumps(final_rows, indent=2), encoding="utf-8")
print("Saved final comparative verification to", out)

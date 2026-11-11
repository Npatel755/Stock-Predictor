import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/quant_futures"))
src = (ROOT / "scripts/research_chameleon_v3.py").read_text(encoding="utf-8")
V = {"__name__": "v3", "__file__": str(ROOT / "scripts/research_chameleon_v3.py")}
exec(src.split("tests = [")[0], V)

simulate_v3 = V["simulate_v3"]
lad_4x = V["lad_4x"]
SER_BASE, RISK_BASE = V["SER_BASE"], V["RISK_BASE"]
SER_BOTH, RISK_BOTH = V["SER_BOTH"], V["RISK_BOTH"]
SER_GAP, RISK_GAP = V["SER_GAP"], V["RISK_GAP"]

base_h1, base_h2 = 18787.0, 33542.0

configs = [
    ("Baseline 2X (Keep $5.5k)", lad_4x, SER_BASE, RISK_BASE, 5500.0, 1e9, 1e9, None, 0.0),
    ("Balanced 3X (Keep $6.5k)", lad_4x, SER_BASE, RISK_BASE, 6500.0, 1e9, 1e9, None, 0.0),
    ("Base Fortress 4X (Keep $8.5k)", lad_4x, SER_BASE, RISK_BASE, 8500.0, 1e9, 1e9, None, 0.0),
    ("Convex Sprint 4X (Keep $8.5k)", lad_4x, SER_BASE, RISK_BASE, 8500.0, 1e9, 1e9, 6000.0, 500.0),
    ("Chameleon Crown Sprint (2-Tier, $8.4k K, Gate $8.5k)", lad_4x, SER_BOTH, RISK_BOTH, 8400.0, 8500.0, 1e9, 6000.0, 500.0),
    ("Chameleon Apex 3-Tier (GAP @ $9.6k, K $8.4k)", lad_4x, SER_GAP, RISK_GAP, 8400.0, 8500.0, 9600.0, 6000.0, 500.0),
    ("Chameleon Apex 3-Tier (GAP @ $9.8k, K $8.4k)", lad_4x, SER_GAP, RISK_GAP, 8400.0, 8500.0, 9800.0, 6000.0, 500.0),
    ("Chameleon Apex 3-Tier (GAP @ $10.0k, K $8.4k)", lad_4x, SER_GAP, RISK_GAP, 8400.0, 8500.0, 10000.0, 6000.0, 500.0),
]

final_table = []
for name, ld, s_t2, r_t2, k_val, g1, g2, sp_bal, sp_amt in configs:
    s0 = simulate_v3("S0", ld, s_t2, r_t2, k_val, g1, g2, sp_bal, sp_amt)
    s3 = simulate_v3("S3", ld, s_t2, r_t2, k_val, g1, g2, sp_bal, sp_amt)
    s4 = simulate_v3("S4", ld, s_t2, r_t2, k_val, g1, g2, sp_bal, sp_amt)
    
    g1_p = (s0["usd_h1"] >= 1.05 * base_h1) and (s0["usd_h2"] >= 1.05 * base_h2)
    g2_p = (s0["closed"] <= 0.005)
    g3_p = (s3["cons"] <= 0.050) and (s4["cons"] <= 0.095)
    g4_p = (s0["near"] <= 0.007)
    
    passed = g1_p and g2_p and g3_p and g4_p
    
    final_table.append(dict(
        name=name,
        usd=s0["usd"],
        usd_h1=s0["usd_h1"],
        usd_h2=s0["usd_h2"],
        p1_days=s0["first_days"],
        y1_pays=s0["y1_pays"],
        usd_y1=s0["usd_y1"],
        s0_ruin=s0["closed"],
        s3_cons=s3["cons"],
        s4_cons=s4["cons"],
        s0_near=s0["near"],
        passed=passed
    ))

out = ROOT / "reports/RESEARCH_STRATOSPHERE_CHAMELEON.json"
out.write_text(json.dumps(final_table, indent=2))
print("Saved final Stratosphere verification to", out)

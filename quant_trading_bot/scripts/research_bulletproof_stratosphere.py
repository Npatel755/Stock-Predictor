"""Research: Bulletproof Stratosphere (Deep in Safe Interior, Far From Any Cliff)
Addressing Claude's exact critique:
1. "K 8,400 is $50 above your own S4 cliff at 8,350 - do not pick a value next to a cliff."
   -> Test K at $8,500, $8,600, $8,700, $8,800 (safely $150 to $450 deep inside the plateau).
2. Gate 1 judged against ADOPTED FORTRESS 4X ($24,895 H1 / $48,176 H2):
   -> Requires H1 >= $26,140 (+5.0%) and H2 >= $50,585 (+5.0%).
3. Tier-2 (Portfolio E: MNQ_BRK_E_2c + MES_MOM_3c) and Tier-3 (GAP: AG_CRABEL15_D_GAP_v53).
4. Sprint P1 @ $6,000 -$500 for rapid 221-day payback.
Tested across all 139 rolling 24m windows (2010-2023).
"""
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

fort_h1, fort_h2 = 24895.0, 48176.0
target_h1 = 1.05 * fort_h1  # $26,139.75
target_h2 = 1.05 * fort_h2  # $50,584.80

grid = []
for k_val in [8500.0, 8600.0, 8700.0, 8800.0]:
    for g1 in [k_val + 100.0, k_val + 200.0]:
        for g2 in [9800.0, 10000.0, 10200.0]:
            name = f"K=${k_val:,.0f}_G1=${g1:,.0f}_G2=${g2:,.0f}"
            grid.append((name, k_val, g1, g2))

print(f"{'Config Name':<32} | {'24m USD':<8} | {'H1/H2 USD':<15} | {'H1% / H2% vs Fort':<18} | {'S3cons':<6} | {'S4cons':<6} | {'Status'}")
print("="*95)

results = []
for name, k_val, g1, g2 in grid:
    s0 = simulate_v3("S0", lad_4x, SER_GAP, RISK_GAP, k_val, g1, g2, 6000.0, 500.0)
    s3 = simulate_v3("S3", lad_4x, SER_GAP, RISK_GAP, k_val, g1, g2, 6000.0, 500.0)
    s4 = simulate_v3("S4", lad_4x, SER_GAP, RISK_GAP, k_val, g1, g2, 6000.0, 500.0)
    
    # Gate 1 strictly vs Fortress 4X
    g1_p = (s0["usd_h1"] >= target_h1) and (s0["usd_h2"] >= target_h2)
    g2_p = (s0["closed"] <= 0.005)
    g3_p = (s3["cons"] <= 0.050) and (s4["cons"] <= 0.095)
    g4_p = (s0["near"] <= 0.007)
    
    passed = g1_p and g2_p and g3_p and g4_p
    status = "PASS" if passed else "FAIL"
    
    diff_h1 = (s0["usd_h1"] - fort_h1) / fort_h1 * 100
    diff_h2 = (s0["usd_h2"] - fort_h2) / fort_h2 * 100
    diff_str = f"{diff_h1:+.1f}% / {diff_h2:+.1f}%"
    
    print(f"{name:<32} | ${s0['usd']:<7,.0f} | ${s0['usd_h1']:<6,.0f}/${s0['usd_h2']:<6,.0f} | {diff_str:<18} | {s3['cons']*100:<5.1f}% | {s4['cons']*100:<5.1f}% | {status}")
    
    results.append(dict(
        name=name,
        k_val=k_val,
        g1=g1,
        g2=g2,
        usd=s0["usd"],
        usd_h1=s0["usd_h1"],
        usd_h2=s0["usd_h2"],
        diff_h1=diff_h1,
        diff_h2=diff_h2,
        p1_days=s0["first_days"],
        y1_pays=s0["y1_pays"],
        usd_y1=s0["usd_y1"],
        s0_ruin=s0["closed"],
        s3_cons=s3["cons"],
        s4_cons=s4["cons"],
        s0_near=s0["near"],
        passed=passed
    ))

out = ROOT / "reports/RESEARCH_BULLETPROOF_STRATOSPHERE.json"
out.write_text(json.dumps(results, indent=2))
print(f"\nSaved bulletproof sweep to {out}")

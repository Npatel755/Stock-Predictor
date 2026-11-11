"""Hyper-parameter sweep around Chameleon Sprint Peak.
Sweeps:
- Sprint trigger bal: $5,750, $6,000, $6,250 (amount: $500)
- Cushion K: $8,400, $8,500, $8,600
- Gate threshold: $8,550, $8,600, $8,650
"""
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

base_h1, base_h2 = 18787.0, 33542.0

grid = []
for k_val in [8400.0, 8500.0, 8600.0]:
    for sp_bal in [5750.0, 6000.0, 6250.0]:
        for g_th in [k_val + 50.0, k_val + 100.0]:
            name = f"K=${k_val:,.0f}_Sp=${sp_bal:,.0f}_Gate=${g_th:,.0f}"
            grid.append((name, k_val, sp_bal, g_th))

print(f"{'Config':<35} | {'24m USD':<8} | {'H1/H2 USD':<15} | {'P1 Days':<7} | {'S3cons':<6} | {'S4cons':<6} | {'Status'}")
print("="*85)

results = []
for name, k_val, sp_bal, g_th in grid:
    s0 = simulate(SER_BASE, RISK_BASE, SER_BOTH, RISK_BOTH, "S0", lad, k_val, g_th, "sprint", a0="2010-07-01", a1="2022-01-01")
    s3 = simulate(SER_BASE, RISK_BASE, SER_BOTH, RISK_BOTH, "S3", lad, k_val, g_th, "sprint", a0="2010-07-01", a1="2022-01-01")
    s4 = simulate(SER_BASE, RISK_BASE, SER_BOTH, RISK_BOTH, "S4", lad, k_val, g_th, "sprint", a0="2010-07-01", a1="2022-01-01")
    
    g1 = (s0["usd_h1"] >= 1.05 * base_h1) and (s0["usd_h2"] >= 1.05 * base_h2)
    g2 = (s0["closed"] <= 0.005)
    g3 = (s3["cons"] <= 0.050) and (s4["cons"] <= 0.095)
    g4 = (s0["near"] <= 0.007)
    
    passed = g1 and g2 and g3 and g4
    status = "PASS" if passed else "FAIL"
    
    print(f"{name:<35} | ${s0['usd']:<7,.0f} | ${s0['usd_h1']:<6,.0f}/${s0['usd_h2']:<6,.0f} | {s0['first_days']:<7.1f} | {s3['cons']*100:<5.1f}% | {s4['cons']*100:<5.1f}% | {status}")
    
    results.append(dict(
        name=name,
        k_val=k_val,
        sp_bal=sp_bal,
        g_th=g_th,
        usd=s0["usd"],
        usd_h1=s0["usd_h1"],
        usd_h2=s0["usd_h2"],
        p1_days=s0["first_days"],
        s3_cons=s3["cons"],
        s4_cons=s4["cons"],
        passed=passed
    ))

out_path = ROOT / "reports/RESEARCH_CHAMELEON_HYPER_SWEEP.json"
out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
print(f"\nSaved hyper sweep to {out_path}")

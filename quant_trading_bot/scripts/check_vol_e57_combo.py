import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/quant_futures"))
src = (ROOT / "scripts/research_uncapped_and_sleeves.py").read_text(encoding="utf-8")
V = {"__name__": "v", "__file__": str(ROOT / "scripts/research_uncapped_and_sleeves.py")}
exec(src.split("tests = [")[0], V)

simulate_advanced = V["simulate_advanced"]
build_tables = V["build_tables"]
df_base = V["df_base"]
slv_brk = V["slv_brk"]
slv_mom = V["slv_mom"]
slv_gap = V["slv_gap"]
slv_vol = V["slv_vol"]
slv_e57 = V["slv_e57"]
lad_4x = V["lad_4x"]
fort_h1, fort_h2 = 24895.0, 48176.0

# Build combo dataframe
df_combo = pd.concat([df_base, slv_brk, slv_mom, slv_gap, slv_vol, slv_e57], ignore_index=True)
SER_COMBO, RISK_COMBO = build_tables(df_combo)

combos = [
    ("GAP + VOL (Benchmark)", V["SER_VOL"], V["RISK_VOL"]),
    ("GAP + VOL + E57 (Triple Boost)", SER_COMBO, RISK_COMBO),
]

for name, s_t2, r_t2 in combos:
    s0 = simulate_advanced("S0", lad_4x, s_t2, r_t2, 8600.0, 8700.0, 10000.0, 1500.0)
    s3 = simulate_advanced("S3", lad_4x, s_t2, r_t2, 8600.0, 8700.0, 10000.0, 1500.0)
    s4 = simulate_advanced("S4", lad_4x, s_t2, r_t2, 8600.0, 8700.0, 10000.0, 1500.0)
    
    diff_h1 = (s0["usd_h1"] - fort_h1) / fort_h1 * 100
    diff_h2 = (s0["usd_h2"] - fort_h2) / fort_h2 * 100
    passed = (s0["usd_h1"] >= 1.05 * fort_h1) and (s0["usd_h2"] >= 1.05 * fort_h2) and (s3["cons"] <= 0.050) and (s4["cons"] <= 0.095)
    print(f"{name:<30} | 24m: ${s0['usd']:<7,.0f} | H1/H2: ${s0['usd_h1']:<6,.0f} ({diff_h1:+.1f}%) / ${s0['usd_h2']:<6,.0f} ({diff_h2:+.1f}%) | S3: {s3['cons']*100:.1f}% | S4: {s4['cons']*100:.1f}% | Passed: {passed}")

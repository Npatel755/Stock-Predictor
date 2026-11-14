import sys
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/quant_futures"))

src = (ROOT / "scripts/research_uncapped_and_sleeves.py").read_text(encoding="utf-8")
V = {"__name__": "v", "__file__": str(ROOT / "scripts/research_uncapped_and_sleeves.py")}
exec(src.split("tests = [")[0], V)

simulate_advanced = V["simulate_advanced"]
build_tables = V["build_tables"]
lad_4x = V["lad_4x"]
fort_h1, fort_h2 = 24895.0, 48176.0

P10 = V["P10"]
ep, bars_for, START = P10["ep"], P10["bars_for"], P10["START"]
df_base = V["df_base"]
base_cols = df_base.columns
pl = V["pl"]

def get_sleeve(name, key, prio=15):
    sl = next(s for s in ep.CANDIDATES[key]["sleeves"] if s["name"] == name)
    x = pl.price_normalize(pl.sleeve_trades(ep, bars_for, START, dict(sl), prio, False))
    x["n_contracts"] = 1.0
    x["mae_per_micro"] = 0.0
    return x[base_cols]

slv_brk = V["slv_brk"]
slv_mom = V["slv_mom"]
slv_gap = V["slv_gap"]
slv_vol = V["slv_vol"]
slv_brk30 = get_sleeve("AG_BRK30_1c", "ag_all_weather", 16)
slv_morn30 = get_sleeve("AG_MORN30_1c", "ag_quad", 17)
slv_trd30pm = get_sleeve("AG_TRD30PM_1c_v52", "ag_arch_d_plus_v2_1c_v52", 18)
slv_trd60q = get_sleeve("AG_TRD60Q_1c", "ag_quad", 19)
slv_mes_mom = get_sleeve("MES_MOM_1c", "ensemble_epsilon", 20)
slv_trd60_d = get_sleeve("AG_TRD60_D_1c_v53", "ag_arch_d_plus_v2_1c_v53", 21)

# Apex Sextet
df_apex = pd.concat([df_base, slv_brk, slv_mom, slv_gap, slv_vol,
                     slv_brk30, slv_morn30, slv_trd30pm, slv_trd60q,
                     slv_mes_mom, slv_trd60_d], ignore_index=True)
s_tab, r_tab = build_tables(df_apex)

print("="*80)
print("Scanning G for Apex Sextet (K=8600)")
print("="*80)
for g in [8600.0, 8625.0, 8650.0, 8675.0, 8700.0, 8750.0]:
    s0 = simulate_advanced("S0", lad_4x, s_tab, r_tab, 8600.0, g, g, 1500.0)
    s3 = simulate_advanced("S3", lad_4x, s_tab, r_tab, 8600.0, g, g, 1500.0)
    s4 = simulate_advanced("S4", lad_4x, s_tab, r_tab, 8600.0, g, g, 1500.0)
    h1_pct = (s0["usd_h1"] - fort_h1) / fort_h1 * 100
    h2_pct = (s0["usd_h2"] - fort_h2) / fort_h2 * 100
    near = s0.get("near", 0.0)
    passed = (s0["usd_h1"] >= 1.05 * fort_h1) and (s0["usd_h2"] >= 1.05 * fort_h2) and (s3["cons"] <= 0.050) and (s4["cons"] <= 0.095)
    print(f"G=${g:,.0f} | 24m: ${s0['usd']:<7,.0f} | H1: ${s0['usd_h1']:<6,.0f} ({h1_pct:+.1f}%) | H2: ${s0['usd_h2']:<6,.0f} ({h2_pct:+.1f}%) | Y1: ${s0['usd_y1']:<6,.0f} | Near: {near*100:.1f}% | S3: {s3['cons']*100:.1f}% | S4: {s4['cons']*100:.1f}% | {passed}")

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

# Build BRK30 + MORN30 champion dataframe
df_champ = pd.concat([df_base, slv_brk, slv_mom, slv_gap, slv_vol, slv_brk30, slv_morn30], ignore_index=True)
SER_CH, RISK_CH = build_tables(df_champ)

# ---- PART 1: Gate2 scan for BRK30 + MORN30 ----
print("="*80)
print("PART 1: Gate2 scan for BRK30 + MORN30 (K=8600, G1=8700)")
print("="*80)
for g2 in [9000.0, 9200.0, 9400.0, 9600.0, 9800.0, 10000.0, 10200.0]:
    s0 = simulate_advanced("S0", lad_4x, SER_CH, RISK_CH, 8600.0, 8700.0, g2, 1500.0)
    s3 = simulate_advanced("S3", lad_4x, SER_CH, RISK_CH, 8600.0, 8700.0, g2, 1500.0)
    s4 = simulate_advanced("S4", lad_4x, SER_CH, RISK_CH, 8600.0, 8700.0, g2, 1500.0)
    h1_pct = (s0["usd_h1"] - fort_h1) / fort_h1 * 100
    h2_pct = (s0["usd_h2"] - fort_h2) / fort_h2 * 100
    near = s0.get("near", 0.0)
    passed = (s0["usd_h1"] >= 1.05 * fort_h1) and (s0["usd_h2"] >= 1.05 * fort_h2) and (s3["cons"] <= 0.050) and (s4["cons"] <= 0.095)
    print(f"G2=${g2:,.0f} | 24m: ${s0['usd']:<7,.0f} | H1: ${s0['usd_h1']:<6,.0f} ({h1_pct:+.1f}%) | H2: ${s0['usd_h2']:<6,.0f} ({h2_pct:+.1f}%) | Y1: ${s0['usd_y1']:<6,.0f} | P1d: {s0['first_days']:.0f} | Near: {near*100:.1f}% | S3: {s3['cons']*100:.1f}% | S4: {s4['cons']*100:.1f}% | {passed}")

# ---- PART 2: K / Gate1 sensitivity for BRK30 + MORN30 at Gate2=9600 ----
print()
print("="*80)
print("PART 2: K / Gate1 sensitivity for BRK30 + MORN30 at Gate2=9600")
print("="*80)
for K in [8400.0, 8500.0, 8600.0, 8700.0, 8800.0]:
    g1 = K + 100.0
    s0 = simulate_advanced("S0", lad_4x, SER_CH, RISK_CH, K, g1, 9600.0, 1500.0)
    s3 = simulate_advanced("S3", lad_4x, SER_CH, RISK_CH, K, g1, 9600.0, 1500.0)
    s4 = simulate_advanced("S4", lad_4x, SER_CH, RISK_CH, K, g1, 9600.0, 1500.0)
    h1_pct = (s0["usd_h1"] - fort_h1) / fort_h1 * 100
    h2_pct = (s0["usd_h2"] - fort_h2) / fort_h2 * 100
    near = s0.get("near", 0.0)
    passed = (s0["usd_h1"] >= 1.05 * fort_h1) and (s0["usd_h2"] >= 1.05 * fort_h2) and (s3["cons"] <= 0.050) and (s4["cons"] <= 0.095)
    print(f"K=${K:,.0f} G1=${g1:,.0f} | 24m: ${s0['usd']:<7,.0f} | H1: ${s0['usd_h1']:<6,.0f} ({h1_pct:+.1f}%) | H2: ${s0['usd_h2']:<6,.0f} ({h2_pct:+.1f}%) | Y1: ${s0['usd_y1']:<6,.0f} | P1d: {s0['first_days']:.0f} | Near: {near*100:.1f}% | S3: {s3['cons']*100:.1f}% | S4: {s4['cons']*100:.1f}% | {passed}")

# ---- PART 3: What if we add TRD30PM too at the best Gate2? ----
print()
print("="*80)
print("PART 3: Triple stack (BRK30 + MORN30 + TRD30PM) Gate2 scan")
print("="*80)
slv_trd30pm = get_sleeve("AG_TRD30PM_1c_v52", "ag_arch_d_plus_v2_1c_v52", 18)
df_triple = pd.concat([df_base, slv_brk, slv_mom, slv_gap, slv_vol, slv_brk30, slv_morn30, slv_trd30pm], ignore_index=True)
SER_T3, RISK_T3 = build_tables(df_triple)
for g2 in [9000.0, 9200.0, 9400.0, 9600.0, 9800.0]:
    s0 = simulate_advanced("S0", lad_4x, SER_T3, RISK_T3, 8600.0, 8700.0, g2, 1500.0)
    s3 = simulate_advanced("S3", lad_4x, SER_T3, RISK_T3, 8600.0, 8700.0, g2, 1500.0)
    s4 = simulate_advanced("S4", lad_4x, SER_T3, RISK_T3, 8600.0, 8700.0, g2, 1500.0)
    h1_pct = (s0["usd_h1"] - fort_h1) / fort_h1 * 100
    h2_pct = (s0["usd_h2"] - fort_h2) / fort_h2 * 100
    near = s0.get("near", 0.0)
    passed = (s0["usd_h1"] >= 1.05 * fort_h1) and (s0["usd_h2"] >= 1.05 * fort_h2) and (s3["cons"] <= 0.050) and (s4["cons"] <= 0.095)
    print(f"G2=${g2:,.0f} | 24m: ${s0['usd']:<7,.0f} | H1: ${s0['usd_h1']:<6,.0f} ({h1_pct:+.1f}%) | H2: ${s0['usd_h2']:<6,.0f} ({h2_pct:+.1f}%) | Y1: ${s0['usd_y1']:<6,.0f} | P1d: {s0['first_days']:.0f} | Near: {near*100:.1f}% | S3: {s3['cons']*100:.1f}% | S4: {s4['cons']*100:.1f}% | {passed}")

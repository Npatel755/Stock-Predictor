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

# Test other sleeves:
candidates_to_test = [
    ("AG_TRD30PM_1c_v52", "ag_arch_d_plus_v2_1c_v52"),
    ("AG_BRK30_1c", "ag_all_weather"),
    ("AG_MORN30_1c", "ag_quad"),
]

results = []
for sname, skey in candidates_to_test:
    try:
        slv_test = get_sleeve(sname, skey, 15)
        df_test = pd.concat([df_base, slv_brk, slv_mom, slv_gap, slv_vol, slv_test], ignore_index=True)
        s_tab, r_tab = build_tables(df_test)
        s0 = simulate_advanced("S0", lad_4x, s_tab, r_tab, 8600.0, 8700.0, 9600.0, 1500.0)
        s3 = simulate_advanced("S3", lad_4x, s_tab, r_tab, 8600.0, 8700.0, 9600.0, 1500.0)
        s4 = simulate_advanced("S4", lad_4x, s_tab, r_tab, 8600.0, 8700.0, 9600.0, 1500.0)
        h1_pct = (s0["usd_h1"] - fort_h1) / fort_h1 * 100
        h2_pct = (s0["usd_h2"] - fort_h2) / fort_h2 * 100
        passed = (s0["usd_h1"] >= 1.05 * fort_h1) and (s0["usd_h2"] >= 1.05 * fort_h2) and (s3["cons"] <= 0.050) and (s4["cons"] <= 0.095)
        print(f"{sname:<25} | 24m: ${s0['usd']:<7,.0f} | H1: ${s0['usd_h1']:<6,.0f} ({h1_pct:+.1f}%) | H2: ${s0['usd_h2']:<6,.0f} ({h2_pct:+.1f}%) | S3: {s3['cons']*100:.1f}% | S4: {s4['cons']*100:.1f}% | Passed: {passed}")
    except Exception as e:
        print(f"{sname} failed: {e}")

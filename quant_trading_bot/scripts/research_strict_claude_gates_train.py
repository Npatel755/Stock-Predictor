"""Research Strict Claude Gates (Training 2010-2023):
Testing whether a conservative 3-tier or 4-tier ladder (with high floor protection)
can beat Claude's live baseline (4) by >= +5% in BOTH halves while STRICTLY passing
all four of Claude's gates:
  1. Dollars >= baseline x 1.05 in BOTH halves (2010-16 AND 2017-23).
  2. Nominal closure (S0, S3, S4) <= baseline + 0.005.
  3. Conservative closure (S0, S3, S4) <= baseline + 0.02.
  4. S0 near-miss <= baseline.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

# Import v55 environment directly
import v55_check_aegis_train as v55

build = v55.build
cell = v55.cell
v53 = v55.V["variant"]("A")  # v5.3 book (no TRD30PM, 09:45 exit)

print("Building cap-aware lookup tables for v5.3 book...")
SER_CAP, RISK_CAP = build(v53, cap_aware=True)

# 1. Baseline: Live paper account (4) - current ladder 2x @ $4k, K=$6k, cap-aware
base_ladder = [(0, 1), (4000, 2)]
base_K = 6000.0
base_res = cell(SER_CAP, RISK_CAP, base_ladder, base_K)

print("\n--- BASELINE (Current Live Paper Model: 2x @ $4k, K=$6k, Cap-Aware) ---")
print(f"S0: ${base_res['S0']['usd']:,.0f} | Closed: {base_res['S0']['closed']} | Cons: {base_res['S0']['cons']} | Near: {base_res['S0']['near']}")
print(f"S3: ${base_res['S3']['usd']:,.0f} | Closed: {base_res['S3']['closed']} | Cons: {base_res['S3']['cons']}")
print(f"S4: ${base_res['S4']['usd']:,.0f} | Closed: {base_res['S4']['closed']} | Cons: {base_res['S4']['cons']}")
print(f"Halves: H1 ${base_res['half1']['usd']:,.0f} | H2 ${base_res['half2']['usd']:,.0f}")

# Target hurdles based on Claude's pre-declared gates:
h1_target = base_res['half1']['usd'] * 1.05
h2_target = base_res['half2']['usd'] * 1.05
s0_closed_max = base_res['S0']['closed'] + 0.005
s3_closed_max = base_res['S3']['closed'] + 0.005
s4_closed_max = base_res['S4']['closed'] + 0.005
s0_cons_max = base_res['S0']['cons'] + 0.02
s3_cons_max = base_res['S3']['cons'] + 0.02
s4_cons_max = base_res['S4']['cons'] + 0.02
s0_near_max = base_res['S0']['near']

print(f"\nHurdles to ADOPT:")
print(f"  H1 Target: >= ${h1_target:,.0f} | H2 Target: >= ${h2_target:,.0f}")
print(f"  Max Closures: S0 <= {s0_closed_max:.3f}, S3 <= {s3_closed_max:.3f}, S4 <= {s4_closed_max:.3f}")
print(f"  Max Cons Closures: S0 <= {s0_cons_max:.3f}, S3 <= {s3_cons_max:.3f}, S4 <= {s4_cons_max:.3f}")
print(f"  Max Near-Miss: S0 <= {s0_near_max:.3f}")

# Sweep candidate configurations
candidates = [
    # Conservative 3x with 1x all the way up to $4k
    ("3x @ $6.0k (1x <$4k, 2x $4k-$6k, 3x >=$6k | K=$6.5k)", [(0, 1), (4000, 2), (6000, 3)], 6500.0),
    ("3x @ $6.0k (1x <$4k, 2x $4k-$6k, 3x >=$6k | K=$7.0k)", [(0, 1), (4000, 2), (6000, 3)], 7000.0),
    ("3x @ $6.0k (1x <$4k, 2x $4k-$6k, 3x >=$6k | K=$7.5k)", [(0, 1), (4000, 2), (6000, 3)], 7500.0),
    ("3x @ $5.5k (1x <$4k, 2x $4k-$5.5k, 3x >=$5.5k | K=$6.5k)", [(0, 1), (4000, 2), (5500, 3)], 6500.0),
    ("3x @ $5.5k (1x <$4k, 2x $4k-$5.5k, 3x >=$5.5k | K=$7.0k)", [(0, 1), (4000, 2), (5500, 3)], 7000.0),
    ("3x @ $5.0k (1x <$4k, 2x $4k-$5k, 3x >=$5k | K=$6.5k)", [(0, 1), (4000, 2), (5000, 3)], 6500.0),
    ("3x @ $5.0k (1x <$4k, 2x $4k-$5k, 3x >=$5k | K=$7.0k)", [(0, 1), (4000, 2), (5000, 3)], 7000.0),
    # Slightly earlier 2x (at $3.5k or $3.8k) with strict 3x
    ("2x @ $3.5k, 3x @ $6.0k | K=$6.5k", [(0, 1), (3500, 2), (6000, 3)], 6500.0),
    ("2x @ $3.5k, 3x @ $6.0k | K=$7.0k", [(0, 1), (3500, 2), (6000, 3)], 7000.0),
    ("2x @ $3.8k, 3x @ $5.8k | K=$6.5k", [(0, 1), (3800, 2), (5800, 3)], 6500.0),
    ("2x @ $3.8k, 3x @ $5.8k | K=$7.0k", [(0, 1), (3800, 2), (5800, 3)], 7000.0),
    # 4-tier with high floors
    ("4-tier: 1x <$4k, 2x $4k-$6k, 3x $6k-$8k, 4x >=$8k | K=$8.0k", [(0, 1), (4000, 2), (6000, 3), (8000, 4)], 8000.0),
    ("4-tier: 1x <$4k, 2x $4k-$6k, 3x $6k-$8k, 4x >=$8k | K=$8.5k", [(0, 1), (4000, 2), (6000, 3), (8000, 4)], 8500.0),
    # Pure 2x with higher cushions
    ("Pure 2x @ $4k | K=$6.5k", [(0, 1), (4000, 2)], 6500.0),
    ("Pure 2x @ $4k | K=$7.0k", [(0, 1), (4000, 2)], 7000.0),
]

print("\n--- RUNNING CANDIDATE EVALUATION ACROSS ALL GATES ---")
results = []
passers = []

for name, lad, K_val in candidates:
    res = cell(SER_CAP, RISK_CAP, lad, K_val)
    
    # Gate checks
    gate1_h1 = res['half1']['usd'] >= h1_target
    gate1_h2 = res['half2']['usd'] >= h2_target
    gate1 = gate1_h1 and gate1_h2
    
    gate2 = (res['S0']['closed'] <= s0_closed_max and 
             res['S3']['closed'] <= s3_closed_max and 
             res['S4']['closed'] <= s4_closed_max)
             
    gate3 = (res['S0']['cons'] <= s0_cons_max and 
             res['S3']['cons'] <= s3_cons_max and 
             res['S4']['cons'] <= s4_cons_max)
             
    gate4 = res['S0']['near'] <= s0_near_max
    
    all_passed = gate1 and gate2 and gate3 and gate4
    
    row = dict(
        name=name,
        ladder=lad,
        cushion=K_val,
        s0_usd=res['S0']['usd'],
        s0_gain_pct=round((res['S0']['usd'] / base_res['S0']['usd'] - 1) * 100, 1),
        h1_usd=res['half1']['usd'],
        h1_gain_pct=round((res['half1']['usd'] / base_res['half1']['usd'] - 1) * 100, 1),
        h2_usd=res['half2']['usd'],
        h2_gain_pct=round((res['half2']['usd'] / base_res['half2']['usd'] - 1) * 100, 1),
        s0_closed=res['S0']['closed'],
        s3_closed=res['S3']['closed'],
        s4_closed=res['S4']['closed'],
        s0_cons=res['S0']['cons'],
        s3_cons=res['S3']['cons'],
        s4_cons=res['S4']['cons'],
        s0_near=res['S0']['near'],
        gate1_both_halves=gate1,
        gate2_closures=gate2,
        gate3_conservative=gate3,
        gate4_near_miss=gate4,
        ALL_GATES_PASSED=all_passed,
    )
    results.append(row)
    if all_passed:
        passers.append(row)
        
    status = "PASSED ALL GATES!" if all_passed else ("FAIL G1" if not gate1 else ("FAIL G2" if not gate2 else ("FAIL G3" if not gate3 else "FAIL G4")))
    print(f"[{status}] {name}")
    print(f"     S0: ${res['S0']['usd']:,.0f} (+{row['s0_gain_pct']}%) | H1: ${res['half1']['usd']:,.0f} (+{row['h1_gain_pct']}%) | H2: ${res['half2']['usd']:,.0f} (+{row['h2_gain_pct']}%)")
    print(f"     S3: Closed {res['S3']['closed']} (Cons: {res['S3']['cons']}) | S4: Closed {res['S4']['closed']} (Cons: {res['S4']['cons']})")

df_res = pd.DataFrame(results)
out_path = ROOT / "reports/RESEARCH_STRICT_CLAUDE_GATES_TRAINING.json"
out_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
print(f"\nSaved report to {out_path}")

print(f"\nTOTAL CONFIGURATIONS PASSING ALL FOUR GATES: {len(passers)}")
if passers:
    print("\n--- WINNING CONFIGURATIONS THAT PASS EVERY SINGLE GATE ---")
    df_pass = pd.DataFrame(passers).sort_values(by="s0_usd", ascending=False)
    print(df_pass[["name", "s0_usd", "s0_gain_pct", "h1_gain_pct", "h2_gain_pct", "s3_cons", "s4_cons"]].to_string(index=False))

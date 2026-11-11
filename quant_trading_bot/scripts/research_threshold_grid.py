"""Threshold Fine-Tuning Grid:
Testing:
1. P1 Milestone at $5,000 / $5,200 / $5,500 (withdraw $500)
2. P2 Milestone at $6,500 / $6,800 / $7,000 (withdraw $500)
3. 3x tier at $4,500 / $4,600 / $4,800
4. 4x tier at $5,200 / $5,400 / $5,600 / $5,800
All with steady cushion K = $8,500 and Stop = $700.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import research_improve_option2_further as r

candidates = [
    # Baseline Option 2 Apex
    ("Apex Base (3x@4.8k, 4x@5.8k | P1@5.5k, P2@7.0k)", ((0,1), (4000,2), (4800,3), (5800,4)), 8500.0, [(5500.0, 500.0), (7000.0, 500.0)]),
    
    # Accelerated Milestone 1 ($5,000 / $5,200)
    ("Ultra-Fast P1 (P1@5.0k -$500, P2@7.0k -$500)", ((0,1), (4000,2), (4800,3), (5800,4)), 8500.0, [(5000.0, 500.0), (7000.0, 500.0)]),
    ("Ultra-Fast P1 (P1@5.2k -$500, P2@7.0k -$500)", ((0,1), (4000,2), (4800,3), (5800,4)), 8500.0, [(5200.0, 500.0), (7000.0, 500.0)]),
    
    # Milestone 1 + Accelerated Milestone 2 ($6,500 / $6,800)
    ("Tuned Milestones (P1@5.2k -$500, P2@6.5k -$500)", ((0,1), (4000,2), (4800,3), (5800,4)), 8500.0, [(5200.0, 500.0), (6500.0, 500.0)]),
    ("Tuned Milestones (P1@5.5k -$500, P2@6.5k -$500)", ((0,1), (4000,2), (4800,3), (5800,4)), 8500.0, [(5500.0, 500.0), (6500.0, 500.0)]),
    
    # Accelerated Ladder Tiers (3x @ $4.6k, 4x @ $5.4k)
    ("Convex Ladder (3x@4.6k, 4x@5.4k | P1@5.5k, P2@7.0k)", ((0,1), (4000,2), (4600,3), (5400,4)), 8500.0, [(5500.0, 500.0), (7000.0, 500.0)]),
    ("Convex Ladder (3x@4.6k, 4x@5.4k | P1@5.2k, P2@6.8k)", ((0,1), (4000,2), (4600,3), (5400,4)), 8500.0, [(5200.0, 500.0), (6800.0, 500.0)]),
    ("Convex Ladder (3x@4.5k, 4x@5.5k | P1@5.2k, P2@6.8k)", ((0,1), (4000,2), (4500,3), (5500,4)), 8500.0, [(5200.0, 500.0), (6800.0, 500.0)]),
    
    # Pure Ladder Variants without Milestones
    ("Convex Pure (3x@4.6k, 4x@5.4k | K=$8.5k)", ((0,1), (4000,2), (4600,3), (5400,4)), 8500.0, None),
    ("Convex Pure (3x@4.5k, 4x@5.5k | K=$8.5k)", ((0,1), (4000,2), (4500,3), (5500,4)), 8500.0, None),
]

results = []
for name, lad, K, ms in candidates:
    res = r.eval_full(name, r.SER_BASE, r.RISK_BASE, lad, K, ms)
    results.append(res)
    safe = (res["s3_cons"] <= 0.05 and res["s4_cons"] <= 0.095 and res["s0_closed"] == 0.0 and res["s3_closed"] <= 0.022 and res["s4_closed"] <= 0.065)
    status = "[PASS]" if safe else "[FAIL]"
    print(f"\n{status} {name}")
    print(f"   24m: ${res['s0_usd']:,.0f} (H1: ${res['h1_usd']:,.0f} | H2: ${res['h2_usd']:,.0f})")
    print(f"   Y1: ${res['s0_y1_usd']:,.0f} ({res['s0_y1_pays']} pays) | P1 Days: {res['first_days']} cal days")
    print(f"   Risk: S0 ruin {res['s0_closed']*100:.1f}% | S3 cons {res['s3_cons']*100:.1f}% | S4 cons {res['s4_cons']*100:.1f}%")

out_file = ROOT / "reports/RESEARCH_THRESHOLD_GRID_RESULTS.json"
out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
print(f"\nSaved to {out_file}")

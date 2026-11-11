import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import research_improve_option2_further as r

candidates = [
    # Fine-tuning 4x threshold with Milestones (P1 @ 5.5k, P2 @ 7.0k)
    ("Milestone A + 4x@$5.6k", ((0,1), (4000,2), (4800,3), (5600,4)), 8500.0, [(5500.0, 500.0), (7000.0, 500.0)]),
    ("Milestone A + 4x@$5.5k", ((0,1), (4000,2), (4800,3), (5500,4)), 8500.0, [(5500.0, 500.0), (7000.0, 500.0)]),
    ("Milestone A + 4x@$5.7k", ((0,1), (4000,2), (4800,3), (5700,4)), 8500.0, [(5500.0, 500.0), (7000.0, 500.0)]),
    
    # Fine-tuning Single Early P1 ($6.0k -$500) with Convex Ladder (3x@4.6k, 4x@5.4k)
    ("Convex Ladder + P1@$6.0k -$500", ((0,1), (4000,2), (4600,3), (5400,4)), 8500.0, [(6000.0, 500.0)]),
    ("Convex Ladder + P1@$6.0k -$500 (3x@4.7k, 4x@5.5k)", ((0,1), (4000,2), (4700,3), (5500,4)), 8500.0, [(6000.0, 500.0)]),
]

for name, lad, K, ms in candidates:
    res = r.eval_full(name, r.SER_BASE, r.RISK_BASE, lad, K, ms)
    safe = (res["s3_cons"] <= 0.05 and res["s4_cons"] <= 0.095 and res["s0_closed"] == 0.0)
    print(f"\n{'[PASS]' if safe else '[FAIL]'} {name}")
    print(f"  24m USD: ${res['s0_usd']:,.0f} (H1: ${res['h1_usd']:,.0f} | H2: ${res['h2_usd']:,.0f})")
    print(f"  Y1 USD: ${res['s0_y1_usd']:,.0f} | Y1 Pays: {res['s0_y1_pays']} | P1 Days: {res['first_days']} cal days")
    print(f"  Risk: S0 ruin {res['s0_closed']*100:.1f}% | S3 cons {res['s3_cons']*100:.1f}% | S4 cons {res['s4_cons']*100:.1f}%")

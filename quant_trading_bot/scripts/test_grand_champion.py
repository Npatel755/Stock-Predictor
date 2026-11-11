import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import research_improve_option2_further as r

candidates = [
    ("Grand Champion: Multi-Milestone + Night Cap 2c", r.SER_NC2, r.RISK_NC2, ((0,1), (4000,2), (4800,3), (5800,4)), 8500.0, [(5500.0, 500.0), (7000.0, 500.0)]),
    ("Grand Champion: P1 @ $6k -$500 + Night Cap 2c", r.SER_NC2, r.RISK_NC2, ((0,1), (4000,2), (4800,3), (5800,4)), 8500.0, [(6000.0, 500.0)]),
    ("Grand Champion: Pure Fast-4X + Night Cap 2c", r.SER_NC2, r.RISK_NC2, ((0,1), (4000,2), (4800,3), (5800,4)), 8500.0, None),
]

for name, ser, risk, lad, K, ms in candidates:
    res = r.eval_full(name, ser, risk, lad, K, ms)
    print(f"\n--- {name} ---")
    print(f"  24m USD: ${res['s0_usd']:,.0f} (H1: ${res['h1_usd']:,.0f} | H2: ${res['h2_usd']:,.0f})")
    print(f"  Y1 USD: ${res['s0_y1_usd']:,.0f} | Y1 Pays: {res['s0_y1_pays']} | P1 Days: {res['first_days']} cal days")
    print(f"  Risk: S0 ruin {res['s0_closed']*100:.1f}% | S3 cons {res['s3_cons']*100:.1f}% | S4 cons {res['s4_cons']*100:.1f}%")

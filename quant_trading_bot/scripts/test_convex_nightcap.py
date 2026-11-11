import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import research_improve_option2_further as r

res = r.eval_full("Convex Pure + Night Cap 2c", r.SER_NC2, r.RISK_NC2, ((0,1), (4000,2), (4600,3), (5400,4)), 8500.0, None)
print(f"Convex Pure + Night Cap 2c:")
print(f"  24m USD: ${res['s0_usd']:,.0f} (H1: ${res['h1_usd']:,.0f} | H2: ${res['h2_usd']:,.0f})")
print(f"  Y1 USD: ${res['s0_y1_usd']:,.0f} | Y1 Pays: {res['s0_y1_pays']} | P1 Days: {res['first_days']} cal days")
print(f"  Risk: S0 ruin {res['s0_closed']*100:.1f}% | S3 cons {res['s3_cons']*100:.1f}% | S4 cons {res['s4_cons']*100:.1f}%")

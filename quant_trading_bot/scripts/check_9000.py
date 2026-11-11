import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/quant_futures"))
src = (ROOT / "scripts/research_chameleon_v3.py").read_text(encoding="utf-8")
V = {"__name__": "v3", "__file__": str(ROOT / "scripts/research_chameleon_v3.py")}
exec(src.split("tests = [")[0], V)
simulate_v3 = V["simulate_v3"]
lad_4x = V["lad_4x"]
SER_GAP, RISK_GAP = V["SER_GAP"], V["RISK_GAP"]
for g2 in [8800.0, 9000.0]:
    s0 = simulate_v3("S0", lad_4x, SER_GAP, RISK_GAP, 8400.0, 8500.0, g2)
    s3 = simulate_v3("S3", lad_4x, SER_GAP, RISK_GAP, 8400.0, 8500.0, g2)
    s4 = simulate_v3("S4", lad_4x, SER_GAP, RISK_GAP, 8400.0, 8500.0, g2)
    print(f"Tier-3 @ ${g2:,.0f} -> USD: ${s0['usd']:<7,.0f} | S3: {s3['cons']*100:.1f}% | S4: {s4['cons']*100:.1f}%")

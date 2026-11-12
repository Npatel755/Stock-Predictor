import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/quant_futures"))

src = (ROOT / "scripts/research_uncapped_and_sleeves.py").read_text(encoding="utf-8")
V = {"__name__": "v", "__file__": str(ROOT / "scripts/research_uncapped_and_sleeves.py")}
exec(src.split("tests = [")[0], V)

simulate_advanced = V["simulate_advanced"]
lad_4x = V["lad_4x"]
SER_VOL, RISK_VOL = V["SER_VOL"], V["RISK_VOL"]
fort_h1, fort_h2 = 24895.0, 48176.0

print("Detailed evaluation across Gate 2 candidates:")
for g2 in [9400.0, 9500.0, 9600.0, 9800.0, 10000.0]:
    s0 = simulate_advanced("S0", lad_4x, SER_VOL, RISK_VOL, 8600.0, 8700.0, g2, 1500.0)
    s3 = simulate_advanced("S3", lad_4x, SER_VOL, RISK_VOL, 8600.0, 8700.0, g2, 1500.0)
    s4 = simulate_advanced("S4", lad_4x, SER_VOL, RISK_VOL, 8600.0, 8700.0, g2, 1500.0)
    h1_pct = (s0["usd_h1"] - fort_h1) / fort_h1 * 100
    h2_pct = (s0["usd_h2"] - fort_h2) / fort_h2 * 100
    y2_usd = s0["usd"] - s0["usd_y1"]
    passed = (s0["usd_h1"] >= 1.05 * fort_h1) and (s0["usd_h2"] >= 1.05 * fort_h2) and (s3["cons"] <= 0.050) and (s4["cons"] <= 0.095)
    print(f"Gate2=${g2:,.0f} | 24m: ${s0['usd']:<7,.0f} | H1: ${s0['usd_h1']:<6,.0f} ({h1_pct:+.1f}%) | H2: ${s0['usd_h2']:<6,.0f} ({h2_pct:+.1f}%) | Y1: ${s0['usd_y1']:<6,.0f} | Y2: ${y2_usd:<6,.0f} | P1 Days: {s0['first_days']:.1f} | N1: {s0['y1_pays']:.1f} | S3: {s3['cons']*100:.1f}% | S4: {s4['cons']*100:.1f}% | Passed: {passed}")

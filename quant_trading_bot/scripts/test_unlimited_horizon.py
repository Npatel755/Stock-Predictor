import json, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
sys.path.insert(0, str(ROOT / "scripts"))
src = (ROOT / "scripts/research_ultra_safe_high_pass_eval.py").read_text()
split_marker = "print(\"\\n\" + \"=\"*95)"
ns = {}
exec(src.split(split_marker)[0], ns)
sim = ns["simulate_evaluation"]

print("="*90)
print("EVALUATION PASS PROBABILITY ACROSS HORIZONS (STATIC $2,000 FLOOR)")
print("="*90)
for horizon in [60, 90, 120, 180, 250, 350]:
    r = sim("Fortress Pro", base_size=6, defensive_size=2, defensive_threshold=-350.0, stage2_size=10, stage2_threshold=1000.0, stage3_size=12, stage3_threshold=2200.0, max_eval_calendar_days=horizon)
    print(f"Horizon {horizon:3d} Trading Days | Pass: {r['pass_pct']:5.1f}% | Ruin: {r['ruin_pct']:5.1f}% | Resolved Pass Rate: {r['resolved_pass_pct']:5.1f}% | Median: {r['med_days']:4.1f}d")

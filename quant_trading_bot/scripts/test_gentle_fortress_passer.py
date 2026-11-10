"""Test Gentle Fortress Scaling (6c -> 7c/8c at +$2,000 cushion)
Goal: Accelerate pass time while maintaining >= 90% Pass Rate and < 5% Ruin.
"""
import sys, json
from pathlib import Path
ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
sys.path.insert(0, str(ROOT / "scripts"))
import test_clean_2week_passer as t2

print("="*125)
print("TESTING GENTLE FORTRESS SCALING (HIGH PASS RATE + FAST PASS TIME)")
print("="*125)

configs = [
    ("1. Pure Static 6 MNQ Baseline", 
     dict(base_sz=6, stg2_sz=6, stg3_sz=6)),
     
    ("2. Gentle Finisher: 6c Base -> 7c at +$2,000", 
     dict(base_sz=6, stg2_sz=6, stg3_sz=7, stg3_thr=2000.0)),

    ("3. Gentle Finisher: 6c Base -> 8c at +$2,000", 
     dict(base_sz=6, stg2_sz=6, stg3_sz=8, stg3_thr=2000.0)),

    ("4. Two-Tier Gentle: 6c Base -> 7c at +$1,500 -> 8c at +$2,500", 
     dict(base_sz=6, stg2_sz=7, stg3_sz=8, stg2_thr=1500.0, stg3_thr=2500.0)),

    ("5. Active Timing VIX >= 16 | 6c Base -> 8c at +$2,000", 
     dict(base_sz=6, stg2_sz=6, stg3_sz=8, stg3_thr=2000.0, min_vix=16.0)),

    ("6. Active Timing VIX >= 18 | 6c Base -> 8c at +$2,000", 
     dict(base_sz=6, stg2_sz=6, stg3_sz=8, stg3_thr=2000.0, min_vix=18.0)),

    ("7. Active Timing VIX >= 18 | 7c Base -> 8c at +$2,000", 
     dict(base_sz=7, stg2_sz=7, stg3_sz=8, stg3_thr=2000.0, min_vix=18.0)),

    ("8. High-Vol Timing VIX >= 20 | 7c Base -> 8c at +$1,800", 
     dict(base_sz=7, stg2_sz=7, stg3_sz=8, stg3_thr=1800.0, min_vix=20.0)),
]

res = []
for lbl, kw in configs:
    r = t2.evaluate_clean_strategy(lbl, **kw)
    res.append(r)
    print(f"{lbl:60s} | Pass: {r['pass_pct']:5.1f}% | Ruin: {r['ruin_pct']:5.1f}% | MEAN TR: {r['mean_trade_days']:4.1f}d | MED TR: {r['med_trade_days']:4.1f}d | P25 TR: {r['p25_trade_days']:4.1f}d | Min: {r['min_trade_days']:2d}d | DD: ${r['avg_dd']:6.2f}")

with open(ROOT / "reports/GENTLE_FORTRESS_RESULTS.json", "w") as f:
    json.dump(res, f, indent=2)

print("\nDone. Saved to reports/GENTLE_FORTRESS_RESULTS.json")

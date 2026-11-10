"""Test Balanced Fortress Scaling with 4 MNQ Defensive Recovery."""
import sys, json
from pathlib import Path
ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
sys.path.insert(0, str(ROOT / "scripts"))
import test_clean_2week_passer as t2

print("="*125)
print("TESTING BALANCED FORTRESS SCALING WITH 4 MNQ DEFENSIVE RECOVERY")
print("="*125)

configs = [
    ("A. 6c Base -> 8c (+$1k) -> 10c (+$2.2k) | Def 4c at -$300", 
     dict(base_sz=6, stg2_sz=8, stg3_sz=10, stg2_thr=1000.0, stg3_thr=2200.0, def_thr=-300.0, def_sz=4)),
    ("B. 6c Base -> 10c (+$1k) -> 12c (+$2k) | Def 4c at -$300", 
     dict(base_sz=6, stg2_sz=10, stg3_sz=12, stg2_thr=1000.0, stg3_thr=2000.0, def_thr=-300.0, def_sz=4)),
    ("C. 6c Base -> 10c (+$800) -> 12c (+$1.8k) | Def 4c at -$300", 
     dict(base_sz=6, stg2_sz=10, stg3_sz=12, stg2_thr=800.0, stg3_thr=1800.0, def_thr=-300.0, def_sz=4)),
    ("D. VIX >= 16 | 6c Base -> 10c (+$800) -> 12c (+$1.8k) | Def 4c", 
     dict(base_sz=6, stg2_sz=10, stg3_sz=12, stg2_thr=800.0, stg3_thr=1800.0, def_thr=-300.0, def_sz=4, min_vix=16.0)),
    ("E. VIX >= 18 | 6c Base -> 10c (+$800) -> 12c (+$1.8k) | Def 4c", 
     dict(base_sz=6, stg2_sz=10, stg3_sz=12, stg2_thr=800.0, stg3_thr=1800.0, def_thr=-300.0, def_sz=4, min_vix=18.0)),
    ("F. VIX >= 20 | 6c Base -> 10c (+$800) -> 14c (+$1.8k) | Def 4c", 
     dict(base_sz=6, stg2_sz=10, stg3_sz=14, stg2_thr=800.0, stg3_thr=1800.0, def_thr=-300.0, def_sz=4, min_vix=20.0)),
]

res = []
for lbl, kw in configs:
    r = t2.evaluate_clean_strategy(lbl, **kw)
    res.append(r)
    print(f"{lbl:62s} | Pass: {r['pass_pct']:5.1f}% | Ruin: {r['ruin_pct']:5.1f}% | MEAN TR: {r['mean_trade_days']:4.1f}d | MED TR: {r['med_trade_days']:4.1f}d | P25 TR: {r['p25_trade_days']:4.1f}d | Min: {r['min_trade_days']:2d}d | DD: ${r['avg_dd']:6.2f}")

with open(ROOT / "reports/RECOVERY_SCALING_RESULTS.json", "w") as f:
    json.dump(res, f, indent=2)

print("\nDone. Saved to reports/RECOVERY_SCALING_RESULTS.json")

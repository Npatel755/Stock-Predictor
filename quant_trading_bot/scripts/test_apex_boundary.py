import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_ultra_optimized_train as ruo

SER = ruo.SER_CAP
RISK = ruo.RISK_CAP

candidates = [
    ('4x @ $6.5k (1x <$4k, 2x $4k-$4.8k, 3x $4.8k-$6.5k, 4x >=$6.5k | K=$8.5k)', [(0, 1), (4000, 2), (4800, 3), (6500, 4)], 8500.0),
    ('4x @ $6.5k (1x <$4k, 2x $4k-$4.8k, 3x $4.8k-$6.5k, 4x >=$6.5k | K=$8.0k)', [(0, 1), (4000, 2), (4800, 3), (6500, 4)], 8000.0),
    ('4x @ $6.8k (1x <$4k, 2x $4k-$5.0k, 3x $5.0k-$6.8k, 4x >=$6.8k | K=$8.5k)', [(0, 1), (4000, 2), (5000, 3), (6800, 4)], 8500.0),
    ('4x @ $7.0k (1x <$4k, 2x $4k-$5.0k, 3x $5.0k-$7.0k, 4x >=$7.0k | K=$8.5k)', [(0, 1), (4000, 2), (5000, 3), (7000, 4)], 8500.0),
    ('4x @ $7.0k (1x <$4k, 2x $4k-$5.0k, 3x $5.0k-$7.0k, 4x >=$7.0k | K=$9.0k)', [(0, 1), (4000, 2), (5000, 3), (7000, 4)], 9000.0),
    ('5-tier (1x <$4k, 2x $4k-$5k, 3x $5k-$6.5k, 4x $6.5k-$8k, 5x >=$8k | K=$9.0k)', [(0, 1), (4000, 2), (5000, 3), (6500, 4), (8000, 5)], 9000.0),
]

for name, lad, k_val in candidates:
    res = ruo.evaluate_cell(SER, RISK, lad, k_val)
    s0 = res['S0']['usd']
    h1 = res['half1']['usd']
    h2 = res['half2']['usd']
    s3_c = res['S3']['cons']
    s4_c = res['S4']['cons']
    s0_cl = res['S0']['closed']
    s3_cl = res['S3']['closed']
    s4_cl = res['S4']['closed']
    print(f"{name}:")
    print(f"   S0: ${s0:,.0f} | H1: ${h1:,.0f} | H2: ${h2:,.0f} | S3 Cons: {s3_c} | S4 Cons: {s4_c} | S3 Cl: {s3_cl} | S4 Cl: {s4_cl}")

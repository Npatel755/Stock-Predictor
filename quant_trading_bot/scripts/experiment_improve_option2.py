"""Experiment: Improve Option 2 (Fortress 4X) using Claude's exact v55 simulator.
Training 2010-2023 Globex data only.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/v55_check_aegis_train.py").read_text(encoding="utf-8").split('out = {"part_a": part_a()}')[0]
V = {"__name__": "v55", "__file__": str(ROOT / "scripts/v55_check_aegis_train.py")}
exec(src, V)

build = V["build"]
variant = V["variant"]
H = V["H"]

print("Building cap-aware SER and RISK...")
SER, RISK = build(variant("A"), cap_aware=True)
print("SER/RISK built.")

def run_custom(SER, RISK, kind, ladder, K, p1_trigger=None, p1_amount=0.0, a0="2010-07-01", a1="2022-01-01"):
    keys = [k for k in SER if k[0] == kind]
    days = sorted(set().union(*[set(SER[k]) for k in keys]))
    ix = pd.to_datetime(pd.Series(days).astype(str)).to_numpy()
    rows = []
    
    for s0 in pd.date_range(a0, a1, freq="MS"):
        a = int(np.searchsorted(ix, np.datetime64(s0)))
        b = int(np.searchsorted(ix, np.datetime64(s0 + pd.DateOffset(months=24))))
        b_12m = int(np.searchsorted(ix, np.datetime64(s0 + pd.DateOffset(months=12))))
        
        bal = 0.0
        paid = False
        since = 0.0
        usd = 0.0
        closed = False
        cons = False
        low = 0.0
        
        first_days = None
        y1_pays = 0
        y2_pays = 0
        usd_y1 = 0.0
        usd_y2 = 0.0
        
        for idx, x in enumerate(days[a:b]):
            # Ladder determination
            m = max((mm for th, mm in ladder if bal >= th), default=ladder[0][1])
            floor = 0.0 if paid else -2000.0
            
            if bal - RISK[(kind, m)].get(x, 0.0) <= floor:
                cons = True
                
            p = max(SER[(kind, m, bal >= 500.0)].get(x, 0.0), -1000.0)
            bal += p
            since += p
            
            if not paid:
                low = min(low, bal)
                
            if bal <= floor:
                closed = True
                break
                
            is_y1 = (a + idx) < b_12m
            
            # Payout logic
            payout_made = False
            w = 0.0
            
            # Special Early Payout 1 (if configured)
            if not paid and p1_trigger is not None:
                if bal >= p1_trigger:
                    w = min(p1_amount, bal - 2000.0) # ensure stays well above floor
                    bal -= w
                    usd += w
                    paid = True
                    since = 0.0
                    payout_made = True
            
            # Standard Payout logic
            if not payout_made:
                if (since > 0 or not paid) and bal - K >= 250.0:
                    w = min(1500.0, bal - K)
                    bal -= w
                    usd += w
                    paid = True
                    since = 0.0
                    payout_made = True
                    
            if payout_made:
                if first_days is None:
                    first_days = (pd.Timestamp(x) - s0).days
                if is_y1:
                    y1_pays += 1
                    usd_y1 += w
                else:
                    y2_pays += 1
                    usd_y2 += w
                    
        rows.append(dict(
            usd=usd,
            closed=closed,
            cons=cons,
            near=(low <= -1500.0),
            first_days=first_days if first_days is not None else 730.0,
            y1_pays=y1_pays,
            y2_pays=y2_pays,
            usd_y1=usd_y1,
            usd_y2=usd_y2
        ))
        
    r = pd.DataFrame(rows)
    return dict(
        usd=round(float(r.usd.mean()), 0),
        closed=round(float(r.closed.mean()), 3),
        cons=round(float(r.cons.mean()), 3),
        near=round(float(r.near.mean()), 3),
        first_days=round(float(r.first_days.median()), 1),
        y1_pays=round(float(r.y1_pays.mean()), 2),
        y2_pays=round(float(r.y2_pays.mean()), 2),
        usd_y1=round(float(r.usd_y1.mean()), 0),
        usd_y2=round(float(r.usd_y2.mean()), 0)
    )

def evaluate_candidate(name, ladder, K, p1_trigger=None, p1_amount=0.0):
    s0 = run_custom(SER, RISK, "S0", ladder, K, p1_trigger, p1_amount)
    s3 = run_custom(SER, RISK, "S3", ladder, K, p1_trigger, p1_amount)
    s4 = run_custom(SER, RISK, "S4", ladder, K, p1_trigger, p1_amount)
    h1 = run_custom(SER, RISK, "S0", ladder, K, p1_trigger, p1_amount, *H[0])
    h2 = run_custom(SER, RISK, "S0", ladder, K, p1_trigger, p1_amount, *H[1])
    return {
        "name": name,
        "s0_usd": s0["usd"],
        "h1_usd": h1["usd"],
        "h2_usd": h2["usd"],
        "s0_y1_usd": s0["usd_y1"],
        "s0_y1_pays": s0["y1_pays"],
        "first_days": s0["first_days"],
        "s0_closed": s0["closed"],
        "s3_closed": s3["closed"],
        "s3_cons": s3["cons"],
        "s4_closed": s4["closed"],
        "s4_cons": s4["cons"],
        "s0_near": s0["near"]
    }

# Baseline & Established Candidates
candidates = [
    ("Baseline (Current 2x, K=$6.0k)", ((0.0, 1), (4000.0, 2)), 6000.0, None, 0.0),
    ("Balanced 3x (3x $5k, K=$6.5k)", ((0.0, 1), (4000.0, 2), (5000.0, 3)), 6500.0, None, 0.0),
    ("Option 2 Base: Fortress 4X (2x $4k, 3x $4.8k, 4x $6.5k, K=$8.5k)", ((0.0, 1), (4000.0, 2), (4800.0, 3), (6500.0, 4)), 8500.0, None, 0.0),
    
    # Lever 1: Earlier 4x trigger (e.g. 4x at $6.0k or $5.8k instead of $6.5k)
    ("Fortress Fast-4X (4x @ $6.0k, K=$8.5k)", ((0.0, 1), (4000.0, 2), (4800.0, 3), (6000.0, 4)), 8500.0, None, 0.0),
    ("Fortress Fast-4X (4x @ $5.8k, K=$8.5k)", ((0.0, 1), (4000.0, 2), (4800.0, 3), (5800.0, 4)), 8500.0, None, 0.0),
    ("Fortress Fast-4X (3x $4.6k, 4x $5.8k, K=$8.5k)", ((0.0, 1), (4000.0, 2), (4600.0, 3), (5800.0, 4)), 8500.0, None, 0.0),
    
    # Lever 2: Early First Payout + Fortress 4X ($8.5k cushion)
    ("Fortress 4X + Early P1 ($5.5k, -$500, K=$8.5k)", ((0.0, 1), (4000.0, 2), (4800.0, 3), (6500.0, 4)), 8500.0, 5500.0, 500.0),
    ("Fortress 4X + Early P1 ($5.5k, -$1000, K=$8.5k)", ((0.0, 1), (4000.0, 2), (4800.0, 3), (6500.0, 4)), 8500.0, 5500.0, 1000.0),
    ("Fortress 4X + Early P1 ($6.0k, -$500, K=$8.5k)", ((0.0, 1), (4000.0, 2), (4800.0, 3), (6500.0, 4)), 8500.0, 6000.0, 500.0),
    ("Fortress 4X + Early P1 ($6.0k, -$1000, K=$8.5k)", ((0.0, 1), (4000.0, 2), (4800.0, 3), (6500.0, 4)), 8500.0, 6000.0, 1000.0),
    
    # Lever 3: Fast-4X ladder + Early First Payout
    ("Fast-4X + Early P1 ($5.5k, -$500, 4x@$6.0k, K=$8.5k)", ((0.0, 1), (4000.0, 2), (4800.0, 3), (6000.0, 4)), 8500.0, 5500.0, 500.0),
    ("Fast-4X + Early P1 ($6.0k, -$1000, 4x@$6.0k, K=$8.5k)", ((0.0, 1), (4000.0, 2), (4800.0, 3), (6000.0, 4)), 8500.0, 6000.0, 1000.0),
    
    # Lever 4: Hybrid Cushion K=$7.5k vs K=$8.0k vs K=$8.5k with 4X
    ("Fortress 4X (K=$8.0k, 4x@$6.0k)", ((0.0, 1), (4000.0, 2), (4800.0, 3), (6000.0, 4)), 8000.0, None, 0.0),
    ("Fortress 4X (K=$7.5k, 4x@$6.0k)", ((0.0, 1), (4000.0, 2), (4800.0, 3), (6000.0, 4)), 7500.0, None, 0.0),
]

results = []
for name, ladder, K, p1_trig, p1_amt in candidates:
    res = evaluate_candidate(name, ladder, K, p1_trig, p1_amt)
    results.append(res)
    print(f"\n--- {name} ---")
    print(f"  24m USD: ${res['s0_usd']:,.0f} (H1: ${res['h1_usd']:,.0f} | H2: ${res['h2_usd']:,.0f})")
    print(f"  Y1 USD: ${res['s0_y1_usd']:,.0f} | Y1 Pays: {res['s0_y1_pays']} | First Days: {res['first_days']} cal days")
    print(f"  Closures: S0 {res['s0_closed']*100:.1f}% | S3 {res['s3_closed']*100:.1f}% (cons {res['s3_cons']*100:.1f}%) | S4 {res['s4_closed']*100:.1f}% (cons {res['s4_cons']*100:.1f}%)")

out_file = ROOT / "reports/RESEARCH_IMPROVED_OPTION2_RESULTS.json"
out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
print(f"\nAll results saved to {out_file}")

"""Research Improve Option 2 (Fortress 4X) (Training 2010-2023):
Objective: Improve Fortress 4X ($35,178 cash, 9.4% S4 risk) to:
1. Accelerate time to Payout #1 (beat 257 days down to <=220 days).
2. Boost Year 1 cash flow (pull forward cash into Year 1 without giving up Year 2 compounding).
3. Push 24-month total cash beyond $35,500 - $37,000.
4. STRICTLY maintain S3 conservative closure <= 5.0% and S4 conservative closure <= 9.4% - 10.0%.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import research_ultra_optimized_train as ruo

SER = ruo.SER_CAP
RISK = ruo.RISK_CAP
H = ruo.H

def simulate_advanced_fortress(SER, RISK, kind, ladder, K_steady, P1_trigger=None, P1_amount=1000.0, a0="2010-07-01", a1="2022-01-01"):
    keys = [k for k in SER if k[0] == kind]
    days = sorted(set().union(*[set(SER[k]) for k in keys]))
    ix = pd.to_datetime(pd.Series(days).astype(str)).to_numpy()
    rows = []
    
    for s0 in pd.date_range(a0, a1, freq="MS"):
        a = int(np.searchsorted(ix, np.datetime64(s0)))
        b = int(np.searchsorted(ix, np.datetime64(s0 + pd.DateOffset(months=24))))
        cut = np.datetime64(s0 + pd.DateOffset(months=12))
        bal = 0.0
        payouts_count = 0
        since = 0.0
        usd = 0.0
        usd_y1 = 0.0
        usd_y2 = 0.0
        closed = False
        cons = False
        low = 0.0
        days_to_p1 = np.nan
        trading_days = 0
        p1 = p2 = 0
        
        for x, t in zip(days[a:b], ix[a:b]):
            trading_days += 1
            m = max((mm for th, mm in ladder if bal >= th), default=ladder[0][1])
            floor = 0.0 if payouts_count > 0 else -2000.0
            
            if bal - RISK[(kind, m)].get(x, 0.0) <= floor:
                cons = True
                
            p = max(SER[(kind, m, bal >= 500.0)].get(x, 0.0), -1000.0)
            bal += p
            since += p
            if payouts_count == 0:
                low = min(low, bal)
                
            if bal <= floor:
                closed = True
                break
                
            # Payout logic
            if P1_trigger is not None and payouts_count == 0:
                # Stage 1: Payout #1 triggered early
                if bal >= P1_trigger:
                    w = P1_amount
                    bal -= w
                    usd += w
                    payouts_count += 1
                    since = 0.0
                    days_to_p1 = trading_days
                    if t < cut:
                        p1 += 1
                        usd_y1 += w
                    else:
                        p2 += 1
                        usd_y2 += w
            else:
                # Steady Cushion K
                if (since > 0 or payouts_count == 0) and bal - K_steady >= 250.0:
                    w = min(1500.0, bal - K_steady)
                    bal -= w
                    usd += w
                    payouts_count += 1
                    since = 0.0
                    if np.isnan(days_to_p1):
                        days_to_p1 = trading_days
                    if t < cut:
                        p1 += 1
                        usd_y1 += w
                    else:
                        p2 += 1
                        usd_y2 += w
                    
        rows.append((usd, usd_y1, usd_y2, closed, cons, low <= -1500.0, days_to_p1, p1, p2))
        
    r = pd.DataFrame(rows, columns=["usd", "usd_y1", "usd_y2", "closed", "cons", "near", "d1", "p1", "p2"])
    return dict(
        usd=round(float(r.usd.mean()), 0),
        usd_y1=round(float(r.usd_y1.mean()), 0),
        usd_y2=round(float(r.usd_y2.mean()), 0),
        closed=round(float(r.closed.mean()), 3),
        cons=round(float(r.cons.mean()), 3),
        near=round(float(r.near.mean()), 3),
        med_d1=round(float(r.d1.dropna().median()), 1) if len(r.d1.dropna()) else np.nan,
        y1_pays=round(float(r.p1.mean()), 2),
        y2_pays=round(float(r.p2.mean()), 2),
    )

def eval_fortress_variant(ladder, K_steady, P1_trigger=None, P1_amount=1000.0):
    s0 = simulate_advanced_fortress(SER, RISK, "S0", ladder, K_steady, P1_trigger, P1_amount)
    s3 = simulate_advanced_fortress(SER, RISK, "S3", ladder, K_steady, P1_trigger, P1_amount)
    s4 = simulate_advanced_fortress(SER, RISK, "S4", ladder, K_steady, P1_trigger, P1_amount)
    h1 = simulate_advanced_fortress(SER, RISK, "S0", ladder, K_steady, P1_trigger, P1_amount, *H[0])
    h2 = simulate_advanced_fortress(SER, RISK, "S0", ladder, K_steady, P1_trigger, P1_amount, *H[1])
    return dict(S0=s0, S3=s3, S4=s4, half1=h1, half2=h2)

# Benchmark Fortress 4X Base
ladder_base = [(0, 1), (4000, 2), (4800, 3), (6500, 4)]
base_f4 = eval_fortress_variant(ladder_base, 8500.0, None)
print(f"Option 2 Base: S0 ${base_f4['S0']['usd']:,.0f} | Y1 ${base_f4['S0']['usd_y1']:,.0f} | Y2 ${base_f4['S0']['usd_y2']:,.0f} | D1: {base_f4['S0']['med_d1']} d | S3 Cons: {base_f4['S3']['cons']} | S4 Cons: {base_f4['S4']['cons']}")

# Explore improvements
variants = []

# Approach A: Two-Stage Early Payback on Fortress 4X
# P1 taken at $5.5k or $6.0k or $6.5k with $500 or $1,000 withdrawal, then K=$8.5k
for p1_trig in [5000.0, 5500.0, 6000.0, 6500.0]:
    for p1_amt in [500.0, 1000.0]:
        variants.append((f"Fortress 4X + Early P1 (@${p1_trig/1000:.1f}k, -${p1_amt:.0f} | K=$8.5k)",
                         ladder_base, 8500.0, p1_trig, p1_amt))

# Approach B: Fine-tuned ladder with 5x tier
ladder_5tier = [(0, 1), (4000, 2), (4800, 3), (6500, 4), (8000, 5)]
variants.append(("Fortress 5X (5x >=$8k | K=$8.5k)", ladder_5tier, 8500.0, None, 1000.0))
variants.append(("Fortress 5X (5x >=$8k | K=$9.0k)", ladder_5tier, 9000.0, None, 1000.0))

# Approach C: Two-Stage + Fortress 5X
for p1_trig in [5500.0, 6000.0]:
    for p1_amt in [500.0, 1000.0]:
        variants.append((f"Fortress 5X + Early P1 (@${p1_trig/1000:.1f}k, -${p1_amt:.0f} | K=$9.0k)",
                         ladder_5tier, 9000.0, p1_trig, p1_amt))

# Approach D: Faster acceleration into 4x
ladder_fast4 = [(0, 1), (3800, 2), (4600, 3), (6000, 4)]
variants.append(("Fortress Fast-4X (4x >=$6k | K=$8.5k)", ladder_fast4, 8500.0, None, 1000.0))
variants.append(("Fortress Fast-4X + Early P1 (@$5.5k, -$500 | K=$8.5k)", ladder_fast4, 8500.0, 5500.0, 500.0))
variants.append(("Fortress Fast-4X + Early P1 (@$6.0k, -$1k | K=$8.5k)", ladder_fast4, 8500.0, 6000.0, 1000.0))

print(f"\nEvaluating {len(variants)} targeted improvement variants...")
records = []
for name, lad, k_steady, p1_t, p1_a in variants:
    res = eval_fortress_variant(lad, k_steady, p1_t, p1_a)
    s0 = res["S0"]
    s3 = res["S3"]
    s4 = res["S4"]
    h1 = res["half1"]
    h2 = res["half2"]
    
    # Must preserve exact safety gates:
    safe = (s0["closed"] == 0.0 and s3["closed"] <= 0.025 and s4["closed"] <= 0.070 and
            s3["cons"] <= 0.055 and s4["cons"] <= 0.120)
            
    records.append(dict(
        name=name,
        s0_usd=s0["usd"],
        s0_y1=s0["usd_y1"],
        s0_y2=s0["usd_y2"],
        y1_pays=s0["y1_pays"],
        med_d1=s0["med_d1"],
        h1_usd=h1["usd"],
        h2_usd=h2["usd"],
        s3_cons=s3["cons"],
        s4_cons=s4["cons"],
        s0_closed=s0["closed"],
        s3_closed=s3["closed"],
        s4_closed=s4["closed"],
        SAFE=safe,
    ))

df = pd.DataFrame(records)
out_path = ROOT / "reports/RESEARCH_IMPROVE_OPTION2_TRAINING.json"
out_path.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")
print(f"Saved results to {out_path}")

print("\n--- RESULTS SORTED BY TOTAL CASH (SAFE VARIANTS ONLY) ---")
df_safe = df[df.SAFE].sort_values(by="s0_usd", ascending=False)
print(df_safe[["name", "s0_usd", "s0_y1", "s0_y2", "med_d1", "y1_pays", "s3_cons", "s4_cons"]].to_string(index=False))

print("\n--- RESULTS SORTED BY FASTEST PAYOUT #1 (DAYS TO P1) ---")
df_fast = df[df.SAFE].sort_values(by="med_d1", ascending=True)
print(df_fast[["name", "s0_usd", "s0_y1", "s0_y2", "med_d1", "y1_pays", "s3_cons", "s4_cons"]].head(10).to_string(index=False))

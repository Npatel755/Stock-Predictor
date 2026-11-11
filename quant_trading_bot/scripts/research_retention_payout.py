"""Experiment: Payout Pacing and Operational Retention
Testing whether retaining a small operational cushion above K ($8.5k)
allows the account to stay in 4x sizing longer and avoid dropping below the payout waterline.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import research_improve_option2_further as r

candidates = [
    # 1. 100% full sweep (Standard benchmark)
    ("Standard 100% Sweep (K=$8.5k, min $250, max $1500)", 1.0, 0.0),
    
    # 2. Retain $200 operational buffer above K
    ("Buffer Retention $200 (Withdraw above $8.7k)", 1.0, 200.0),
    ("Buffer Retention $400 (Withdraw above $8.9k)", 1.0, 400.0),
    
    # 3. Fractional profit sweep (80%, 85%, 90% of excess)
    ("Fractional 80% of excess (keep 20% in account)", 0.80, 0.0),
    ("Fractional 85% of excess (keep 15% in account)", 0.85, 0.0),
    ("Fractional 90% of excess (keep 10% in account)", 0.90, 0.0),
    
    # 4. Lower minimum request threshold ($150 vs $200 vs $250)
    ("Low Min Request $150 (K=$8.5k)", 1.0, 0.0, 150.0),
    ("Low Min Request $200 (K=$8.5k)", 1.0, 0.0, 200.0),
]

def simulate_retention(SER, RISK, kind, lad, K, pct=1.0, reserve=0.0, min_w=250.0, sprint=False, a0="2010-07-01", a1="2022-01-01"):
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
        usd_y1 = 0.0
        
        for idx, x in enumerate(days[a:b]):
            m = max((mm for th, mm in lad if bal >= th), default=lad[0][1])
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
            payout_made = False
            w = 0.0
            
            # Optional sprint first payout @ $6.0k
            if sprint and not paid:
                if bal >= 6000.0:
                    w = 500.0
                    bal -= w
                    usd += w
                    paid = True
                    since = 0.0
                    payout_made = True
            
            if not payout_made:
                excess = bal - (K + reserve)
                if (since > 0 or not paid) and excess >= min_w:
                    w = min(1500.0, excess * pct)
                    if w >= min_w:
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
                    
        rows.append(dict(
            usd=usd,
            closed=closed,
            cons=cons,
            near=(low <= -1500.0),
            first_days=first_days if first_days is not None else 730.0,
            y1_pays=y1_pays,
            usd_y1=usd_y1
        ))
        
    r = pd.DataFrame(rows)
    return dict(
        usd=round(float(r.usd.mean()), 0),
        closed=round(float(r.closed.mean()), 3),
        cons=round(float(r.cons.mean()), 3),
        near=round(float(r.near.mean()), 3),
        first_days=round(float(r.first_days.median()), 1),
        y1_pays=round(float(r.y1_pays.mean()), 2),
        usd_y1=round(float(r.usd_y1.mean()), 0)
    )

lad = ((0,1), (4000,2), (4600,3), (5400,4))
results = []

for c in candidates:
    name = c[0]
    pct = c[1]
    reserve = c[2]
    min_w = c[3] if len(c) > 3 else 250.0
    
    # Pure
    s0 = simulate_retention(r.SER_BASE, r.RISK_BASE, "S0", lad, 8500.0, pct, reserve, min_w, False)
    s3 = simulate_retention(r.SER_BASE, r.RISK_BASE, "S3", lad, 8500.0, pct, reserve, min_w, False)
    s4 = simulate_retention(r.SER_BASE, r.RISK_BASE, "S4", lad, 8500.0, pct, reserve, min_w, False)
    
    # Sprint
    s0_sp = simulate_retention(r.SER_BASE, r.RISK_BASE, "S0", lad, 8500.0, pct, reserve, min_w, True)
    
    safe = (s3["cons"] <= 0.05 and s4["cons"] <= 0.095 and s0["closed"] == 0.0)
    print(f"\n{'[PASS]' if safe else '[FAIL]'} {name}")
    print(f"  PURE:   24m ${s0['usd']:,.0f} | Y1 ${s0['usd_y1']:,.0f} ({s0['y1_pays']} pays) | P1 {s0['first_days']}d | S3 {s3['cons']*100:.1f}% | S4 {s4['cons']*100:.1f}%")
    print(f"  SPRINT: 24m ${s0_sp['usd']:,.0f} | Y1 ${s0_sp['usd_y1']:,.0f} ({s0_sp['y1_pays']} pays) | P1 {s0_sp['first_days']}d")

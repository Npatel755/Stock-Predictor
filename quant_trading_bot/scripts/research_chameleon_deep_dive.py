"""Comprehensive Deep-Dive on Cushion-Gated Chameleon Strategies.
Explores:
1. Gate thresholds: $8,600, $8,700, $8,800, $8,900, $9,000, $9,200, $9,500
2. Sleeve variants:
   - Variant A: Base v5.3 (Benchmark)
   - Variant B: Base + MNQ_BRK_E_2c
   - Variant C: Base + MES_MOM_3c
   - Variant D: Base + Both (Full Portfolio E)
3. Pacing modes: Pure ($8.5k K), Sprint ($6.0k P1, $8.5k K), Sprint ($6.0k P1, $9.0k K)
4. Full audit of Claude's 4 Gates including 2010-16 vs 2017-23 split!
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import sys

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/v55_check_aegis_train.py").read_text(encoding="utf-8").split('out = {"part_a": part_a()}')[0]
V = {"__name__": "v55", "__file__": str(ROOT / "scripts/v55_check_aegis_train.py")}
exec(src, V)

pl = V["pl"]
stressed = V["stressed"]
sc17 = V["sc17"]
N0 = V["N0"]
fds = V["fds"]
NIGHT_RISK = V["NIGHT_RISK"]
variant = V["variant"]
H = V["H"]
P10 = V["P10"]
ep, bars_for, START = P10["ep"], P10["bars_for"], P10["START"]

df_base = variant("A")
base_cols = df_base.columns

# Generate candidate sleeve trades
def get_sleeve(name, key="portfolio_e", prio=10):
    sl = next(s for s in ep.CANDIDATES[key]["sleeves"] if s["name"] == name)
    x = pl.price_normalize(pl.sleeve_trades(ep, bars_for, START, dict(sl), prio, False))
    x["n_contracts"] = 1.0
    x["mae_per_micro"] = 0.0
    return x[base_cols]

slv_brk = get_sleeve("MNQ_BRK_E_2c", prio=10)
slv_mom = get_sleeve("MES_MOM_3c", prio=11)

df_brk = pd.concat([df_base, slv_brk], ignore_index=True)
df_mom = pd.concat([df_base, slv_mom], ignore_index=True)
df_both = pd.concat([df_base, slv_brk, slv_mom], ignore_index=True)

def build_tables(df_variant):
    SER, RISK = {}, {}
    for kind in ("S0", "S3", "S4"):
        e = stressed(df_variant, kind)
        _, n = sc17(kind, N0)
        nr = NIGHT_RISK * (1.5 if kind == "S4" else 1.0)
        r = pl.route(e)
        
        for m in (1, 2, 3, 4):
            per = r.net_today / r.n_contracts
            risk = r.risk_today
            q = np.minimum(m * r.n_contracts, np.floor(900.0 / risk)) if m > 1 else r.n_contracts
            i = r.assign(net_today=per * q, q=q)[lambda x: x.q >= 1]
            
            qn = (min(m, int(900.0 // nr))) if m > 1 else 1
            nm = n.assign(net_today=n.net_today * qn) if qn >= 1 else n.iloc[0:0]
            
            stop = 400.0 if m == 1 else 700.0
            SER[(kind, m, False)] = fds(i[["tin", "tout", "net_today"]], stop).to_dict()
            SER[(kind, m, True)] = fds(pd.concat([i[["tin", "tout", "net_today"]], nm], ignore_index=True), stop).to_dict()
            
            rk = (i.risk_today * i.q).groupby(i.tout.dt.date).max()
            if qn >= 1:
                rk = pd.concat([rk, pd.Series(nr * qn, index=pd.Index(n.tout.dt.date))]).groupby(level=0).max()
            RISK[(kind, m)] = rk.to_dict()
            
    return SER, RISK

print("Building simulation tables for all books...")
SER_BASE, RISK_BASE = build_tables(df_base)
SER_BRK, RISK_BRK = build_tables(df_brk)
SER_MOM, RISK_MOM = build_tables(df_mom)
SER_BOTH, RISK_BOTH = build_tables(df_both)
print("Simulation tables ready.")

def simulate(SER_B, RISK_B, SER_E, RISK_E, kind, lad, K=8500.0, gate_th=8500.0, sprint_bal=6000.0, sprint_amt=500.0, a0="2010-07-01", a1="2022-01-01"):
    keys = [k for k in SER_B if k[0] == kind]
    days = sorted(set().union(*[set(SER_B[k]) for k in keys]))
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
            
            use_exp = (bal >= gate_th)
            SER = SER_E if use_exp else SER_B
            RISK = RISK_E if use_exp else RISK_B
            
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
            
            if sprint_bal is not None and not paid:
                if bal >= sprint_bal:
                    w = sprint_amt
                    bal -= w
                    usd += w
                    paid = True
                    since = 0.0
                    payout_made = True
            
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
                    
        rows.append(dict(
            s0=s0,
            usd=usd,
            closed=closed,
            cons=cons,
            near=(low <= -1500.0),
            first_days=first_days if first_days is not None else 730.0,
            y1_pays=y1_pays,
            usd_y1=usd_y1
        ))
        
    r = pd.DataFrame(rows)
    r_h1 = r[r.s0 < "2017-01-01"]
    r_h2 = r[r.s0 >= "2017-01-01"]
    
    return dict(
        usd=round(float(r.usd.mean()), 0),
        usd_h1=round(float(r_h1.usd.mean()), 0),
        usd_h2=round(float(r_h2.usd.mean()), 0),
        closed=round(float(r.closed.mean()), 3),
        cons=round(float(r.cons.mean()), 3),
        near=round(float(r.near.mean()), 3),
        first_days=round(float(r.first_days.median()), 1),
        y1_pays=round(float(r.y1_pays.mean()), 2),
        usd_y1=round(float(r.usd_y1.mean()), 0)
    )

lad = ((0,1), (4000,2), (4600,3), (5400,4))

# Test configurations
configs = [
    # Baseline benchmarks
    ("Baseline 2X (Keep $5.5k)", SER_BASE, RISK_BASE, ((0,1),(5000,2)), 5500.0, 1e9, None, 0.0),
    ("Base v5.3 Convex Pure ($8.5k)", SER_BASE, RISK_BASE, lad, 8500.0, 1e9, None, 0.0),
    ("Base v5.3 Convex Sprint ($8.5k, P1@$6k)", SER_BASE, RISK_BASE, lad, 8500.0, 1e9, 6000.0, 500.0),
    
    # MNQ Breakout Only
    ("Chameleon MNQ_BRK Gate @ $8.5k (Pure)", SER_BASE, RISK_BASE, SER_BRK, RISK_BRK, lad, 8500.0, 8500.0, None, 0.0),
    ("Chameleon MNQ_BRK Gate @ $8.5k (Sprint)", SER_BASE, RISK_BASE, SER_BRK, RISK_BRK, lad, 8500.0, 8500.0, 6000.0, 500.0),
    ("Chameleon MNQ_BRK Gate @ $8.8k (Sprint)", SER_BASE, RISK_BASE, SER_BRK, RISK_BRK, lad, 8500.0, 8800.0, 6000.0, 500.0),
    ("Chameleon MNQ_BRK Gate @ $9.0k (Sprint)", SER_BASE, RISK_BASE, SER_BRK, RISK_BRK, lad, 8500.0, 9000.0, 6000.0, 500.0),
    
    # MES Momentum Only
    ("Chameleon MES_MOM Gate @ $8.5k (Sprint)", SER_BASE, RISK_BASE, SER_MOM, RISK_MOM, lad, 8500.0, 8500.0, 6000.0, 500.0),
    ("Chameleon MES_MOM Gate @ $9.0k (Sprint)", SER_BASE, RISK_BASE, SER_MOM, RISK_MOM, lad, 8500.0, 9000.0, 6000.0, 500.0),
    
    # Both Sleeves (Full Portfolio E)
    ("Chameleon Both Gate @ $8.7k (Sprint)", SER_BASE, RISK_BASE, SER_BOTH, RISK_BOTH, lad, 8500.0, 8700.0, 6000.0, 500.0),
    ("Chameleon Both Gate @ $8.8k (Sprint)", SER_BASE, RISK_BASE, SER_BOTH, RISK_BOTH, lad, 8500.0, 8800.0, 6000.0, 500.0),
    ("Chameleon Both Gate @ $8.9k (Sprint)", SER_BASE, RISK_BASE, SER_BOTH, RISK_BOTH, lad, 8500.0, 8900.0, 6000.0, 500.0),
    ("Chameleon Both Gate @ $9.0k (Pure)", SER_BASE, RISK_BASE, SER_BOTH, RISK_BOTH, lad, 8500.0, 9000.0, None, 0.0),
    ("Chameleon Both Gate @ $9.0k (Sprint)", SER_BASE, RISK_BASE, SER_BOTH, RISK_BOTH, lad, 8500.0, 9000.0, 6000.0, 500.0),
    ("Chameleon Both Gate @ $9.2k (Sprint)", SER_BASE, RISK_BASE, SER_BOTH, RISK_BOTH, lad, 8500.0, 9200.0, 6000.0, 500.0),
    ("Chameleon Both Gate @ $9.5k (Sprint)", SER_BASE, RISK_BASE, SER_BOTH, RISK_BOTH, lad, 8500.0, 9500.0, 6000.0, 500.0),
]

all_res = []
print("\n" + "="*80)
print(f"{'Config Name':<42} | {'24m USD':<8} | {'H1/H2 USD':<15} | {'P1 Days':<7} | {'S3cons':<6} | {'S4cons':<6} | {'Status'}")
print("="*80)

base_h1, base_h2 = 18787.0, 33542.0

for cfg in configs:
    if len(cfg) == 8:
        name, sb, rb, ld, k_val, g_th, sp_bal, sp_amt = cfg
        se, re = sb, rb
    else:
        name, sb, rb, se, re, ld, k_val, g_th, sp_bal, sp_amt = cfg
        
    s0 = simulate(sb, rb, se, re, "S0", ld, k_val, g_th, sp_bal, sp_amt)
    s3 = simulate(sb, rb, se, re, "S3", ld, k_val, g_th, sp_bal, sp_amt)
    s4 = simulate(sb, rb, se, re, "S4", ld, k_val, g_th, sp_bal, sp_amt)
    
    # Check 4 gates
    g1 = (s0["usd_h1"] >= 1.05 * base_h1) and (s0["usd_h2"] >= 1.05 * base_h2)
    g2 = (s0["closed"] <= 0.005)
    g3 = (s3["cons"] <= 0.050) and (s4["cons"] <= 0.095)
    g4 = (s0["near"] <= 0.007)
    
    passed = g1 and g2 and g3 and g4
    status = "PASS" if passed else "FAIL"
    
    print(f"{name:<42} | ${s0['usd']:<7,.0f} | ${s0['usd_h1']:<6,.0f}/${s0['usd_h2']:<6,.0f} | {s0['first_days']:<7.1f} | {s3['cons']*100:<5.1f}% | {s4['cons']*100:<5.1f}% | {status}")
    
    all_res.append(dict(
        name=name,
        usd=s0["usd"],
        usd_h1=s0["usd_h1"],
        usd_h2=s0["usd_h2"],
        usd_y1=s0["usd_y1"],
        y1_pays=s0["y1_pays"],
        p1_days=s0["first_days"],
        s0_ruin=s0["closed"],
        s3_cons=s3["cons"],
        s4_cons=s4["cons"],
        s0_near=s0["near"],
        passed=passed
    ))

out_path = ROOT / "reports/RESEARCH_CHAMELEON_DEEP_DIVE.json"
out_path.write_text(json.dumps(all_res, indent=2), encoding="utf-8")
print(f"\nSaved results to {out_path}")

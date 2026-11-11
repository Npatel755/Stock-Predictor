"""Experiment: Cushion-Gated Sleeve Expansion (The Chameleon Engine)
Hypothesis:
- When bal < K ($8,500): Trade STRICTLY Base v5.3 (preserves 5.0% S3 cons, 9.4% S4 cons, 0% ruin).
- When bal >= K ($8,500): Activate Expanded Sleeves (MNQ_BRK_E + MES_MOM) to harvest $41k cash!
Tested across all 139 rolling 24m windows (2010-2023).
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

SLV = []
for prio, (name, key) in enumerate((("MNQ_BRK_E_2c", "portfolio_e"), ("MES_MOM_3c", "portfolio_e")), start=10):
    sl = next(s for s in ep.CANDIDATES[key]["sleeves"] if s["name"] == name)
    x = pl.price_normalize(pl.sleeve_trades(ep, bars_for, START, dict(sl), prio, False))
    x["n_contracts"] = 1.0
    x["mae_per_micro"] = 0.0
    SLV.append(x[base_cols])

df_expanded = pd.concat([df_base] + SLV, ignore_index=True)

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

print("Building tables for Base and Expanded books...")
SER_BASE, RISK_BASE = build_tables(df_base)
SER_EXP, RISK_EXP = build_tables(df_expanded)
print("Tables built.")

def simulate_chameleon(SER_B, RISK_B, SER_E, RISK_E, kind, lad, K, gate_threshold=8500.0, sprint=True, a0="2010-07-01", a1="2022-01-01"):
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
            
            # Select table: Base if bal < gate_threshold, Expanded if bal >= gate_threshold
            use_exp = (bal >= gate_threshold)
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
            
            # Sprint early payout @ $6.0k
            if sprint and not paid:
                if bal >= 6000.0:
                    w = 500.0
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

gates = [
    ("Always Base v5.3 (Benchmark)", 1e9, False),
    ("Always Base v5.3 Sprint (Benchmark)", 1e9, True),
    ("Chameleon Gate @ $8.5k (Pure)", 8500.0, False),
    ("Chameleon Gate @ $8.5k (Sprint)", 8500.0, True),
    ("Chameleon Gate @ $8.0k (Pure)", 8000.0, False),
    ("Chameleon Gate @ $8.0k (Sprint)", 8000.0, True),
    ("Chameleon Gate @ $9.0k (Pure)", 9000.0, False),
    ("Chameleon Gate @ $9.0k (Sprint)", 9000.0, True),
]

results = []
for name, gate_val, sprint_on in gates:
    s0 = simulate_chameleon(SER_BASE, RISK_BASE, SER_EXP, RISK_EXP, "S0", lad, 8500.0, gate_val, sprint_on)
    s3 = simulate_chameleon(SER_BASE, RISK_BASE, SER_EXP, RISK_EXP, "S3", lad, 8500.0, gate_val, sprint_on)
    s4 = simulate_chameleon(SER_BASE, RISK_BASE, SER_EXP, RISK_EXP, "S4", lad, 8500.0, gate_val, sprint_on)
    
    safe = (s3["cons"] <= 0.05 and s4["cons"] <= 0.095 and s0["closed"] == 0.0)
    print(f"\n{'[PASS]' if safe else '[FAIL]'} {name}")
    print(f"  24m USD: ${s0['usd']:,.0f} | Y1 USD: ${s0['usd_y1']:,.0f} ({s0['y1_pays']} pays) | P1 Days: {s0['first_days']} cal days")
    print(f"  Risk: S0 ruin {s0['closed']*100:.1f}% | S3 cons {s3['cons']*100:.1f}% | S4 cons {s4['cons']*100:.1f}%")


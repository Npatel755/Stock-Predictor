"""Fine-tuning Chameleon Strategies:
1. Exact threshold scan between $8,500 and $8,700 for Portfolio E (Both).
2. Test Portfolio E Scaled (MES_MOM_2c + MNQ_BRK_E_2c) across gates $8,000 to $8,700.
3. Combine Multi-Milestone early payouts (P1 @ $5.5k -$500, P2 @ $7.0k -$500) with Chameleon.
4. Verify all 4 gates across 139 rolling 24m windows (2010-2023).
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

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
P10 = V["P10"]
ep, bars_for, START = P10["ep"], P10["bars_for"], P10["START"]

df_base = variant("A")
base_cols = df_base.columns

def get_sleeve(name, key="portfolio_e", prio=10):
    sl = next(s for s in ep.CANDIDATES[key]["sleeves"] if s["name"] == name)
    x = pl.price_normalize(pl.sleeve_trades(ep, bars_for, START, dict(sl), prio, False))
    x["n_contracts"] = 1.0
    x["mae_per_micro"] = 0.0
    return x[base_cols]

# Sleeves for Portfolio E (MES_MOM_3c + MNQ_BRK_E_2c)
slv_brk = get_sleeve("MNQ_BRK_E_2c", key="portfolio_e", prio=10)
slv_mom3 = get_sleeve("MES_MOM_3c", key="portfolio_e", prio=11)
df_both = pd.concat([df_base, slv_brk, slv_mom3], ignore_index=True)

# Sleeves for Portfolio E Scaled (MES_MOM_2c + MNQ_BRK_E_2c)
slv_mom2 = get_sleeve("MES_MOM_2c", key="portfolio_e_scaled", prio=11)
df_scaled = pd.concat([df_base, slv_brk, slv_mom2], ignore_index=True)

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

print("Building tables for Base, Full E, and Scaled E...")
SER_BASE, RISK_BASE = build_tables(df_base)
SER_BOTH, RISK_BOTH = build_tables(df_both)
SER_SCALED, RISK_SCALED = build_tables(df_scaled)
print("Tables built successfully.")

def simulate(SER_B, RISK_B, SER_E, RISK_E, kind, lad, K=8500.0, gate_th=8500.0, pacing="sprint", a0="2010-07-01", a1="2022-01-01"):
    keys = [k for k in SER_B if k[0] == kind]
    days = sorted(set().union(*[set(SER_B[k]) for k in keys]))
    ix = pd.to_datetime(pd.Series(days).astype(str)).to_numpy()
    rows = []
    
    for s0 in pd.date_range(a0, a1, freq="MS"):
        a = int(np.searchsorted(ix, np.datetime64(s0)))
        b = int(np.searchsorted(ix, np.datetime64(s0 + pd.DateOffset(months=24))))
        b_12m = int(np.searchsorted(ix, np.datetime64(s0 + pd.DateOffset(months=12))))
        
        bal = 0.0
        paid_count = 0
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
            floor = 0.0 if paid_count > 0 else -2000.0
            
            use_exp = (bal >= gate_th)
            SER = SER_E if use_exp else SER_B
            RISK = RISK_E if use_exp else RISK_B
            
            if bal - RISK[(kind, m)].get(x, 0.0) <= floor:
                cons = True
                
            p = max(SER[(kind, m, bal >= 500.0)].get(x, 0.0), -1000.0)
            bal += p
            since += p
            
            if paid_count == 0:
                low = min(low, bal)
                
            if bal <= floor:
                closed = True
                break
                
            is_y1 = (a + idx) < b_12m
            payout_made = False
            w = 0.0
            
            # Pacing rules
            if pacing == "sprint" and paid_count == 0:
                if bal >= 6000.0:
                    w = 500.0
                    bal -= w
                    usd += w
                    paid_count += 1
                    since = 0.0
                    payout_made = True
            elif pacing == "multi" and paid_count < 2:
                if paid_count == 0 and bal >= 5500.0:
                    w = 500.0
                    bal -= w
                    usd += w
                    paid_count += 1
                    since = 0.0
                    payout_made = True
                elif paid_count == 1 and bal >= 7000.0 and since > 0:
                    w = 500.0
                    bal -= w
                    usd += w
                    paid_count += 1
                    since = 0.0
                    payout_made = True
                    
            if not payout_made:
                if (since > 0 or paid_count == 0) and bal - K >= 250.0:
                    w = min(1500.0, bal - K)
                    bal -= w
                    usd += w
                    paid_count += 1
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

configs = [
    # Full Portfolio E (Both) threshold sweep
    ("Full E (Sprint) Gate @ $8.55k", SER_BOTH, RISK_BOTH, 8550.0, "sprint"),
    ("Full E (Sprint) Gate @ $8.60k", SER_BOTH, RISK_BOTH, 8600.0, "sprint"),
    ("Full E (Sprint) Gate @ $8.65k", SER_BOTH, RISK_BOTH, 8650.0, "sprint"),
    ("Full E (Sprint) Gate @ $8.70k", SER_BOTH, RISK_BOTH, 8700.0, "sprint"),
    ("Full E (Sprint) Gate @ $8.75k", SER_BOTH, RISK_BOTH, 8750.0, "sprint"),
    
    # Full E Multi-Milestone
    ("Full E (Multi-Milestone) Gate @ $8.70k", SER_BOTH, RISK_BOTH, 8700.0, "multi"),
    ("Full E (Multi-Milestone) Gate @ $8.80k", SER_BOTH, RISK_BOTH, 8800.0, "multi"),
    ("Full E (Multi-Milestone) Gate @ $9.00k", SER_BOTH, RISK_BOTH, 9000.0, "multi"),
    
    # Scaled E (MES_MOM_2c) threshold sweep
    ("Scaled E (Sprint) Gate @ $8.0k", SER_SCALED, RISK_SCALED, 8000.0, "sprint"),
    ("Scaled E (Sprint) Gate @ $8.2k", SER_SCALED, RISK_SCALED, 8200.0, "sprint"),
    ("Scaled E (Sprint) Gate @ $8.4k", SER_SCALED, RISK_SCALED, 8400.0, "sprint"),
    ("Scaled E (Sprint) Gate @ $8.5k", SER_SCALED, RISK_SCALED, 8500.0, "sprint"),
    ("Scaled E (Sprint) Gate @ $8.6k", SER_SCALED, RISK_SCALED, 8600.0, "sprint"),
    ("Scaled E (Sprint) Gate @ $8.7k", SER_SCALED, RISK_SCALED, 8700.0, "sprint"),
    ("Scaled E (Multi-Milestone) Gate @ $8.5k", SER_SCALED, RISK_SCALED, 8500.0, "multi"),
    ("Scaled E (Multi-Milestone) Gate @ $8.7k", SER_SCALED, RISK_SCALED, 8700.0, "multi"),
]

base_h1, base_h2 = 18787.0, 33542.0

all_res = []
print("\n" + "="*85)
print(f"{'Config Name':<42} | {'24m USD':<8} | {'H1/H2 USD':<15} | {'P1 Days':<7} | {'Y1 Pays':<7} | {'S3cons':<6} | {'S4cons':<6} | {'Status'}")
print("="*85)

for name, se, re, g_th, pacing in configs:
    s0 = simulate(SER_BASE, RISK_BASE, se, re, "S0", lad, 8500.0, g_th, pacing)
    s3 = simulate(SER_BASE, RISK_BASE, se, re, "S3", lad, 8500.0, g_th, pacing)
    s4 = simulate(SER_BASE, RISK_BASE, se, re, "S4", lad, 8500.0, g_th, pacing)
    
    g1 = (s0["usd_h1"] >= 1.05 * base_h1) and (s0["usd_h2"] >= 1.05 * base_h2)
    g2 = (s0["closed"] <= 0.005)
    g3 = (s3["cons"] <= 0.050) and (s4["cons"] <= 0.095)
    g4 = (s0["near"] <= 0.007)
    
    passed = g1 and g2 and g3 and g4
    status = "PASS" if passed else "FAIL"
    
    print(f"{name:<42} | ${s0['usd']:<7,.0f} | ${s0['usd_h1']:<6,.0f}/${s0['usd_h2']:<6,.0f} | {s0['first_days']:<7.1f} | {s0['y1_pays']:<7.2f} | {s3['cons']*100:<5.1f}% | {s4['cons']*100:<5.1f}% | {status}")
    
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

out_path = ROOT / "reports/RESEARCH_CHAMELEON_FINE_TUNE.json"
out_path.write_text(json.dumps(all_res, indent=2), encoding="utf-8")
print(f"\nSaved fine tune results to {out_path}")

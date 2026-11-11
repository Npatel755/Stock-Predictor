"""Experiment: Chameleon V2 - Stratosphere Tier & Advanced Dynamic Gating
Hypotheses:
1. Stratosphere 5X: When bal >= $10,000 / $11,000 / $12,000, scale to 5x (cap-aware trimmed).
   Since the cushion is $10k+ above the $0 floor, can 5x be run with ZERO tail risk increase?
2. Multi-Tier Sleeves:
   - bal < $8,500: Base v5.3 (1x-4x)
   - bal >= $8,500: + Portfolio E (MNQ_BRK_E_2c + MES_MOM_3c)
   - bal >= $10,500: + GAP Addon (AG_CRABEL15_D_GAP_v53)
3. Faster Sprint:
   - Test Sprint @ $5,600 -$400, $5,800 -$500, $6,000 -$500.
Tested across all 139 rolling 24m windows (2010-2023).
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

slv_brk = get_sleeve("MNQ_BRK_E_2c", key="portfolio_e", prio=10)
slv_mom = get_sleeve("MES_MOM_3c", key="portfolio_e", prio=11)
slv_gap = get_sleeve("AG_CRABEL15_D_GAP_v53", key="ag_arch_d_plus_v2_gap_addon_v53", prio=12)

df_both = pd.concat([df_base, slv_brk, slv_mom], ignore_index=True)
df_tier2 = pd.concat([df_base, slv_brk, slv_mom, slv_gap], ignore_index=True)

def build_tables_5x(df_variant):
    SER, RISK = {}, {}
    for kind in ("S0", "S3", "S4"):
        e = stressed(df_variant, kind)
        _, n = sc17(kind, N0)
        nr = NIGHT_RISK * (1.5 if kind == "S4" else 1.0)
        r = pl.route(e)
        
        for m in (1, 2, 3, 4, 5):
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

print("Building tables with 5x support for Base, Portfolio E, and Tier 2...")
SER_BASE, RISK_BASE = build_tables_5x(df_base)
SER_BOTH, RISK_BOTH = build_tables_5x(df_both)
SER_T2, RISK_T2 = build_tables_5x(df_tier2)
print("Tables built.")

def simulate_v2(kind, lad, K=8400.0, gate1=8500.0, gate2=1e9, sprint_bal=6000.0, sprint_amt=500.0, a0="2010-07-01", a1="2022-01-01"):
    keys = [k for k in SER_BASE if k[0] == kind]
    days = sorted(set().union(*[set(SER_BASE[k]) for k in keys]))
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
            
            # Select table: Base if < gate1, Both if gate1 <= bal < gate2, Tier2 if bal >= gate2
            if bal >= gate2:
                SER, RISK = SER_T2, RISK_T2
            elif bal >= gate1:
                SER, RISK = SER_BOTH, RISK_BOTH
            else:
                SER, RISK = SER_BASE, RISK_BASE
                
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

# Ladder definitions
lad_4x = ((0,1), (4000,2), (4600,3), (5400,4))
lad_5x_10k = ((0,1), (4000,2), (4600,3), (5400,4), (10000,5))
lad_5x_11k = ((0,1), (4000,2), (4600,3), (5400,4), (11000,5))
lad_5x_12k = ((0,1), (4000,2), (4600,3), (5400,4), (12000,5))

tests = [
    # Baseline benchmarks
    ("Current Crown Sprint ($8.4k K, Gate $8.5k)", lad_4x, 8400.0, 8500.0, 1e9, 6000.0, 500.0),
    ("Current Fortified Sprint ($8.5k K, Gate $8.55k)", lad_4x, 8500.0, 8550.0, 1e9, 6000.0, 500.0),
    
    # Faster Sprint Variations on Crown
    ("Crown Sprint @ $5.6k -$400", lad_4x, 8400.0, 8500.0, 1e9, 5600.0, 400.0),
    ("Crown Sprint @ $5.7k -$400", lad_4x, 8400.0, 8500.0, 1e9, 5700.0, 400.0),
    ("Crown Sprint @ $5.8k -$500", lad_4x, 8400.0, 8500.0, 1e9, 5800.0, 500.0),
    
    # Stratosphere 5X Tiers (Tested on Crown)
    ("Stratosphere 5X @ $10.0k", lad_5x_10k, 8400.0, 8500.0, 1e9, 6000.0, 500.0),
    ("Stratosphere 5X @ $11.0k", lad_5x_11k, 8400.0, 8500.0, 1e9, 6000.0, 500.0),
    ("Stratosphere 5X @ $12.0k", lad_5x_12k, 8400.0, 8500.0, 1e9, 6000.0, 500.0),
    
    # Multi-Tier Sleeves (Crown + GAP Addon @ $10.5k)
    ("Multi-Tier Sleeves (T2 @ $10.5k)", lad_4x, 8400.0, 8500.0, 10500.0, 6000.0, 500.0),
    ("Multi-Tier Sleeves (T2 @ $11.0k)", lad_4x, 8400.0, 8500.0, 11000.0, 6000.0, 500.0),
    ("Multi-Tier + Stratosphere 5X @ $11k", lad_5x_11k, 8400.0, 8500.0, 11000.0, 6000.0, 500.0),
]

base_h1, base_h2 = 18787.0, 33542.0
all_res = []

print("\n" + "="*85)
print(f"{'Config Name':<38} | {'24m USD':<8} | {'H1/H2 USD':<15} | {'P1 Days':<7} | {'S3cons':<6} | {'S4cons':<6} | {'Status'}")
print("="*85)

for name, ld, k_val, g1, g2, sp_bal, sp_amt in tests:
    s0 = simulate_v2("S0", ld, k_val, g1, g2, sp_bal, sp_amt)
    s3 = simulate_v2("S3", ld, k_val, g1, g2, sp_bal, sp_amt)
    s4 = simulate_v2("S4", ld, k_val, g1, g2, sp_bal, sp_amt)
    
    g1_pass = (s0["usd_h1"] >= 1.05 * base_h1) and (s0["usd_h2"] >= 1.05 * base_h2)
    g2_pass = (s0["closed"] <= 0.005)
    g3_pass = (s3["cons"] <= 0.050) and (s4["cons"] <= 0.095)
    g4_pass = (s0["near"] <= 0.007)
    
    passed = g1_pass and g2_pass and g3_pass and g4_pass
    status = "PASS" if passed else "FAIL"
    
    print(f"{name:<38} | ${s0['usd']:<7,.0f} | ${s0['usd_h1']:<6,.0f}/${s0['usd_h2']:<6,.0f} | {s0['first_days']:<7.1f} | {s3['cons']*100:<5.1f}% | {s4['cons']*100:<5.1f}% | {status}")
    
    all_res.append(dict(
        name=name,
        usd=s0["usd"],
        usd_h1=s0["usd_h1"],
        usd_h2=s0["usd_h2"],
        p1_days=s0["first_days"],
        y1_pays=s0["y1_pays"],
        usd_y1=s0["usd_y1"],
        s3_cons=s3["cons"],
        s4_cons=s4["cons"],
        s0_near=s0["near"],
        passed=passed
    ))

out_path = ROOT / "reports/RESEARCH_CHAMELEON_V2_RESULTS.json"
out_path.write_text(json.dumps(all_res, indent=2), encoding="utf-8")
print(f"\nSaved results to {out_path}")

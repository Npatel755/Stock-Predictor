"""Research: Uncapped Post-P3 Payouts & Deep Cushion Alpha Sleeves
Explores:
1. Topstep Rule Realism: Cap is $1,500 for P1-P3, but lifts to $2,500 or $3,000 starting at P4.
   Does sweeping accumulated profit faster in deep cushion reduce drawdown exposure and boost total cash?
2. Additional Sleeves in Tier 3 (balance >= $10,000):
   - AG_CRABEL15_D_GAP_v53 (Current Champion)
   - + MNQ_VOL_1c
   - + MNQ_E57_1c
   - + MNQ_HYB_C_1c
Tested across all 139 rolling 24m windows (2010-2023) against Adopted Fortress 4X ($24,895 H1 / $48,176 H2).
"""
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/quant_futures"))
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

def get_sleeve(name, key, prio=10):
    sl = next(s for s in ep.CANDIDATES[key]["sleeves"] if s["name"] == name)
    x = pl.price_normalize(pl.sleeve_trades(ep, bars_for, START, dict(sl), prio, False))
    x["n_contracts"] = 1.0
    x["mae_per_micro"] = 0.0
    return x[base_cols]

slv_brk = get_sleeve("MNQ_BRK_E_2c", "portfolio_e", 10)
slv_mom = get_sleeve("MES_MOM_3c", "portfolio_e", 11)
slv_gap = get_sleeve("AG_CRABEL15_D_GAP_v53", "ag_arch_d_plus_v2_gap_addon_v53", 12)
slv_vol = get_sleeve("MNQ_VOL_1c", "ensemble_epsilon", 13)
slv_e57 = get_sleeve("MNQ_E57_1c", "ensemble_epsilon", 14)

df_both = pd.concat([df_base, slv_brk, slv_mom], ignore_index=True)
df_gap = pd.concat([df_base, slv_brk, slv_mom, slv_gap], ignore_index=True)
df_vol = pd.concat([df_base, slv_brk, slv_mom, slv_gap, slv_vol], ignore_index=True)
df_e57 = pd.concat([df_base, slv_brk, slv_mom, slv_gap, slv_e57], ignore_index=True)

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

print("Building tables for Base, Portfolio E, GAP, VOL, and E57...")
SER_BASE, RISK_BASE = build_tables(df_base)
SER_BOTH, RISK_BOTH = build_tables(df_both)
SER_GAP, RISK_GAP = build_tables(df_gap)
SER_VOL, RISK_VOL = build_tables(df_vol)
SER_E57, RISK_E57 = build_tables(df_e57)
print("Simulation tables ready.")

def simulate_advanced(kind, lad, SER_T2, RISK_T2, K=8600.0, gate1=8700.0, gate2=10000.0, max_p4=1500.0, a0="2010-07-01", a1="2022-01-01"):
    keys = [k for k in SER_BASE if k[0] == kind]
    days = sorted(set().union(*[set(SER_BASE[k]) for k in keys]))
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
            
            if paid_count == 0:
                low = min(low, bal)
                
            if bal <= floor:
                closed = True
                break
                
            is_y1 = (a + idx) < b_12m
            payout_made = False
            w = 0.0
            
            # Sprint early payout @ $6,000 -$500
            if paid_count == 0 and bal >= 6000.0:
                w = 500.0
                bal -= w
                usd += w
                paid_count += 1
                since = 0.0
                payout_made = True
            
            if not payout_made:
                if (since > 0 or paid_count == 0) and bal - K >= 250.0:
                    max_w = 1500.0 if paid_count < 3 else max_p4
                    w = min(max_w, bal - K)
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

lad_4x = ((0,1), (4000,2), (4600,3), (5400,4))
fort_h1, fort_h2 = 24895.0, 48176.0

tests = [
    # Baseline benchmark
    ("Fortified 3-Tier (Max $1.5k Cap)", SER_GAP, RISK_GAP, 8600.0, 8700.0, 10000.0, 1500.0),
    
    # Topstep Rule Realism: Payout Cap Lifts After P3
    ("Fortified 3-Tier (P4+ Cap $2.0k)", SER_GAP, RISK_GAP, 8600.0, 8700.0, 10000.0, 2000.0),
    ("Fortified 3-Tier (P4+ Cap $2.5k)", SER_GAP, RISK_GAP, 8600.0, 8700.0, 10000.0, 2500.0),
    ("Fortified 3-Tier (P4+ Cap $3.0k)", SER_GAP, RISK_GAP, 8600.0, 8700.0, 10000.0, 3000.0),
    
    # Ultra-Safe Cushion ($8.8k K) with P4+ Cap Lift
    ("Ultra-Safe 3-Tier (K $8.8k, Cap $2.5k)", SER_GAP, RISK_GAP, 8800.0, 8900.0, 10000.0, 2500.0),
    ("Ultra-Safe 3-Tier (K $8.8k, Cap $3.0k)", SER_GAP, RISK_GAP, 8800.0, 8900.0, 10000.0, 3000.0),
    
    # Additional Deep-Cushion Alpha Sleeves in Tier 3
    ("Tier 3 GAP + VOL (Cap $1.5k)", SER_VOL, RISK_VOL, 8600.0, 8700.0, 10000.0, 1500.0),
    ("Tier 3 GAP + VOL (P4+ Cap $2.5k)", SER_VOL, RISK_VOL, 8600.0, 8700.0, 10000.0, 2500.0),
    ("Tier 3 GAP + E57 (Cap $1.5k)", SER_E57, RISK_E57, 8600.0, 8700.0, 10000.0, 1500.0),
    ("Tier 3 GAP + E57 (P4+ Cap $2.5k)", SER_E57, RISK_E57, 8600.0, 8700.0, 10000.0, 2500.0),
]

all_res = []
print("\n" + "="*95)
print(f"{'Config Name':<38} | {'24m USD':<8} | {'H1/H2 USD':<15} | {'H1% / H2% vs Fort':<18} | {'S3cons':<6} | {'S4cons':<6} | {'Status'}")
print("="*95)

for name, s_t2, r_t2, k_val, g1, g2, max_p4 in tests:
    s0 = simulate_advanced("S0", lad_4x, s_t2, r_t2, k_val, g1, g2, max_p4)
    s3 = simulate_advanced("S3", lad_4x, s_t2, r_t2, k_val, g1, g2, max_p4)
    s4 = simulate_advanced("S4", lad_4x, s_t2, r_t2, k_val, g1, g2, max_p4)
    
    g1_p = (s0["usd_h1"] >= 1.05 * fort_h1) and (s0["usd_h2"] >= 1.05 * fort_h2)
    g2_p = (s0["closed"] <= 0.005)
    g3_p = (s3["cons"] <= 0.050) and (s4["cons"] <= 0.095)
    g4_p = (s0["near"] <= 0.007)
    
    passed = g1_p and g2_p and g3_p and g4_p
    status = "PASS" if passed else "FAIL"
    
    diff_h1 = (s0["usd_h1"] - fort_h1) / fort_h1 * 100
    diff_h2 = (s0["usd_h2"] - fort_h2) / fort_h2 * 100
    diff_str = f"{diff_h1:+.1f}% / {diff_h2:+.1f}%"
    
    print(f"{name:<38} | ${s0['usd']:<7,.0f} | ${s0['usd_h1']:<6,.0f}/${s0['usd_h2']:<6,.0f} | {diff_str:<18} | {s3['cons']*100:<5.1f}% | {s4['cons']*100:<5.1f}% | {status}")
    
    all_res.append(dict(
        name=name,
        usd=s0["usd"],
        usd_h1=s0["usd_h1"],
        usd_h2=s0["usd_h2"],
        diff_h1=diff_h1,
        diff_h2=diff_h2,
        p1_days=s0["first_days"],
        y1_pays=s0["y1_pays"],
        usd_y1=s0["usd_y1"],
        s0_ruin=s0["closed"],
        s3_cons=s3["cons"],
        s4_cons=s4["cons"],
        s0_near=s0["near"],
        passed=passed
    ))

out_path = ROOT / "reports/RESEARCH_UNCAPPED_AND_SLEEVES.json"
out_path.write_text(json.dumps(all_res, indent=2))
print(f"\nSaved results to {out_path}")

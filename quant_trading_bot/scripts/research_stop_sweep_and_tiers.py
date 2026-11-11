"""Research: Stop Sweep, Tier Grid, and Asymmetric Cushion Scaling
Testing if optimizing the daily stop ($500-$800) and fine-tuning the 4x ladder thresholds
can push cash beyond $36,000 while maintaining 9.4% S4 conservative closure and 5.0% S3.
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
H = V["H"]

d = variant("A")

def build_stop_tables(m_stop_dict):
    """Build SER and RISK with custom stop for each multiplier m."""
    SER, RISK = {}, {}
    for kind in ("S0", "S3", "S4"):
        e = stressed(d, kind)
        _, n = sc17(kind, N0)
        nr = NIGHT_RISK * (1.5 if kind == "S4" else 1.0)
        r = pl.route(e)
        
        for m in (1, 2, 3, 4, 5):
            per = r.net_today / r.n_contracts
            risk = r.risk_today
            q = np.minimum(m * r.n_contracts, np.floor(900.0 / risk)) if m > 1 else r.n_contracts
            i = r.assign(net_today=per * q, q=q)[lambda x: x.q >= 1]
            
            # Night contracts
            qn = (min(m, int(900.0 // nr))) if m > 1 else 1
            nm = n.assign(net_today=n.net_today * qn) if qn >= 1 else n.iloc[0:0]
            
            stop = m_stop_dict.get(m, 700.0)
            SER[(kind, m, False)] = fds(i[["tin", "tout", "net_today"]], stop).to_dict()
            SER[(kind, m, True)] = fds(pd.concat([i[["tin", "tout", "net_today"]], nm], ignore_index=True), stop).to_dict()
            
            rk = (i.risk_today * i.q).groupby(i.tout.dt.date).max()
            if qn >= 1:
                rk = pd.concat([rk, pd.Series(nr * qn, index=pd.Index(n.tout.dt.date))]).groupby(level=0).max()
            RISK[(kind, m)] = rk.to_dict()
            
    return SER, RISK

def simulate_engine(SER, RISK, kind, ladder, K, milestones=None, a0="2010-07-01", a1="2022-01-01"):
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
        
        ms_idx = 0
        ms_list = list(milestones) if milestones else []
        
        for idx, x in enumerate(days[a:b]):
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
            payout_made = False
            w = 0.0
            
            if ms_idx < len(ms_list):
                trig, amt = ms_list[ms_idx]
                if bal >= trig:
                    w = min(amt, bal - 2000.0)
                    bal -= w
                    usd += w
                    paid = True
                    since = 0.0
                    payout_made = True
                    ms_idx += 1
            
            if not payout_made and ms_idx >= len(ms_list):
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

def eval_full(name, SER, RISK, ladder, K, milestones=None):
    s0 = simulate_engine(SER, RISK, "S0", ladder, K, milestones)
    s3 = simulate_engine(SER, RISK, "S3", ladder, K, milestones)
    s4 = simulate_engine(SER, RISK, "S4", ladder, K, milestones)
    h1 = simulate_engine(SER, RISK, "S0", ladder, K, milestones, *H[0])
    h2 = simulate_engine(SER, RISK, "S0", ladder, K, milestones, *H[1])
    return {
        "name": name,
        "s0_usd": s0["usd"],
        "h1_usd": h1["usd"],
        "h2_usd": h2["usd"],
        "s0_y1_usd": s0["usd_y1"],
        "s0_y1_pays": s0["y1_pays"],
        "s0_y2_usd": s0["usd_y2"],
        "s0_y2_pays": s0["y2_pays"],
        "first_days": s0["first_days"],
        "s0_closed": s0["closed"],
        "s3_closed": s3["closed"],
        "s3_cons": s3["cons"],
        "s4_closed": s4["closed"],
        "s4_cons": s4["cons"],
        "s0_near": s0["near"]
    }

# Test different stop configurations
stop_configs = {
    "Stop 700 (Current)": {1: 400.0, 2: 700.0, 3: 700.0, 4: 700.0, 5: 700.0},
    "Stop 600": {1: 400.0, 2: 600.0, 3: 600.0, 4: 600.0, 5: 600.0},
    "Stop 650": {1: 400.0, 2: 650.0, 3: 650.0, 4: 650.0, 5: 650.0},
    "Stop 750": {1: 400.0, 2: 750.0, 3: 750.0, 4: 750.0, 5: 750.0},
    "Stop 800": {1: 400.0, 2: 800.0, 3: 800.0, 4: 800.0, 5: 800.0},
    "Dynamic Stop (m1:400, m2:550, m3:700, m4:800)": {1: 400.0, 2: 550.0, 3: 700.0, 4: 800.0, 5: 850.0},
}

all_results = []
for sname, sdict in stop_configs.items():
    print(f"\nBuilding tables for {sname}...")
    ser, risk = build_stop_tables(sdict)
    
    # Test on Multi-Milestone A
    res_a = eval_full(f"Multi-Milestone A | {sname}", ser, risk, ((0,1), (4000,2), (4800,3), (5800,4)), 8500.0, [(5500.0, 500.0), (7000.0, 500.0)])
    all_results.append(res_a)
    print(f"  Multi-Milestone A: 24m ${res_a['s0_usd']:,.0f} | Y1 ${res_a['s0_y1_usd']:,.0f} ({res_a['s0_y1_pays']} pays) | P1 {res_a['first_days']}d | S3 cons {res_a['s3_cons']*100:.1f}% | S4 cons {res_a['s4_cons']*100:.1f}%")
    
    # Test on Pure Fast-4X
    res_b = eval_full(f"Fast-4X Pure | {sname}", ser, risk, ((0,1), (4000,2), (4800,3), (5800,4)), 8500.0, None)
    all_results.append(res_b)
    print(f"  Fast-4X Pure:      24m ${res_b['s0_usd']:,.0f} | Y1 ${res_b['s0_y1_usd']:,.0f} ({res_b['s0_y1_pays']} pays) | P1 {res_b['first_days']}d | S3 cons {res_b['s3_cons']*100:.1f}% | S4 cons {res_b['s4_cons']*100:.1f}%")

out_file = ROOT / "reports/RESEARCH_STOP_SWEEP_RESULTS.json"
out_file.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
print(f"\nAll results saved to {out_file}")

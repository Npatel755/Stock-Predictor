"""Research Alpha Innovations on Top of Convex 4X Architecture
Testing strategy alpha enhancements:
1. Cell A (Current v5.3: drop TRD30PM)
2. Cell A+B (v5.3 + Crabel Continuation 3c with Cap-Aware Trimming)
3. Cell A+C (v5.3 + Skip Crabel Fades)
4. Cell A+B+C (v5.3 + Continuation 3c + Skip Fades)
5. Cell A + MES 2c base (MES Trend at 2 micros base)
6. Cell A + Asymmetric Sizing (Crabel & Trend 4x, Overnight capped at 2c)
All tested across 139 rolling 24m windows with Convex Ladder:
(1x <$4k, 2x $4k-$4.6k, 3x $4.6k-$5.4k, 4x >=$5.4k | K=$8.5k | Stop $700)
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

def get_variant_trades(opt):
    if opt == "A":
        return variant("A")
    elif opt == "AB":
        return variant(["A", "B"])
    elif opt == "AC":
        return variant(["A", "C"])
    elif opt == "ABC":
        return variant(["A", "B", "C"])
    elif opt == "A_MES2":
        d = variant("A").copy()
        mes = d.sleeve.str.contains("MES")
        d.loc[mes, "net_today"] *= 2.0
        d.loc[mes, "n_contracts"] *= 2.0
        return d
    elif opt == "AB_MES2":
        d = variant(["A", "B"]).copy()
        mes = d.sleeve.str.contains("MES")
        d.loc[mes, "net_today"] *= 2.0
        d.loc[mes, "n_contracts"] *= 2.0
        return d
    return variant("A")

def build_tables(df_variant, night_cap=None):
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
            
            m_night = min(m, night_cap) if night_cap is not None else m
            qn = (min(m_night, int(900.0 // nr))) if m_night > 1 else 1
            nm = n.assign(net_today=n.net_today * qn) if qn >= 1 else n.iloc[0:0]
            
            stop = 400.0 if m == 1 else 700.0
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

def eval_candidate(name, df_v, night_cap=None):
    ser, risk = build_tables(df_v, night_cap)
    lad = ((0,1), (4000,2), (4600,3), (5400,4))
    
    # 1. Pure Convex
    s0_p = simulate_engine(ser, risk, "S0", lad, 8500.0, None)
    s3_p = simulate_engine(ser, risk, "S3", lad, 8500.0, None)
    s4_p = simulate_engine(ser, risk, "S4", lad, 8500.0, None)
    h1_p = simulate_engine(ser, risk, "S0", lad, 8500.0, None, *H[0])
    h2_p = simulate_engine(ser, risk, "S0", lad, 8500.0, None, *H[1])
    
    # 2. Sprint Convex (P1 @ $6.0k -$500)
    s0_s = simulate_engine(ser, risk, "S0", lad, 8500.0, [(6000.0, 500.0)])
    s3_s = simulate_engine(ser, risk, "S3", lad, 8500.0, [(6000.0, 500.0)])
    s4_s = simulate_engine(ser, risk, "S4", lad, 8500.0, [(6000.0, 500.0)])
    
    return {
        "name": name,
        "pure": {
            "usd": s0_p["usd"],
            "h1": h1_p["usd"],
            "h2": h2_p["usd"],
            "y1_usd": s0_p["usd_y1"],
            "y1_pays": s0_p["y1_pays"],
            "p1_days": s0_p["first_days"],
            "s3_cons": s3_p["cons"],
            "s4_cons": s4_p["cons"],
            "s0_closed": s0_p["closed"],
            "s3_closed": s3_p["closed"],
            "s4_closed": s4_p["closed"]
        },
        "sprint": {
            "usd": s0_s["usd"],
            "y1_usd": s0_s["usd_y1"],
            "y1_pays": s0_s["y1_pays"],
            "p1_days": s0_s["first_days"],
            "s3_cons": s3_s["cons"],
            "s4_cons": s4_s["cons"],
            "s0_closed": s0_s["closed"],
            "s3_closed": s3_s["closed"],
            "s4_closed": s4_s["closed"]
        }
    }

options = [
    ("Base v5.3 (Cell A)", get_variant_trades("A")),
    ("v5.3 + Continuation 3c (Cell AB)", get_variant_trades("AB")),
    ("v5.3 + Skip Fades (Cell AC)", get_variant_trades("AC")),
    ("v5.3 + Cont 3c + Skip Fades (Cell ABC)", get_variant_trades("ABC")),
    ("v5.3 + MES 2c", get_variant_trades("A_MES2")),
    ("v5.3 + Cont 3c + MES 2c", get_variant_trades("AB_MES2")),
]

results = []
for name, df_v in options:
    res = eval_candidate(name, df_v)
    results.append(res)
    p = res["pure"]
    s = res["sprint"]
    safe_p = (p["s3_cons"] <= 0.05 and p["s4_cons"] <= 0.095 and p["s0_closed"] == 0.0)
    print(f"\n{'[PASS]' if safe_p else '[FAIL]'} {name}")
    print(f"  PURE:   24m ${p['usd']:,.0f} (H1 ${p['h1']:,.0f} | H2 ${p['h2']:,.0f}) | Y1 ${p['y1_usd']:,.0f} ({p['y1_pays']} pays) | P1 {p['p1_days']}d | S3 {p['s3_cons']*100:.1f}% | S4 {p['s4_cons']*100:.1f}%")
    print(f"  SPRINT: 24m ${s['usd']:,.0f} | Y1 ${s['y1_usd']:,.0f} ({s['y1_pays']} pays) | P1 {s['p1_days']}d | S3 {s['s3_cons']*100:.1f}% | S4 {s['s4_cons']*100:.1f}%")

out_file = ROOT / "reports/RESEARCH_ALPHA_CONVEX_RESULTS.json"
out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
print(f"\nAll alpha results saved to {out_file}")

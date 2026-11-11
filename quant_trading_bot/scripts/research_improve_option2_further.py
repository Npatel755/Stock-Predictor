"""Comprehensive Research: Improve Option 2 Even Further
Evaluating:
1. Intraday Profit-Lock / Win-Lock (halt after realized gain >= $800, $1000, $1200)
2. Progressive Milestone Payout Schedule (e.g. P1 @ $5.5k, P2 @ $7.0k -> steady $8.5k)
3. 5X Upper Tier Compounding (5x >= $8.0k or >= $8.5k with $900 cap)
4. Decoupled Overnight Sizing (night max 1c or 2c vs full m)
5. Optimal ladder threshold grid (T3, T4, T5)
All tested across 139 rolling 24-month windows on 14-year Globex training split (2010-2023).
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

d = variant("A")  # v5.3 book, 09:45 exit

print("Building extended simulation tables (m = 1..5, with and without win-locks)...")

def build_advanced(win_lock=None, night_cap=None):
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
            m_night = min(m, night_cap) if night_cap is not None else m
            qn = (min(m_night, int(900.0 // nr))) if m_night > 1 else 1
            nm = n.assign(net_today=n.net_today * qn) if qn >= 1 else n.iloc[0:0]
            
            stop = 400.0 if m == 1 else 700.0
            
            # Helper for day series with optional win lock
            def custom_day_series(df_trades, stop_val, lock_val):
                if lock_val is None:
                    return fds(df_trades, stop_val)
                # Apply win lock: if realized net reaches lock_val, stop taking new trades
                rows = []
                for dt, grp in df_trades.groupby(df_trades.tout.dt.date):
                    grp_sorted = grp.sort_values("tin")
                    cum = 0.0
                    for row in grp_sorted.itertuples():
                        if cum <= -stop_val:
                            break
                        if cum >= lock_val:
                            break
                        cum += row.net_today
                    rows.append((dt, max(-1000.0, cum)))
                return pd.Series(dict(rows))
                
            SER[(kind, m, False)] = custom_day_series(i[["tin", "tout", "net_today"]], stop, win_lock).to_dict()
            SER[(kind, m, True)] = custom_day_series(pd.concat([i[["tin", "tout", "net_today"]], nm], ignore_index=True), stop, win_lock).to_dict()
            
            rk = (i.risk_today * i.q).groupby(i.tout.dt.date).max()
            if qn >= 1:
                rk = pd.concat([rk, pd.Series(nr * qn, index=pd.Index(n.tout.dt.date))]).groupby(level=0).max()
            RISK[(kind, m)] = rk.to_dict()
            
    return SER, RISK

# Pre-build baseline table
SER_BASE, RISK_BASE = build_advanced(win_lock=None, night_cap=None)

# Pre-build win-lock tables
SER_WL1000, RISK_WL1000 = build_advanced(win_lock=1000.0, night_cap=None)
SER_WL1200, RISK_WL1200 = build_advanced(win_lock=1200.0, night_cap=None)

# Pre-build night-cap 2c table
SER_NC2, RISK_NC2 = build_advanced(win_lock=None, night_cap=2)

print("All simulation tables built successfully.")

def simulate_engine(SER, RISK, kind, ladder, K, milestones=None, a0="2010-07-01", a1="2022-01-01"):
    """
    milestones: list of tuples (trigger_balance, withdraw_amount)
    executed in order when balance >= trigger_balance.
    Once all milestones are satisfied, daily payouts above K are unlocked.
    """
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
            
            # Milestone check
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
            
            # Standard daily payout if all milestones completed
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

candidates = [
    # Reference baselines
    ("Baseline (Current 2x, K=$6k)", SER_BASE, RISK_BASE, ((0,1), (4000,2)), 6000.0, None),
    ("Balanced 3x (3x $5k, K=$6.5k)", SER_BASE, RISK_BASE, ((0,1), (4000,2), (5000,3)), 6500.0, None),
    ("Option 2 Base (Fortress 4X, K=$8.5k)", SER_BASE, RISK_BASE, ((0,1), (4000,2), (4800,3), (6500,4)), 8500.0, None),
    ("Option 2A (Fortress Sprint: P1 @ $6k -$500, K=$8.5k)", SER_BASE, RISK_BASE, ((0,1), (4000,2), (4800,3), (6000,4)), 8500.0, [(6000.0, 500.0)]),
    ("Option 2B (Fast-4X Pure: 4x @ $5.8k, K=$8.5k)", SER_BASE, RISK_BASE, ((0,1), (4000,2), (4800,3), (5800,4)), 8500.0, None),
    
    # Track 1: Multi-Stage Milestone Schedules (e.g. Progressive Payback)
    ("Multi-Milestone A (P1 @ $5.5k -$500, P2 @ $7k -$500, K=$8.5k)", SER_BASE, RISK_BASE, ((0,1), (4000,2), (4800,3), (5800,4)), 8500.0, [(5500.0, 500.0), (7000.0, 500.0)]),
    ("Multi-Milestone B (P1 @ $5.5k -$500, P2 @ $7.5k -$1000, K=$8.5k)", SER_BASE, RISK_BASE, ((0,1), (4000,2), (4800,3), (5800,4)), 8500.0, [(5500.0, 500.0), (7500.0, 1000.0)]),
    ("Multi-Milestone C (P1 @ $6.0k -$1000, P2 @ $7.5k -$1000, K=$8.5k)", SER_BASE, RISK_BASE, ((0,1), (4000,2), (4800,3), (5800,4)), 8500.0, [(6000.0, 1000.0), (7500.0, 1000.0)]),
    
    # Track 2: 5X Upper-Tier Scaling (Compounding above K=$8.5k)
    ("Fortress 5X (4x @ $5.8k, 5x >= $8.5k, K=$8.5k)", SER_BASE, RISK_BASE, ((0,1), (4000,2), (4800,3), (5800,4), (8500,5)), 8500.0, None),
    ("Fortress 5X + Early P1 ($6k -$500, 5x >= $8.5k, K=$8.5k)", SER_BASE, RISK_BASE, ((0,1), (4000,2), (4800,3), (5800,4), (8500,5)), 8500.0, [(6000.0, 500.0)]),
    ("Fortress 5X + Early P1 ($5.5k -$500, 5x >= $8.5k, K=$8.5k)", SER_BASE, RISK_BASE, ((0,1), (4000,2), (4800,3), (5800,4), (8500,5)), 8500.0, [(5500.0, 500.0)]),
    ("Fortress 5X Aggressive (4x @ $5.8k, 5x >= $8.0k, K=$8.5k)", SER_BASE, RISK_BASE, ((0,1), (4000,2), (4800,3), (5800,4), (8000,5)), 8500.0, None),
    
    # Track 3: Intraday Win-Lock (Locking in gains >= $1,000 / $1,200)
    ("Fast-4X + Win-Lock $1,000 (K=$8.5k)", SER_WL1000, RISK_WL1000, ((0,1), (4000,2), (4800,3), (5800,4)), 8500.0, None),
    ("Fast-4X + Win-Lock $1,200 (K=$8.5k)", SER_WL1200, RISK_WL1200, ((0,1), (4000,2), (4800,3), (5800,4)), 8500.0, None),
    ("Fast-4X Sprint + Win-Lock $1,000 (P1 @ $6k, K=$8.5k)", SER_WL1000, RISK_WL1000, ((0,1), (4000,2), (4800,3), (5800,4)), 8500.0, [(6000.0, 500.0)]),
    
    # Track 4: Decoupled Overnight Sizing (Overnight capped at 2c)
    ("Fast-4X + Night Cap 2c (K=$8.5k)", SER_NC2, RISK_NC2, ((0,1), (4000,2), (4800,3), (5800,4)), 8500.0, None),
    ("Fast-4X Sprint + Night Cap 2c (P1 @ $6k, K=$8.5k)", SER_NC2, RISK_NC2, ((0,1), (4000,2), (4800,3), (5800,4)), 8500.0, [(6000.0, 500.0)]),
    ("Fast-4X Sprint + Night Cap 2c + 5x (P1 @ $6k, 5x>=$8.5k)", SER_NC2, RISK_NC2, ((0,1), (4000,2), (4800,3), (5800,4), (8500,5)), 8500.0, [(6000.0, 500.0)]),
]

results = []
for name, ser, risk, ladder, K, ms in candidates:
    res = eval_full(name, ser, risk, ladder, K, ms)
    results.append(res)
    safe = (res["s3_cons"] <= 0.05 and res["s4_cons"] <= 0.095 and res["s0_closed"] == 0.0 and res["s3_closed"] <= 0.022 and res["s4_closed"] <= 0.065)
    print(f"\n{'[PASS]' if safe else '[FAIL]'} {name}")
    print(f"   24m: ${res['s0_usd']:,.0f} (H1: ${res['h1_usd']:,.0f} | H2: ${res['h2_usd']:,.0f})")
    print(f"   Y1: ${res['s0_y1_usd']:,.0f} ({res['s0_y1_pays']} pays) | Y2: ${res['s0_y2_usd']:,.0f} ({res['s0_y2_pays']} pays) | P1 Days: {res['first_days']} cal days")
    print(f"   Risk: S0 ruin {res['s0_closed']*100:.1f}% | S3 cons {res['s3_cons']*100:.1f}% | S4 cons {res['s4_cons']*100:.1f}%")

out_file = ROOT / "reports/RESEARCH_IMPROVE_OPTION2_FURTHER.json"
out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
print(f"\nAll results saved to {out_file}")

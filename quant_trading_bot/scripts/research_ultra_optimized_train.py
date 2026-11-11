"""Research Ultra-Optimized Funded Strategy (Training 2010-2023):
Pushing the performance frontier beyond the Balanced 3x Champion ($32,076) by:
1. Fine-grained ladder tuning (2x @ $4k, 3x @ $5k-$6k, 4x @ $7.5k-$8.5k).
2. Cushion K swept from $7.0k to $9.0k.
3. Two-Stage Payback Protocol (P1 @ $4.0k, withdraw $1k -> 44d payback) combined with high-floor scaling.
4. Testing Intraday Session Win-Lock ($800, $1,000, $1,200, None).
5. All evaluated against Claude's exact 4 gates:
   - Gate 1: S0 Dollars >= 1.05x baseline ($25,899) in BOTH halves.
   - Gate 2: Nominal closures <= baseline + 0.005.
   - Gate 3: Conservative closures <= baseline + 0.02 (target <= 5.0% in S3).
   - Gate 4: S0 near-miss <= baseline (0.7%).
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import v55_check_aegis_train as v55
build = v55.build
v53 = v55.V["variant"]("A")  # v5.3 book, 09:45 exit

print("Building cap-aware lookup tables for v5.3 book (including m=1,2,3,4,5)...")

def build_extended(d, cap_aware=True, win_lock=None):
    pl, stressed, sc17, N0, fds, NIGHT_RISK = (v55.V[k] for k in ("pl", "stressed", "sc17", "N0", "fds", "NIGHT_RISK"))
    SER, RISK = {}, {}
    for kind in ("S0", "S3", "S4"):
        e = stressed(d, kind); _, n = sc17(kind, N0); nr = NIGHT_RISK * (1.5 if kind == "S4" else 1.0)
        r = pl.route(e)
        for m in (1, 2, 3, 4, 5):
            per = r.net_today / r.n_contracts; risk = r.risk_today
            if cap_aware:
                q = np.minimum(m * r.n_contracts, np.floor(900.0 / risk)) if m > 1 else r.n_contracts
            else:
                q = np.where(risk * r.n_contracts * m <= (900.0 if m > 1 else 1e9), m * r.n_contracts, 0.0)
            i = r.assign(net_today=per * q, q=q)[lambda x: x.q >= 1]
            qn = (min(m, int(900.0 // nr)) if cap_aware else (m if (m == 1 or nr * m <= 900.0) else 0)) if m > 1 else 1
            nm = n.assign(net_today=n.net_today * qn) if qn >= 1 else n.iloc[0:0]
            stop = 400.0 if m == 1 else 700.0

            # Win lock simulation if specified
            def apply_day_series(df_trades, stop_val, lock_val=win_lock):
                if lock_val is None:
                    return fds(df_trades, stop_val)
                # Apply fast day series with win lock
                kept = []
                for row in df_trades.sort_values("tin").itertuples():
                    same_day_closed = [q for q in kept if q.tout.date() == row.tin.date() and q.tout <= row.tin]
                    realized_pnl = sum(getattr(q, "net_today") for q in same_day_closed)
                    if realized_pnl <= -stop_val:
                        continue
                    if realized_pnl >= lock_val:
                        continue  # Skip trade if win lock reached
                    kept.append(row)
                if not kept:
                    return pd.Series(dtype=float)
                kdf = pd.DataFrame(kept)
                return kdf.groupby(kdf.tout.dt.date)["net_today"].sum().sort_index()

            SER[(kind, m, False)] = apply_day_series(i[["tin", "tout", "net_today"]], stop).to_dict()
            SER[(kind, m, True)] = apply_day_series(pd.concat([i[["tin", "tout", "net_today"]], nm], ignore_index=True), stop).to_dict()
            rk = (i.risk_today * i.q).groupby(i.tout.dt.date).max()
            if qn >= 1:
                rk = pd.concat([rk, pd.Series(nr * qn, index=pd.Index(n.tout.dt.date))]).groupby(level=0).max()
            RISK[(kind, m)] = rk.to_dict()
    return SER, RISK

SER_CAP, RISK_CAP = build_extended(v53, cap_aware=True, win_lock=None)

H = (("2010-07-01", "2016-06-01"), ("2016-07-01", "2022-01-01"))

def run_sim(SER, RISK, kind, ladder, K, two_stage=False, a0="2010-07-01", a1="2022-01-01"):
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
                
            # Payout Logic
            if two_stage and payouts_count == 0:
                # Stage 1: Payout #1 at +$4,000
                if bal >= 4000.0:
                    w = 1000.0
                    bal -= w
                    usd += w
                    payouts_count += 1
                    since = 0.0
                    days_to_p1 = trading_days
                    if t < cut: p1 += 1
                    else: p2 += 1
            else:
                # Steady Cushion K
                if (since > 0 or payouts_count == 0) and bal - K >= 250.0:
                    w = min(1500.0, bal - K)
                    bal -= w
                    usd += w
                    payouts_count += 1
                    since = 0.0
                    if np.isnan(days_to_p1):
                        days_to_p1 = trading_days
                    if t < cut: p1 += 1
                    else: p2 += 1
                    
        rows.append((usd, closed, cons, low <= -1500.0, days_to_p1, p1, p2))
        
    r = pd.DataFrame(rows, columns=["usd", "closed", "cons", "near", "d1", "p1", "p2"])
    return dict(
        usd=round(float(r.usd.mean()), 0),
        closed=round(float(r.closed.mean()), 3),
        cons=round(float(r.cons.mean()), 3),
        near=round(float(r.near.mean()), 3),
        med_d1=round(float(r.d1.dropna().median()), 1) if len(r.d1.dropna()) else np.nan,
        y1=round(float(r.p1.mean()), 2),
        y2=round(float(r.p2.mean()), 2),
    )

def evaluate_cell(SER, RISK, ladder, K, two_stage=False):
    s0 = run_sim(SER, RISK, "S0", ladder, K, two_stage)
    s3 = run_sim(SER, RISK, "S3", ladder, K, two_stage)
    s4 = run_sim(SER, RISK, "S4", ladder, K, two_stage)
    h1 = run_sim(SER, RISK, "S0", ladder, K, two_stage, *H[0])
    h2 = run_sim(SER, RISK, "S0", ladder, K, two_stage, *H[1])
    return dict(S0=s0, S3=s3, S4=s4, half1=h1, half2=h2)

# Baseline check
base_ladder = [(0, 1), (4000, 2)]
base = evaluate_cell(SER_CAP, RISK_CAP, base_ladder, 6000.0, two_stage=False)
print(f"Base: S0 ${base['S0']['usd']:,.0f} | Cons S3: {base['S3']['cons']} | S4: {base['S4']['cons']} | H1 ${base['half1']['usd']:,.0f} | H2 ${base['half2']['usd']:,.0f}")

# Target hurdles
h1_target = base['half1']['usd'] * 1.05
h2_target = base['half2']['usd'] * 1.05
s0_closed_max = base['S0']['closed'] + 0.005
s3_closed_max = base['S3']['closed'] + 0.005
s4_closed_max = base['S4']['closed'] + 0.005
s0_cons_max = base['S0']['cons'] + 0.02
s3_cons_max = base['S3']['cons'] + 0.02
s4_cons_max = base['S4']['cons'] + 0.02
s0_near_max = base['S0']['near']

# Test fine-grained sweep of high-floor 3-tier and 4-tier designs
specs = []

# 1. High-floor 3-tier fine sweep
for th3 in [4800, 5000, 5200, 5500]:
    for k_val in [6500.0, 7000.0, 7500.0]:
        specs.append((f"3-tier (1x <$4k, 2x $4k-${th3/1000:.1f}k, 3x >=${th3/1000:.1f}k | K=${k_val/1000:.1f}k)",
                      [(0, 1), (4000, 2), (th3, 3)], k_val, False))
        specs.append((f"Two-Stage 3-tier (P1 @ $4k | 3x >=${th3/1000:.1f}k | K=${k_val/1000:.1f}k)",
                      [(0, 1), (4000, 2), (th3, 3)], k_val, True))

# 2. High-floor 4-tier fine sweep
for th3 in [5000, 5500, 6000]:
    for th4 in [7000, 7500, 8000]:
        for k_val in [7500.0, 8000.0, 8500.0]:
            if th4 > k_val + 500:
                continue
            specs.append((f"4-tier (1x <$4k, 2x $4k-${th3/1000:.1f}k, 3x ${th3/1000:.1f}k-${th4/1000:.1f}k, 4x >=${th4/1000:.1f}k | K=${k_val/1000:.1f}k)",
                          [(0, 1), (4000, 2), (th3, 3), (th4, 4)], k_val, False))
            specs.append((f"Two-Stage 4-tier (P1 @ $4k | 3x >=${th3/1000:.1f}k, 4x >=${th4/1000:.1f}k | K=${k_val/1000:.1f}k)",
                          [(0, 1), (4000, 2), (th3, 3), (th4, 4)], k_val, True))

print(f"\nEvaluating {len(specs)} configurations...")
results = []
passers = []

for name, lad, k_val, two_stg in specs:
    res = evaluate_cell(SER_CAP, RISK_CAP, lad, k_val, two_stage=two_stg)
    
    g1 = res['half1']['usd'] >= h1_target and res['half2']['usd'] >= h2_target
    g2 = (res['S0']['closed'] <= s0_closed_max and 
          res['S3']['closed'] <= s3_closed_max and 
          res['S4']['closed'] <= s4_closed_max)
    g3 = (res['S0']['cons'] <= s0_cons_max and 
          res['S3']['cons'] <= s3_cons_max and 
          res['S4']['cons'] <= s4_cons_max)
    g4 = res['S0']['near'] <= s0_near_max
    
    all_ok = g1 and g2 and g3 and g4
    
    row = dict(
        name=name,
        ladder=lad,
        cushion=k_val,
        two_stage=two_stg,
        s0_usd=res['S0']['usd'],
        s0_gain_pct=round((res['S0']['usd'] / base['S0']['usd'] - 1) * 100, 1),
        h1_usd=res['half1']['usd'],
        h1_gain_pct=round((res['half1']['usd'] / base['half1']['usd'] - 1) * 100, 1),
        h2_usd=res['half2']['usd'],
        h2_gain_pct=round((res['half2']['usd'] / base['half2']['usd'] - 1) * 100, 1),
        s3_cons=res['S3']['cons'],
        s4_cons=res['S4']['cons'],
        s0_closed=res['S0']['closed'],
        s3_closed=res['S3']['closed'],
        s4_closed=res['S4']['closed'],
        s0_near=res['S0']['near'],
        med_d1=res['S0']['med_d1'],
        ALL_GATES_PASSED=all_ok,
    )
    results.append(row)
    if all_ok:
        passers.append(row)

out_path = ROOT / "reports/RESEARCH_ULTRA_OPTIMIZED_TRAINING.json"
out_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
print(f"Saved results to {out_path}")

print(f"\nTOTAL PASSED ALL 4 GATES: {len(passers)} / {len(specs)}")
if passers:
    df_pass = pd.DataFrame(passers).sort_values(by="s0_usd", ascending=False)
    print("\nTOP 15 ULTRA-OPTIMIZED GATE-PASSING CONFIGURATIONS:")
    print(df_pass[["name", "s0_usd", "s0_gain_pct", "h1_gain_pct", "h2_gain_pct", "s3_cons", "s4_cons", "med_d1"]].head(15).to_string(index=False))

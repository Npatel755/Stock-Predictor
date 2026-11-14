import sys
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/quant_futures"))

src = (ROOT / "scripts/research_uncapped_and_sleeves.py").read_text(encoding="utf-8")
V = {"__name__": "v", "__file__": str(ROOT / "scripts/research_uncapped_and_sleeves.py")}
exec(src.split("tests = [")[0], V)

build_tables = V["build_tables"]
lad_4x = V["lad_4x"]
fort_h1, fort_h2 = 24895.0, 48176.0

P10 = V["P10"]
ep, bars_for, START = P10["ep"], P10["bars_for"], P10["START"]
df_base = V["df_base"]
base_cols = df_base.columns
pl = V["pl"]

def get_sleeve(name, key, prio=15, contracts=1.0):
    sl = next(s for s in ep.CANDIDATES[key]["sleeves"] if s["name"] == name)
    x = pl.price_normalize(pl.sleeve_trades(ep, bars_for, START, dict(sl), prio, False))
    x["n_contracts"] = float(contracts)
    x["mae_per_micro"] = 0.0
    return x[base_cols]

slv_brk = V["slv_brk"]
slv_mom = V["slv_mom"]
slv_gap = V["slv_gap"]
slv_vol = V["slv_vol"]
slv_brk30 = get_sleeve("AG_BRK30_1c", "ag_all_weather", 16)
slv_morn30 = get_sleeve("AG_MORN30_1c", "ag_quad", 17)
slv_trd30pm = get_sleeve("AG_TRD30PM_1c_v52", "ag_arch_d_plus_v2_1c_v52", 18)
slv_trd60q = get_sleeve("AG_TRD60Q_1c", "ag_quad", 19)
slv_mes_mom = get_sleeve("MES_MOM_1c", "ensemble_epsilon", 20)
slv_trd60_d = get_sleeve("AG_TRD60_D_1c_v53", "ag_arch_d_plus_v2_1c_v53", 21)
slv_crabel15 = get_sleeve("AG_CRABEL15_1c", "ag_arch_c_v2", 22)
slv_crabel15_d = get_sleeve("AG_CRABEL15_D_1c_v53", "ag_arch_d_plus_v2_1c_v53", 23)
slv_hyb = get_sleeve("MNQ_HYB_C_1c", "ensemble_beta", 24)

df_nonet = pd.concat([df_base, slv_brk, slv_mom, slv_gap, slv_vol,
                      slv_brk30, slv_morn30, slv_trd30pm, slv_trd60q,
                      slv_mes_mom, slv_trd60_d, slv_crabel15, slv_crabel15_d, slv_hyb], ignore_index=True)

s_tab, r_tab = build_tables(df_nonet)

SER_BASE = V["SER_BASE"]
RISK_BASE = V["RISK_BASE"]

def simulate_custom(kind, lad, SER_T2, RISK_T2, K=8600.0, gate=8650.0,
                    p1_thresh=6000.0, p1_amt=500.0,
                    max_cap_base=1500.0, deep_cap_thresh=12250.0, max_cap_deep=2500.0,
                    a0="2010-07-01", a1="2022-01-01"):
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
            
            if bal >= gate:
                SER, RISK = SER_T2, RISK_T2
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
            
            # Milestone 1:
            if paid_count == 0 and bal >= p1_thresh:
                w = p1_amt
                bal -= w
                usd += w
                paid_count += 1
                since = 0.0
                payout_made = True
            
            # Standard daily profit withdrawals above K:
            if not payout_made:
                if (since > 0 or paid_count == 0) and bal - K >= 250.0:
                    current_cap = max_cap_deep if bal >= deep_cap_thresh else max_cap_base
                    max_w = 1500.0 if paid_count < 3 else current_cap
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

print("="*95)
print("AUDITING CHAMELEON NONET APEX ACROSS ALL 5 STRESS SCENARIOS")
print("="*95)

for sc in ["S0", "S1", "S2", "S3", "S4"]:
    res = simulate_custom(sc, lad_4x, s_tab, r_tab, 8600.0, 8650.0, deep_cap_thresh=12250.0, max_cap_deep=2500.0)
    h1_pct = (res["usd_h1"] - fort_h1) / fort_h1 * 100
    h2_pct = (res["usd_h2"] - fort_h2) / fort_h2 * 100
    print(f"Scenario {sc} | 24m: ${res['usd']:<7,.0f} | H1: ${res['usd_h1']:<6,.0f} ({h1_pct:+.1f}%) | H2: ${res['usd_h2']:<6,.0f} ({h2_pct:+.1f}%) | Y1: ${res['usd_y1']:<6,.0f} | P1d: {res['first_days']:.0f} | Nom Closed: {res['closed']*100:.1f}% | Cons Closed: {res['cons']*100:.1f}% | Near: {res['near']*100:.1f}%")

print()
print("="*95)
print("COMPARISON: STANDARD $1,500 FLAT CAP")
print("="*95)
for sc in ["S0", "S1", "S2", "S3", "S4"]:
    res = simulate_custom(sc, lad_4x, s_tab, r_tab, 8600.0, 8650.0, max_cap_deep=1500.0)
    h1_pct = (res["usd_h1"] - fort_h1) / fort_h1 * 100
    h2_pct = (res["usd_h2"] - fort_h2) / fort_h2 * 100
    print(f"Scenario {sc} | 24m: ${res['usd']:<7,.0f} | H1: ${res['usd_h1']:<6,.0f} ({h1_pct:+.1f}%) | H2: ${res['usd_h2']:<6,.0f} ({h2_pct:+.1f}%) | Y1: ${res['usd_y1']:<6,.0f} | P1d: {res['first_days']:.0f} | Nom Closed: {res['closed']*100:.1f}% | Cons Closed: {res['cons']*100:.1f}% | Near: {res['near']*100:.1f}%")

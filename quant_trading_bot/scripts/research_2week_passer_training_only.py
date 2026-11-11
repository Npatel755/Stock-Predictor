"""Research: Achieving ~2-Week Average Pass Time STRICTLY on 14-Year Training Split (2010-2023).
METHODOLOGICAL INVARIANT:
- 100% RESTRICTED TO TRAINING DATA (2010-06-01 to 2023-12-31).
- ZERO ACCESS OR EVALUATION ON VALIDATION OR TEST.
"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

print("="*95)
print("TRAINING-ONLY RESEARCH: OPTIMIZING FOR ~2-WEEK AVERAGE EVALUATION PASS TIME")
print("Data Partition: 14-Year Training Split (2010-2023) ONLY")
print("="*95)

# 1. Load Intraday
src_dplus = (ROOT / "scripts/dplus_4_pilot.py").read_text().split("\nout = {}")[0]
ns_dplus = {"__file__": str(ROOT / "scripts/dplus_4_pilot.py")}
exec(src_dplus, ns_dplus)
base_intraday = ns_dplus["base"]

# 2. Load VIX & Calendar
vix_path = ROOT / "data/external/VIX_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df["date"] = pd.to_datetime(vix_df["DATE"]).dt.date
vix_train = vix_df[(vix_df["date"] >= pd.to_datetime("2010-06-01").date()) & (vix_df["date"] <= pd.to_datetime("2023-12-31").date())]
all_sessions = sorted(vix_train["date"].unique())
vix_dict = dict(zip(vix_df["date"], vix_df["CLOSE"]))

# 3. Load Cached Overnight Trades (Training only)
with open(ROOT / "data/processed/overnight_trades_train.json") as f:
    on_trades = json.load(f)

# Build day-by-day events (Overnight + Crabel Continuation)
daily_events = {}

for tr in on_trades:
    d = pd.to_datetime(tr["exit_day"]).date()
    # Apply strict 20pt bracket stop on overnight
    mae_pts = float(tr["mae_pts"])
    pnl_1c = float(tr["pnl_1c"])
    if mae_pts <= -20.0:
        pnl_1c = -20.0 * 2.0 - 2.60 # stop out at -20 pts
        mae_1c = -20.0 * 2.0
    else:
        mae_1c = mae_pts * 2.0
        
    daily_events.setdefault(d, []).append({
        "type": "overnight",
        "net_1c": pnl_1c,
        "mae_1c": mae_1c,
        "pts": pnl_1c / 2.0
    })

for t in base_intraday:
    d = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
    vix = vix_dict.get(d, 18.0)
    sleeve = t["sleeve"]
    cont = t.get("cont", False)
    if vix >= 15.0 and sleeve.startswith("AG_CRABEL") and cont:
        net_1c = float(t["net"])
        pts = net_1c / 2.0
        # Adaptive Trailing Ratchet (+18pt banker, +25pt lock @ +40, +45pt lock @ +60, +75pt target)
        if pts > 18.0:
            if pts >= 75.0: r = 75.0
            elif pts >= 50.0: r = 35.0
            elif pts >= 30.0: r = 15.0
            else: r = 1.0
            eff = 0.5 * 18.0 + 0.5 * r
            adj_net = eff * 2.0 - 2.60
        else:
            adj_net = net_1c
            
        daily_events.setdefault(d, []).append({
            "type": "crabel",
            "net_1c": adj_net,
            "mae_1c": -34.6, # strict 17.3 pt stop
            "pts": adj_net / 2.0
        })

for d in daily_events:
    daily_events[d].sort(key=lambda x: 0 if x["type"] == "overnight" else 1)

print(f"Loaded {len(all_sessions)} trading sessions across 14 years.")
print(f"Active trade sessions: {len(daily_events)}")

STATIC_FLOOR = -2000.0
DLL_LIMIT = -1000.0
DAILY_LOCK = 1500.0

def simulate_training_eval(
    name,
    enable_overnight=True,
    enable_crabel=True,
    base_sz=6,
    stg2_sz=8,
    stg3_sz=10,
    stg2_thr=1200.0,
    stg3_thr=2400.0,
    def_thr=-200.0,
    def_sz=3,
    min_vix=0.0,
    horizon=90
):
    total = len(all_sessions) - horizon
    passed = 0
    ruined = 0
    timeout = 0
    pass_tr_days = []
    pass_sess = []
    max_dds = []
    
    for i in range(total):
        start_day = all_sessions[i]
        if vix_dict.get(start_day, 18.0) < min_vix:
            continue
            
        cum = 0.0
        hwm = 0.0
        busted = False
        pass_run = False
        peak_dd = 0.0
        tr_days = 0
        
        for step in range(horizon):
            d = all_sessions[i + step]
            tr_list = daily_events.get(d, [])
            if not tr_list:
                continue
                
            active_today = False
            day_pnl = 0.0
            day_mae = 0.0
            
            for tr in tr_list:
                t_type = tr["type"]
                if t_type == "overnight" and not enable_overnight:
                    continue
                if t_type == "crabel" and not enable_crabel:
                    continue
                    
                active_today = True
                
                # Asymmetric Cushion Sizing
                if cum <= def_thr:
                    sz = def_sz # 3 MNQ defensive
                elif cum >= stg3_thr:
                    sz = stg3_sz # Finisher
                elif cum >= stg2_thr:
                    sz = stg2_sz # Cushion
                else:
                    sz = base_sz # Base
                    
                pnl = tr["net_1c"] * sz
                mae = tr["mae_1c"] * sz
                
                if (day_pnl + mae) < day_mae:
                    day_mae = day_pnl + mae
                day_pnl += pnl
                
                # Daily Lock
                if day_pnl >= DAILY_LOCK:
                    day_pnl = DAILY_LOCK
                    break
                    
            if not active_today:
                continue
                
            tr_days += 1
            
            # Check DLL (-$1,000)
            if day_pnl <= DLL_LIMIT or day_mae <= DLL_LIMIT:
                busted = True; break
                
            # Check Static Floor during session
            if (cum + day_mae) <= STATIC_FLOOR:
                busted = True; break
                
            cum += day_pnl
            current_dd = hwm - cum
            if current_dd > peak_dd: peak_dd = current_dd
            if cum > hwm: hwm = cum
            
            if cum <= STATIC_FLOOR:
                busted = True; break
                
            if cum >= 4000.0 and day_pnl <= 2000.0:
                pass_run = True
                passed += 1
                pass_tr_days.append(tr_days)
                pass_sess.append(step + 1)
                max_dds.append(peak_dd)
                break
                
        if busted and not pass_run:
            ruined += 1
        elif not pass_run and not busted:
            timeout += 1
            
    tot = passed + ruined
    p_pct = (passed / max(1, tot)) * 100
    r_pct = (ruined / max(1, tot)) * 100
    
    mean_t = np.mean(pass_tr_days) if passed else 999.0
    med_t = np.median(pass_tr_days) if passed else 999.0
    p25_t = np.percentile(pass_tr_days, 25) if passed else 999.0
    min_t = np.min(pass_tr_days) if passed else 999
    
    mean_s = np.mean(pass_sess) if passed else 999.0
    med_s = np.median(pass_sess) if passed else 999.0
    avg_dd = np.mean(max_dds) if passed else 999.0
    
    return {
        "name": name,
        "passed": passed,
        "ruined": ruined,
        "timeout": timeout,
        "pass_pct": round(p_pct, 1),
        "ruin_pct": round(r_pct, 1),
        "mean_trade_days": round(mean_t, 1),
        "med_trade_days": round(med_t, 1),
        "p25_trade_days": round(p25_t, 1),
        "min_trade_days": int(min_t),
        "mean_sessions": round(mean_s, 1),
        "med_sessions": round(med_s, 1),
        "avg_dd": round(avg_dd, 2)
    }

configs = [
    # 1. Single Sleeve Crabel 6 MNQ Static (Baseline)
    ("1. Crabel Only Static 6 MNQ (Single-Sleeve Baseline)",
     dict(enable_overnight=False, enable_crabel=True, base_sz=6, stg2_sz=6, stg3_sz=6)),
     
    # 2. Multi-Sleeve Double-Dip Static 6 MNQ (Overnight + Crabel)
    ("2. Multi-Sleeve Double-Dip (6 MNQ Static, OVN+Crabel)",
     dict(enable_overnight=True, enable_crabel=True, base_sz=6, stg2_sz=6, stg3_sz=6)),

    # 3. Multi-Sleeve Gentle Finisher (6c -> 8c @ +$2,000)
    ("3. Multi-Sleeve Gentle Finisher (6c -> 8c @ +$2k)",
     dict(enable_overnight=True, enable_crabel=True, base_sz=6, stg2_sz=6, stg3_sz=8, stg3_thr=2000.0)),

    # 4. Multi-Sleeve 3-Tier Staging (6c -> 8c @ +$1.2k -> 10c @ +$2.4k)
    ("4. Multi-Sleeve 3-Tier (6c -> 8c @ $1.2k -> 10c @ $2.4k)",
     dict(enable_overnight=True, enable_crabel=True, base_sz=6, stg2_sz=8, stg3_sz=10, stg2_thr=1200.0, stg3_thr=2400.0)),

    # 5. Multi-Sleeve Active Timing (VIX >= 16, 6c -> 8c @ $1.2k -> 10c @ $2.4k)
    ("5. Multi-Sleeve Active Timing (VIX >= 16, 6c -> 8c -> 10c)",
     dict(enable_overnight=True, enable_crabel=True, base_sz=6, stg2_sz=8, stg3_sz=10, stg2_thr=1200.0, stg3_thr=2400.0, min_vix=16.0)),

    # 6. Multi-Sleeve High-Vol Timing (VIX >= 18, 6c -> 8c -> 10c)
    ("6. Multi-Sleeve High-Vol Timing (VIX >= 18, 6c -> 8c -> 10c)",
     dict(enable_overnight=True, enable_crabel=True, base_sz=6, stg2_sz=8, stg3_sz=10, stg2_thr=1200.0, stg3_thr=2400.0, min_vix=18.0)),

    # 7. Multi-Sleeve High-Vol Sprint (VIX >= 18, 8c Base -> 10c -> 12c)
    ("7. Multi-Sleeve High-Vol Sprint (VIX >= 18, 8c -> 10c -> 12c)",
     dict(enable_overnight=True, enable_crabel=True, base_sz=8, stg2_sz=10, stg3_sz=12, stg2_thr=1000.0, stg3_thr=2200.0, min_vix=18.0)),
]

results = []
for lbl, kw in configs:
    r = simulate_training_eval(lbl, **kw)
    results.append(r)
    print(f"{r['name']:60s} | Pass: {r['pass_pct']:5.1f}% | Ruin: {r['ruin_pct']:5.1f}% | MEAN TR: {r['mean_trade_days']:4.1f}d | MED TR: {r['med_trade_days']:4.1f}d | P25 TR: {r['p25_trade_days']:4.1f}d | Min: {r['min_trade_days']:2d}d | DD: ${r['avg_dd']:6.2f}")

with open(ROOT / "reports/TRAINING_ONLY_2WEEK_RESEARCH_RESULTS.json", "w") as f:
    json.dump(results, f, indent=2)

print("\nSaved to reports/TRAINING_ONLY_2WEEK_RESEARCH_RESULTS.json")

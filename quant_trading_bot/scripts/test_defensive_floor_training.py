"""Test Defensive Floor + Smart Finisher on 14-Year Training Split (2010-2023).
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

# Load VIX
vix_path = ROOT / "data/external/VIX_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df["date"] = pd.to_datetime(vix_df["DATE"]).dt.date
vix_train = vix_df[(vix_df["date"] >= pd.to_datetime("2010-06-01").date()) & (vix_df["date"] <= pd.to_datetime("2023-12-31").date())]
all_sessions = sorted(vix_train["date"].unique())
vix_dict = dict(zip(vix_df["date"], vix_df["CLOSE"]))

# Load Cached Overnight Trades (Training only)
with open(ROOT / "data/processed/overnight_trades_train.json") as f:
    on_trades = json.load(f)

# Load Intraday Base Trades (Training only)
src_dplus = (ROOT / "scripts/dplus_4_pilot.py").read_text().split("\nout = {}")[0]
ns_dplus = {"__file__": str(ROOT / "scripts/dplus_4_pilot.py")}
exec(src_dplus, ns_dplus)
base_intraday = ns_dplus["base"]

FRICTION_PTS = 1.30
PT_VAL = 2.00
STATIC_FLOOR = -2000.0
DLL_LIMIT = -1000.0
DAILY_LOCK = 1500.0

def evaluate_architecture(
    name,
    trade_pool, # dict of date -> trade
    base_sz=6,
    cushion_sz=8,
    finisher_sz=10,
    cushion_thr=1500.0,
    finisher_thr=2700.0,
    def_thr=-250.0,
    def_sz=3,
    min_vix=0.0,
    horizon=120
):
    total = len(all_sessions) - horizon
    passed = 0
    ruined = 0
    timeouts = 0
    pass_tr_days = []
    pass_sess = []
    max_dds = []
    dll_breaches = 0
    
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
            tr = trade_pool.get(d, None)
            if tr is None:
                continue
                
            tr_days += 1
            
            # Dynamic Asymmetric Sizing
            if cum <= def_thr:
                sz = def_sz # Defensive de-escalation
            elif cum >= finisher_thr:
                sz = finisher_sz # Finisher sprint
            elif cum >= cushion_thr:
                sz = cushion_sz # Cushion acceleration
            else:
                sz = base_sz # Standard base
                
            pnl = tr["net_1c"] * sz
            mae = tr["mae_1c"] * sz
            
            # Check Daily Loss Limit (-$1,000)
            if pnl <= DLL_LIMIT or mae <= DLL_LIMIT:
                busted = True
                dll_breaches += 1
                break
                
            # Check Static Floor during trade
            if (cum + mae) <= STATIC_FLOOR:
                busted = True
                break
                
            # Daily consistency lock
            if pnl > DAILY_LOCK:
                pnl = DAILY_LOCK
                
            cum += pnl
            current_dd = hwm - cum
            if current_dd > peak_dd: peak_dd = current_dd
            if cum > hwm: hwm = cum
            
            if cum <= STATIC_FLOOR:
                busted = True
                break
                
            if cum >= 4000.0 and pnl <= 2000.0:
                pass_run = True
                passed += 1
                pass_sess.append(step + 1)
                pass_tr_days.append(tr_days)
                max_dds.append(peak_dd)
                break
                
        if busted and not pass_run:
            ruined += 1
        elif not pass_run and not busted:
            timeouts += 1
            
    tot_evals = passed + ruined
    p_pct = (passed / max(1, tot_evals)) * 100
    r_pct = (ruined / max(1, tot_evals)) * 100
    
    mean_s = np.mean(pass_sess) if passed else 999.0
    med_s = np.median(pass_sess) if passed else 999.0
    p25_s = np.percentile(pass_sess, 25) if passed else 999.0
    min_s = np.min(pass_sess) if passed else 999
    
    mean_t = np.mean(pass_tr_days) if passed else 999.0
    med_t = np.median(pass_tr_days) if passed else 999.0
    p25_t = np.percentile(pass_tr_days, 25) if passed else 999.0
    min_t = np.min(pass_tr_days) if passed else 999
    
    avg_dd = np.mean(max_dds) if passed else 999.0
    
    print(f"{name:58s} | TR MEAN: {mean_t:4.1f}d | MED: {med_t:4.1f}d | P25: {p25_t:4.1f}d | MIN: {min_t:2d}d | Pass: {p_pct:5.1f}% | Ruin: {r_pct:4.1f}% | DLL: {dll_breaches:2d} | DD: ${avg_dd:.2f}")
    return {
        "name": name,
        "passed": passed, "ruined": ruined, "timeouts": timeouts, "dll_breaches": dll_breaches,
        "pass_pct": round(p_pct, 1), "ruin_pct": round(r_pct, 1),
        "mean_sessions": round(mean_s, 1), "med_sessions": round(med_s, 1), "p25_sessions": round(p25_s, 1),
        "mean_trade_days": round(mean_t, 1), "med_trade_days": round(med_t, 1), "p25_trade_days": round(p25_t, 1),
        "min_trade_days": int(min_t), "avg_dd": round(avg_dd, 2)
    }

# Build pools
# Pool 1: Crabel Continuation (Adaptive Ratchet: +20pt scaleout, +25 @ +40, +45 @ +60, +85 target)
pool_crabel = {}
for t in base_intraday:
    d = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
    vix = vix_dict.get(d, 18.0)
    if t["sleeve"].startswith("AG_CRABEL") and t.get("cont", False) and vix >= 15.0:
        net_1c = float(t["net"])
        pts = net_1c / PT_VAL
        if pts > 20.0:
            if pts >= 85.0: r = 85.0
            elif pts >= 60.0: r = 45.0
            elif pts >= 40.0: r = 25.0
            else: r = 1.0
            eff = 0.5 * 20.0 + 0.5 * r
            adj_net = eff * PT_VAL - FRICTION_PTS * PT_VAL
        else:
            adj_net = net_1c
        pool_crabel[d] = {"net_1c": adj_net, "mae_1c": -34.6, "pts": adj_net / PT_VAL}

# Pool 2: Duo-Sleeve (Crabel Continuation priority > Overnight Dip fallback, max 1 trade/day)
pool_duo = {}
for tr in on_trades:
    d = pd.to_datetime(tr["exit_day"]).date()
    mae_pts = float(tr["mae_pts"])
    pnl_1c = float(tr["pnl_1c"])
    if mae_pts <= -20.0:
        pnl_1c = -20.0 * PT_VAL - FRICTION_PTS * PT_VAL
        mae_1c = -20.0 * PT_VAL
    else:
        mae_1c = mae_pts * PT_VAL
    pool_duo[d] = {"net_1c": pnl_1c, "mae_1c": mae_1c, "pts": pnl_1c / PT_VAL}

# Crabel overrides overnight
for d, tr in pool_crabel.items():
    pool_duo[d] = tr

print(f"Crabel Pool: {len(pool_crabel)} trades")
print(f"Duo Pool:    {len(pool_duo)} trades")

print("\n" + "="*115)
print("TESTING DEFENSIVE FLOOR + ASYMMETRIC FINISHER ON TRAINING SPLIT (2010-2023)")
print("="*115)

# Test Crabel Only
evaluate_architecture("Crabel Only: Static 6 MNQ", pool_crabel, base_sz=6, cushion_sz=6, finisher_sz=6)
evaluate_architecture("Crabel Only: Gentle Fortress (6c -> 8c @ $2k, Def 3c @ -$250)", pool_crabel, base_sz=6, cushion_sz=8, finisher_sz=8, cushion_thr=2000.0, finisher_thr=2000.0, def_thr=-250.0, def_sz=3)
evaluate_architecture("Crabel Only: Asym Finisher (6c -> 8c @ $1.5k -> 10c @ $2.8k, Def 3c)", pool_crabel, base_sz=6, cushion_sz=8, finisher_sz=10, cushion_thr=1500.0, finisher_thr=2800.0, def_thr=-250.0, def_sz=3)

# Test Duo Sleeve (Crabel > Overnight)
evaluate_architecture("Duo 1/Day: Static 6 MNQ", pool_duo, base_sz=6, cushion_sz=6, finisher_sz=6)
evaluate_architecture("Duo 1/Day: Gentle (6c -> 8c @ $1.5k, Def 3c @ -$250)", pool_duo, base_sz=6, cushion_sz=8, finisher_sz=8, cushion_thr=1500.0, finisher_thr=1500.0, def_thr=-250.0, def_sz=3)
evaluate_architecture("Duo 1/Day: Asym Finisher (6c -> 8c @ $1.5k -> 10c @ $2.8k, Def 3c)", pool_duo, base_sz=6, cushion_sz=8, finisher_sz=10, cushion_thr=1500.0, finisher_thr=2800.0, def_thr=-250.0, def_sz=3)
evaluate_architecture("Duo 1/Day: Fast Sprint (6c -> 9c @ $1.2k -> 12c @ $2.5k, Def 3c)", pool_duo, base_sz=6, cushion_sz=9, finisher_sz=12, cushion_thr=1200.0, finisher_thr=2500.0, def_thr=-250.0, def_sz=3)
evaluate_architecture("Duo 1/Day: High-Vol Sprint (VIX >= 18, 6c -> 10c -> 12c, Def 3c)", pool_duo, base_sz=6, cushion_sz=10, finisher_sz=12, cushion_thr=1200.0, finisher_thr=2400.0, def_thr=-250.0, def_sz=3, min_vix=18.0)

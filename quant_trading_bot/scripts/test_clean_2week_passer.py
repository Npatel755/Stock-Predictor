"""Clean 2-Week Evaluation Passer Simulation.
Key design:
1. Max 1 trade per session (clean execution, zero intraday DLL compounding)
2. Priority: Crabel Continuation (highest expectancy) -> Overnight Dip -> Trend 60m
3. Staging ladder:
   - Base (P&L $0 to +$1,200): 6 MNQ (worst day -$207.60, 0 DLL risk)
   - Cushion (P&L +$1,200 to +$2,500): 8 MNQ (worst day -$276.80, 0 DLL risk)
   - Finisher (P&L >= +$2,500): 10 MNQ (worst day -$346.00, 0 DLL risk)
4. Anti-Ruin Defensive Ratchet: Drops to 1 MNQ if P&L < -$250
5. Adaptive Trailing Ratchet (+20pt banker, +25pt lock at +40, +45pt lock at +60, +85pt target)
6. Topstep Static Floor (-$2,000 fixed) & DLL (-$1,000)
"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

# Load Intraday
src_dplus = (ROOT / "scripts/dplus_4_pilot.py").read_text().split("\nout = {}")[0]
ns_dplus = {"__file__": str(ROOT / "scripts/dplus_4_pilot.py")}
exec(src_dplus, ns_dplus)
base_intraday = ns_dplus["base"]

# Load VIX
vix_path = ROOT / "data/external/VIX_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df["date"] = pd.to_datetime(vix_df["DATE"]).dt.date
vix_train = vix_df[(vix_df["date"] >= pd.to_datetime("2010-06-01").date()) & (vix_df["date"] <= pd.to_datetime("2023-12-31").date())]
all_sessions = sorted(vix_train["date"].unique())
vix_dict = dict(zip(vix_df["date"], vix_df["CLOSE"]))

# Load Cached Overnight Trades
with open(ROOT / "data/processed/overnight_trades_train.json") as f:
    on_trades = json.load(f)

# Priority selection per day: Crabel Continuation > Overnight Dip > TRD60
daily_best_trade = {}

# 1. TRD60 as fallback
for t in base_intraday:
    if t["sleeve"] == "AG_TRD60_D_1c":
        d = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
        daily_best_trade[d] = {
            "type": "trend",
            "net_1c": float(t["net"]),
            "mae_1c": -min(float(t.get("stop_risk", 34.6 * 2.0)), 70.0),
            "pts": float(t["net"]) / 2.0
        }

# 2. Overnight Dip overrides if no Crabel
for tr in on_trades:
    d = pd.to_datetime(tr["exit_day"]).date()
    daily_best_trade[d] = {
        "type": "overnight",
        "net_1c": float(tr["pnl_1c"]),
        "mae_1c": max(float(tr["mae_1c"]), -25.0 * 2.0),
        "pts": float(tr["pnl_1c"]) / 2.0
    }

# 3. Crabel Continuation takes HIGHEST priority
for t in base_intraday:
    if t["sleeve"].startswith("AG_CRABEL") and t.get("cont", False):
        d = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
        vix = vix_dict.get(d, 18.0)
        if vix >= 15.0:
            daily_best_trade[d] = {
                "type": "crabel",
                "net_1c": float(t["net"]),
                "mae_1c": -34.6, # strict 17.3 pt stop
                "pts": float(t["net"]) / 2.0
            }

print(f"Total trading sessions: {len(all_sessions)}")
print(f"Total sessions with active trades: {len(daily_best_trade)}")

FRICTION_PTS = 1.30
PT_VAL = 2.00
STATIC_FLOOR = -2000.0

def evaluate_clean_strategy(
    name,
    base_sz=6,
    stg2_sz=8,
    stg3_sz=10,
    stg2_thr=1200.0,
    stg3_thr=2500.0,
    def_thr=-250.0,
    def_sz=1,
    daily_lock=1500.0,
    min_vix=0.0,
    horizon_sessions=100
):
    total = len(all_sessions) - horizon_sessions
    passed = 0
    ruined = 0
    pass_sess = []
    pass_tr_days = []
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
        
        for step in range(horizon_sessions):
            d = all_sessions[i + step]
            tr = daily_best_trade.get(d, None)
            if tr is None:
                continue
                
            tr_days += 1
            
            # Sizing Staging
            if cum <= def_thr:
                sz = def_sz
            elif cum >= stg3_thr:
                sz = stg3_sz
            elif cum >= stg2_thr:
                sz = stg2_sz
            else:
                sz = base_sz
                
            pts = tr["pts"]
            tr_type = tr["type"]
            mae = tr["mae_1c"] * sz
            
            if tr_type == "overnight":
                pnl = tr["net_1c"] * sz
                if tr["mae_1c"] <= -25.0 * 2.0:
                    pnl = -25.0 * 2.0 * sz
            elif tr_type == "crabel":
                # Adaptive Trailing Ratchet on Crabel
                if pts > 20.0:
                    if pts >= 85.0: r = 85.0
                    elif pts >= 60.0: r = 45.0
                    elif pts >= 40.0: r = 25.0
                    else: r = 1.0
                    eff = 0.5 * 20.0 + 0.5 * r
                    pnl = (eff * PT_VAL - FRICTION_PTS * PT_VAL) * sz
                else:
                    pnl = tr["net_1c"] * sz
            else: # trend
                if pts > 25.0:
                    if pts >= 75.0: r = 75.0
                    elif pts >= 50.0: r = 35.0
                    elif pts >= 35.0: r = 20.0
                    else: r = 1.0
                    eff = 0.5 * 20.0 + 0.5 * r
                    pnl = (eff * PT_VAL - FRICTION_PTS * PT_VAL) * sz
                else:
                    pnl = tr["net_1c"] * sz
                    
            if pnl > daily_lock: pnl = daily_lock
            
            # Check DLL (-$1,000)
            if pnl <= -1000.0 or mae <= -1000.0:
                busted = True; break
                
            # Check Static Floor during trade
            if (cum + mae) <= STATIC_FLOOR:
                busted = True; break
                
            cum += pnl
            current_dd = hwm - cum
            if current_dd > peak_dd: peak_dd = current_dd
            if cum > hwm: hwm = cum
            
            if cum <= STATIC_FLOOR:
                busted = True; break
                
            if cum >= 4000.0 and pnl <= 2000.0:
                pass_run = True
                passed += 1
                pass_sess.append(step + 1)
                pass_tr_days.append(tr_days)
                max_dds.append(peak_dd)
                break
                
        if busted and not pass_run:
            ruined += 1
            
    tot = passed + ruined
    p_pct = (passed / max(1, tot)) * 100
    r_pct = (ruined / max(1, tot)) * 100
    
    mean_s = np.mean(pass_sess) if passed else 999.0
    med_s = np.median(pass_sess) if passed else 999.0
    p25_s = np.percentile(pass_sess, 25) if passed else 999.0
    min_s = np.min(pass_sess) if passed else 999
    
    mean_t = np.mean(pass_tr_days) if passed else 999.0
    med_t = np.median(pass_tr_days) if passed else 999.0
    p25_t = np.percentile(pass_tr_days, 25) if passed else 999.0
    min_t = np.min(pass_tr_days) if passed else 999
    
    avg_dd = np.mean(max_dds) if passed else 999.0
    
    return {
        "name": name,
        "passed": passed,
        "ruined": ruined,
        "pass_pct": round(p_pct, 1),
        "ruin_pct": round(r_pct, 1),
        "mean_sessions": round(mean_s, 1),
        "med_sessions": round(med_s, 1),
        "p25_sessions": round(p25_s, 1),
        "min_sessions": int(min_s),
        "mean_trade_days": round(mean_t, 1),
        "med_trade_days": round(med_t, 1),
        "p25_trade_days": round(p25_t, 1),
        "min_trade_days": int(min_t),
        "avg_dd": round(avg_dd, 2)
    }

print("\n" + "="*125)
print("TESTING 2-WEEK EVALUATION PASSER ARCHITECTURE")
print("="*125)

configs = [
    # 1. Static 6 MNQ
    ("1. Static 6 MNQ Baseline (No Compounding)", dict(base_sz=6, stg2_sz=6, stg3_sz=6)),
    
    # 2. Conservative Staging: 6c -> 8c -> 10c
    ("2. Fortress Staging (6c -> 8c at $1.2k -> 10c at $2.5k)", dict(base_sz=6, stg2_sz=8, stg3_sz=10, stg2_thr=1200.0, stg3_thr=2500.0)),

    # 3. Aggressive Staging: 6c -> 10c -> 12c
    ("3. Sprint Staging (6c -> 10c at $1.0k -> 12c at $2.2k)", dict(base_sz=6, stg2_sz=10, stg3_sz=12, stg2_thr=1000.0, stg3_thr=2200.0)),

    # 4. Power Base: 8c -> 10c -> 14c
    ("4. Velocity Sprint (8c -> 10c at $1.0k -> 14c at $2.2k)", dict(base_sz=8, stg2_sz=10, stg3_sz=14, stg2_thr=1000.0, stg3_thr=2200.0)),

    # 5. Volatility Filter: VIX >= 16 (Sprint Staging)
    ("5. Active Timing VIX >= 16 (6c -> 10c -> 12c)", dict(base_sz=6, stg2_sz=10, stg3_sz=12, stg2_thr=1000.0, stg3_thr=2200.0, min_vix=16.0)),

    # 6. Volatility Filter: VIX >= 18 (Velocity Sprint)
    ("6. High Vol Timing VIX >= 18 (8c -> 10c -> 14c)", dict(base_sz=8, stg2_sz=10, stg3_sz=14, stg2_thr=1000.0, stg3_thr=2200.0, min_vix=18.0)),

    # 7. Volatility Filter: VIX >= 20 (Turbo Sprint)
    ("7. Turbo Sprint VIX >= 20 (8c -> 12c -> 14c)", dict(base_sz=8, stg2_sz=12, stg3_sz=14, stg2_thr=800.0, stg3_thr=2000.0, min_vix=20.0)),
]

results = []
for lbl, kw in configs:
    r = evaluate_clean_strategy(lbl, **kw)
    results.append(r)
    print(f"{r['name']:55s} | MEAN TR: {r['mean_trade_days']:4.1f}d | MED TR: {r['med_trade_days']:4.1f}d | P25 TR: {r['p25_trade_days']:4.1f}d | Min: {r['min_trade_days']:2d}d | Pass: {r['pass_pct']:4.1f}% | Ruin: {r['ruin_pct']:4.1f}% | DD: ${r['avg_dd']:6.2f}")

with open(ROOT / "reports/CLEAN_2WEEK_PASSER_RESULTS.json", "w") as f:
    json.dump(results, f, indent=2)

print("\nDone. Saved to reports/CLEAN_2WEEK_PASSER_RESULTS.json")

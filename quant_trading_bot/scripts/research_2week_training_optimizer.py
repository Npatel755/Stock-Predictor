"""Comprehensive 2-Week Average Passer Optimization STRICTLY on 14-Year Training Split (2010-2023).
METHODOLOGICAL INVARIANT:
- 100% EXCLUSIVELY ON TRAINING DATA (2010-06-01 to 2023-12-31).
- ZERO ACCESS, ZERO LOOKUPS, ZERO TUNING ON VALIDATION (2024-2025) OR BLIND TEST (2026).
"""
import sys, json, os
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

print("="*95)
print("TRAINING-ONLY RESEARCH: OPTIMIZING 2-WEEK AVERAGE EVALUATION PASSER")
print("Data Partition: 14-Year Training Split (2010-06-01 to 2023-12-31) ONLY")
print("Target: Mean Pass Time ~10-14 Trade Days (~2 Weeks), Pass Rate >= 85%, Ruin <= 5%")
print("="*95)

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

# Prepare daily events dictionary for training
# We can evaluate:
# 1. Crabel Continuation only
# 2. Multi-Sleeve: Overnight Reopen Dip + Crabel Continuation
# 3. Multi-Sleeve: Overnight + Crabel Continuation + TRD60
print(f"Loaded {len(all_sessions)} total sessions in Training Split.")
print(f"Loaded {len(on_trades)} overnight trades.")
print(f"Loaded {len(base_intraday)} intraday base trades.")

# Build detailed session trade map
def build_trade_map(runner_t2=85.0, lock1=25.0, lock2=45.0, on_stop=20.0, trd60_stop=25.0):
    events = {}
    
    # 1. Overnight Reopen Dip
    for tr in on_trades:
        d = pd.to_datetime(tr["exit_day"]).date()
        mae_pts = float(tr["mae_pts"])
        pnl_1c = float(tr["pnl_1c"])
        if mae_pts <= -on_stop:
            pnl_1c = -on_stop * PT_VAL - FRICTION_PTS * PT_VAL
            mae_1c = -on_stop * PT_VAL
        else:
            mae_1c = mae_pts * PT_VAL
        events.setdefault(d, []).append({
            "sleeve": "overnight",
            "net_1c": pnl_1c,
            "mae_1c": mae_1c,
            "pts": pnl_1c / PT_VAL
        })
        
    # 2. Intraday Trades
    for t in base_intraday:
        d = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
        sleeve = t["sleeve"]
        vix = vix_dict.get(d, 18.0)
        
        if sleeve.startswith("AG_CRABEL") and t.get("cont", False) and vix >= 15.0:
            net_1c = float(t["net"])
            pts = net_1c / PT_VAL
            # Adaptive Trailing Ratchet
            if pts > 20.0:
                if pts >= runner_t2: r = runner_t2
                elif pts >= 60.0: r = lock2
                elif pts >= 40.0: r = lock1
                else: r = 1.0
                eff = 0.5 * 20.0 + 0.5 * r
                adj_net = eff * PT_VAL - FRICTION_PTS * PT_VAL
            else:
                adj_net = net_1c
                
            events.setdefault(d, []).append({
                "sleeve": "crabel",
                "net_1c": adj_net,
                "mae_1c": -34.6, # strict 17.3 pt stop
                "pts": adj_net / PT_VAL
            })
            
        elif sleeve == "AG_TRD60_D_1c" and vix >= 16.0:
            net_1c = float(t["net"])
            pts = net_1c / PT_VAL
            # Apply strict stop on TRD60 to prevent large drawdowns
            mae = -min(float(t.get("stop_risk", 34.6 * 2.0)), trd60_stop * PT_VAL)
            if pts < -trd60_stop:
                adj_net = -trd60_stop * PT_VAL - FRICTION_PTS * PT_VAL
            elif pts > 25.0:
                if pts >= 75.0: r = 75.0
                elif pts >= 50.0: r = 35.0
                else: r = 1.0
                eff = 0.5 * 20.0 + 0.5 * r
                adj_net = eff * PT_VAL - FRICTION_PTS * PT_VAL
            else:
                adj_net = net_1c
                
            events.setdefault(d, []).append({
                "sleeve": "trend",
                "net_1c": adj_net,
                "mae_1c": mae,
                "pts": adj_net / PT_VAL
            })
            
    # Sort events by execution time: overnight (morning exit) -> crabel (10-12 ET) -> trend (afternoon)
    prio_order = {"overnight": 0, "crabel": 1, "trend": 2}
    for d in events:
        events[d].sort(key=lambda x: prio_order[x["sleeve"]])
        
    return events

print("Ready to run training simulations.")

def simulate_training_eval(
    events,
    name,
    enable_sleeves=["crabel"], # list of allowed sleeves
    max_trades_per_day=1,       # 1 or 2
    skip_intraday_if_on_loss=True,
    base_sz=6,
    stg2_sz=8,
    stg3_sz=10,
    stg2_thr=1200.0,
    stg3_thr=2500.0,
    def_thr=-250.0,
    def_sz=3,
    min_vix=0.0,
    horizon_sessions=100
):
    total = len(all_sessions) - horizon_sessions
    passed = 0
    ruined = 0
    timeouts = 0
    pass_sess = []
    pass_tr_days = []
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
        
        for step in range(horizon_sessions):
            d = all_sessions[i + step]
            tr_list = events.get(d, [])
            if not tr_list:
                continue
                
            active_today = False
            day_pnl = 0.0
            day_mae = 0.0
            trades_taken_today = 0
            on_lost_today = False
            
            for tr in tr_list:
                slv = tr["sleeve"]
                if slv not in enable_sleeves:
                    continue
                if trades_taken_today >= max_trades_per_day:
                    break
                if skip_intraday_if_on_loss and on_lost_today and slv != "overnight":
                    break
                    
                active_today = True
                trades_taken_today += 1
                
                # Dynamic Cushion Sizing
                if cum <= def_thr:
                    sz = def_sz
                elif cum >= stg3_thr:
                    sz = stg3_sz
                elif cum >= stg2_thr:
                    sz = stg2_sz
                else:
                    sz = base_sz
                    
                pnl = tr["net_1c"] * sz
                mae = tr["mae_1c"] * sz
                
                if (day_pnl + mae) < day_mae:
                    day_mae = day_pnl + mae
                day_pnl += pnl
                
                if slv == "overnight" and pnl < 0:
                    on_lost_today = True
                    
                # Daily consistency lock
                if day_pnl >= DAILY_LOCK:
                    day_pnl = DAILY_LOCK
                    break
                    
            if not active_today:
                continue
                
            tr_days += 1
            
            # Check Daily Loss Limit (-$1,000)
            if day_pnl <= DLL_LIMIT or day_mae <= DLL_LIMIT:
                busted = True
                dll_breaches += 1
                break
                
            # Check Static Floor during session
            if (cum + day_mae) <= STATIC_FLOOR:
                busted = True
                break
                
            cum += day_pnl
            current_dd = hwm - cum
            if current_dd > peak_dd: peak_dd = current_dd
            if cum > hwm: hwm = cum
            
            if cum <= STATIC_FLOOR:
                busted = True
                break
                
            if cum >= 4000.0 and day_pnl <= 2000.0:
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
    
    res = {
        "name": name,
        "passed": passed,
        "ruined": ruined,
        "timeouts": timeouts,
        "dll_breaches": dll_breaches,
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
    
    print(f"{name:55s} | TR MEAN: {mean_t:4.1f}d | MED: {med_t:4.1f}d | P25: {p25_t:4.1f}d | MIN: {min_t:2d}d | Pass: {p_pct:5.1f}% | Ruin: {r_pct:4.1f}% | DLL: {dll_breaches:2d} | DD: ${avg_dd:.2f}")
    return res

# Run exploration across candidate configurations on Training Data
trade_map = build_trade_map(runner_t2=85.0, lock1=25.0, lock2=45.0, on_stop=20.0, trd60_stop=25.0)

print("\n" + "="*115)
print("EVALUATING CANDIDATES ON 14-YEAR TRAINING DATA (2010-2023)")
print("="*115)

candidates = []

# Baseline: Crabel Only
candidates.append(simulate_training_eval(
    trade_map,
    name="1. Baseline: Crabel Only (Static 6 MNQ)",
    enable_sleeves=["crabel"],
    max_trades_per_day=1,
    base_sz=6, stg2_sz=6, stg3_sz=6
))

candidates.append(simulate_training_eval(
    trade_map,
    name="2. Baseline: Crabel Only Gentle Fortress (6c -> 8c @ $2k)",
    enable_sleeves=["crabel"],
    max_trades_per_day=1,
    base_sz=6, stg2_sz=8, stg3_sz=8, stg2_thr=2000.0, stg3_thr=2000.0, def_thr=-300.0, def_sz=4
))

# Duo-Sleeve: Overnight + Crabel (Max 1 trade/day: Crabel priority, Overnight fallback)
candidates.append(simulate_training_eval(
    trade_map,
    name="3. Duo-Sleeve 1/Day: Crabel > OVN (Static 6 MNQ)",
    enable_sleeves=["overnight", "crabel"],
    max_trades_per_day=1,
    base_sz=6, stg2_sz=6, stg3_sz=6
))

candidates.append(simulate_training_eval(
    trade_map,
    name="4. Duo-Sleeve 1/Day: Crabel > OVN Gentle (6c -> 8c @ $1.5k)",
    enable_sleeves=["overnight", "crabel"],
    max_trades_per_day=1,
    base_sz=6, stg2_sz=8, stg3_sz=8, stg2_thr=1500.0, stg3_thr=1500.0, def_thr=-250.0, def_sz=3
))

candidates.append(simulate_training_eval(
    trade_map,
    name="5. Duo-Sleeve 1/Day: Crabel > OVN Finisher (6c -> 8c @ $1.2k -> 10c @ $2.5k)",
    enable_sleeves=["overnight", "crabel"],
    max_trades_per_day=1,
    base_sz=6, stg2_sz=8, stg3_sz=10, stg2_thr=1200.0, stg3_thr=2500.0, def_thr=-250.0, def_sz=3
))

# Duo-Sleeve: Overnight + Crabel (Max 2 trades/day: Double-Dip when both present)
candidates.append(simulate_training_eval(
    trade_map,
    name="6. Duo-Sleeve Double-Dip (Static 6 MNQ, 2/day)",
    enable_sleeves=["overnight", "crabel"],
    max_trades_per_day=2,
    skip_intraday_if_on_loss=True,
    base_sz=6, stg2_sz=6, stg3_sz=6
))

candidates.append(simulate_training_eval(
    trade_map,
    name="7. Duo-Sleeve Double-Dip Gentle (6c -> 8c @ $1.5k, 2/day)",
    enable_sleeves=["overnight", "crabel"],
    max_trades_per_day=2,
    skip_intraday_if_on_loss=True,
    base_sz=6, stg2_sz=8, stg3_sz=8, stg2_thr=1500.0, stg3_thr=1500.0, def_thr=-250.0, def_sz=3
))

candidates.append(simulate_training_eval(
    trade_map,
    name="8. Duo-Sleeve Double-Dip Finisher (6c -> 8c @ $1.2k -> 10c @ $2.4k)",
    enable_sleeves=["overnight", "crabel"],
    max_trades_per_day=2,
    skip_intraday_if_on_loss=True,
    base_sz=6, stg2_sz=8, stg3_sz=10, stg2_thr=1200.0, stg3_thr=2400.0, def_thr=-250.0, def_sz=3
))

# Trio-Sleeve: Overnight + Crabel + TRD60
candidates.append(simulate_training_eval(
    trade_map,
    name="9. Trio-Sleeve 1/Day (OVN+Crabel+TRD60, Static 6 MNQ)",
    enable_sleeves=["overnight", "crabel", "trend"],
    max_trades_per_day=1,
    base_sz=6, stg2_sz=6, stg3_sz=6
))

candidates.append(simulate_training_eval(
    trade_map,
    name="10. Trio-Sleeve 1/Day Gentle (6c -> 8c @ $1.5k)",
    enable_sleeves=["overnight", "crabel", "trend"],
    max_trades_per_day=1,
    base_sz=6, stg2_sz=8, stg3_sz=8, stg2_thr=1500.0, stg3_thr=1500.0, def_thr=-250.0, def_sz=3
))

candidates.append(simulate_training_eval(
    trade_map,
    name="11. Trio-Sleeve 1/Day Finisher (6c -> 8c @ $1.2k -> 10c @ $2.4k)",
    enable_sleeves=["overnight", "crabel", "trend"],
    max_trades_per_day=1,
    base_sz=6, stg2_sz=8, stg3_sz=10, stg2_thr=1200.0, stg3_thr=2400.0, def_thr=-250.0, def_sz=3
))

candidates.append(simulate_training_eval(
    trade_map,
    name="12. Trio-Sleeve 1/Day Sprint (6c -> 9c @ $1.2k -> 12c @ $2.4k)",
    enable_sleeves=["overnight", "crabel", "trend"],
    max_trades_per_day=1,
    base_sz=6, stg2_sz=9, stg3_sz=12, stg2_thr=1200.0, stg3_thr=2400.0, def_thr=-250.0, def_sz=3
))

# High Volatility Gated Trio-Sleeve (VIX >= 16)
candidates.append(simulate_training_eval(
    trade_map,
    name="13. Trio-Sleeve Active Timing (VIX >= 16, 6c -> 8c -> 10c)",
    enable_sleeves=["overnight", "crabel", "trend"],
    max_trades_per_day=1,
    base_sz=6, stg2_sz=8, stg3_sz=10, stg2_thr=1200.0, stg3_thr=2400.0, def_thr=-250.0, def_sz=3,
    min_vix=16.0
))

candidates.append(simulate_training_eval(
    trade_map,
    name="14. Trio-Sleeve High-Vol Timing (VIX >= 18, 6c -> 8c -> 10c)",
    enable_sleeves=["overnight", "crabel", "trend"],
    max_trades_per_day=1,
    base_sz=6, stg2_sz=8, stg3_sz=10, stg2_thr=1200.0, stg3_thr=2400.0, def_thr=-250.0, def_sz=3,
    min_vix=18.0
))

# Save results
out_path = ROOT / "reports/TRAINING_ONLY_OPTIMIZATION_GRID.json"
with open(out_path, "w") as f:
    json.dump(candidates, f, indent=2)
print(f"\nAll results saved to {out_path}")

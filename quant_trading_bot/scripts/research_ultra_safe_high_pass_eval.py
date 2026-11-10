"""Ultra-Safe High-Pass Evaluation Strategy Research & Optimization.
Strictly on 14-Year Training Split (2010-2023). Zero exposure to Validation or Blind Test.

Rules:
- Evaluation Target: +$4,000 ($54,000)
- Topstep Static Drawdown Floor: -$2,000 ($48,000 - fixed, never trails)
- Daily Loss Limit: -$1,000
- 50% Consistency Rule: Max single day profit <= $2,000 (Daily lock enforced at +$1,500 to +$1,750)
- Full CME Micro Friction: $0.61 commission/side, 1.75 tick spread, 1.0 tick slippage (1.30 pts roundtrip)

Improvements Tested:
1. Defensive Drawdown Ratchet (Anti-Ruin Armor: cut contracts when in drawdown)
2. Asymmetric Cushion Staging (Defensive 2-3c -> Base 5-6c -> Accel 8-10c -> Sprint 12c)
3. Free-Roll Scale-Out (50% Banker at +20/25pt + 50% Runner with stop to BE)
4. Intraday Green-to-Red Protection (Lock in green days)
5. Multi-Session Coverage (Overnight Dip + Morning Crabel + Midday/Afternoon Trend)
6. Stepped through all 3,432 real NYSE/CME trading sessions (2010-2023).
"""
import sys, json, os
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

# 1. Load Intraday Trades
src_dplus = (ROOT / "scripts/dplus_4_pilot.py").read_text().split("\nout = {}")[0]
ns_dplus = {"__file__": str(ROOT / "scripts/dplus_4_pilot.py")}
exec(src_dplus, ns_dplus)
base_intraday = ns_dplus["base"]

# 2. Load VIX & Full Calendar of All 3,432 Trading Days
vix_path = ROOT / "data/external/VIX_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df["date"] = pd.to_datetime(vix_df["DATE"]).dt.date
vix_train = vix_df[(vix_df["date"] >= pd.to_datetime("2010-06-01").date()) & (vix_df["date"] <= pd.to_datetime("2023-12-31").date())]
all_calendar_days = sorted(vix_train["date"].unique())
vix_dict = dict(zip(vix_df["date"], vix_df["CLOSE"]))
print(f"Loaded {len(all_calendar_days)} real trading days from 2010 to 2023.")

# 3. Load Cached Overnight Trades
with open(ROOT / "data/processed/overnight_trades_train.json") as f:
    on_trades_data = json.load(f)

# 4. Map trades chronologically by day
trades_by_day = {}

# Overnight Trades (Order 0: executed 18:05 to 09:45)
for tr in on_trades_data:
    ex_day = pd.to_datetime(tr["exit_day"]).date()
    trades_by_day.setdefault(ex_day, []).append({
        "order": 0,
        "type": "overnight",
        "net_1c": float(tr["pnl_1c"]),
        "mae_1c": float(tr["mae_1c"]),
        "pts": float(tr["pnl_1c"]) / 2.0,
        "sleeve": "OVERNIGHT"
    })

# Intraday Trades
for t in base_intraday:
    t_day = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
    cont = t.get("cont", False)
    sleeve = t["sleeve"]
    is_crabel = sleeve.startswith("AG_CRABEL")
    if is_crabel and not cont: 
        continue # filter non-continuation
        
    net_1c = float(t["net"])
    pts_1c = net_1c / 2.0
    stop_r = float(t.get("stop_risk", 34.6 * 2.0))
    mae_1c = -min(stop_r, 70.0)
    
    order = 1 if is_crabel else 2
    trades_by_day.setdefault(t_day, []).append({
        "order": order,
        "type": "intraday",
        "net_1c": net_1c,
        "mae_1c": mae_1c,
        "pts": pts_1c,
        "sleeve": sleeve,
        "is_crabel": is_crabel
    })

for d in trades_by_day:
    trades_by_day[d].sort(key=lambda x: x["order"])

print(f"Days with active trade signals: {len(trades_by_day)}")

def simulate_evaluation(
    name,
    base_size=5,
    defensive_size=2,
    defensive_threshold=-400.0,
    stage2_size=8,
    stage2_threshold=1000.0,
    stage3_size=12,
    stage3_threshold=2200.0,
    use_cushion_staging=True,
    use_defensive_ratchet=True,
    daily_lock=1500.0,
    daily_stop=350.0,
    on_hard_stop_pts=25.0,
    banker_pts=20.0,
    runner_pts=80.0,
    use_scaleout=True,
    is_static_floor=True, # Topstep static floor: fixed at -$2,000, never trails
    max_eval_calendar_days=90 # 90 trading days (~4.5 months)
):
    total_trials = len(all_calendar_days) - max_eval_calendar_days
    passed = 0
    ruined = 0
    timeout = 0
    pass_days = []
    max_dds_on_pass = []
    
    for i in range(total_trials):
        cum = 0.0
        hwm = 0.0
        floor = -2000.0
        busted = False
        pass_run = False
        max_d_pnl = -9999.0
        peak_dd = 0.0
        
        for step in range(max_eval_calendar_days):
            d = all_calendar_days[i + step]
            trades = trades_by_day.get(d, [])
            
            if not trades:
                # Flat day (no signals)
                continue
                
            # Determine current sizing
            if use_defensive_ratchet and cum <= defensive_threshold:
                current_size = defensive_size
                on_size = 1
            elif use_cushion_staging and cum >= stage3_threshold:
                current_size = stage3_size
                on_size = 2
            elif use_cushion_staging and cum >= stage2_threshold:
                current_size = stage2_size
                on_size = 2
            else:
                current_size = base_size
                on_size = 1
                
            day_pnl = 0.0
            day_mae = 0.0
            day_hwm = 0.0
            
            for tr in trades:
                if tr["type"] == "overnight":
                    sz = on_size
                    mae = max(tr["mae_1c"], -on_hard_stop_pts * 2.0) * sz
                    pnl = tr["net_1c"] * sz
                    if tr["mae_1c"] < -on_hard_stop_pts * 2.0:
                        pnl = -on_hard_stop_pts * 2.0 * sz
                elif tr["is_crabel"]:
                    sz = current_size
                    mae = tr["mae_1c"] * sz
                    pts = tr["pts"]
                    if use_scaleout and pts > 20.0:
                        run = min(pts, runner_pts)
                        eff_pts = 0.5 * banker_pts + 0.5 * run
                        pnl = (eff_pts * 2.0 - 1.30 * 2.0) * sz
                    else:
                        pnl = tr["net_1c"] * sz
                else: # trend sleeve
                    sz = max(2, current_size // 2) if not use_cushion_staging else current_size
                    mae = tr["mae_1c"] * sz
                    pts = tr["pts"]
                    if use_scaleout and pts > 25.0:
                        run = min(pts, runner_pts)
                        eff_pts = 0.5 * banker_pts + 0.5 * run
                        pnl = (eff_pts * 2.0 - 1.30 * 2.0) * sz
                    else:
                        pnl = tr["net_1c"] * sz
                        
                # Update day excursions
                if (day_pnl + mae) < day_mae:
                    day_mae = day_pnl + mae
                day_pnl += pnl
                if day_pnl > day_hwm:
                    day_hwm = day_pnl
                    
                # Intraday Green-to-Red Protection: If day made +$400, protect gains (stop at +$100)
                if day_hwm >= 400.0 and day_pnl <= 100.0:
                    break
                    
                # Daily circuit breakers
                if day_pnl >= daily_lock or day_pnl <= -daily_stop:
                    break
                    
            # Check Daily Loss Limit (-$1,000)
            if day_pnl <= -1000.0 or day_mae <= -1000.0:
                busted = True; break
                
            # Check Drawdown Floor
            if (cum + day_mae) <= floor:
                busted = True; break
                
            cum += day_pnl
            current_dd = hwm - cum
            if current_dd > peak_dd: peak_dd = current_dd
            
            if cum > hwm:
                hwm = cum
                if not is_static_floor:
                    # Trailing floor: trails HWM, locks at 0 once HWM >= 2000
                    floor = 0.0 if hwm >= 2000.0 else -2000.0 + hwm
                    
            if cum <= floor:
                busted = True; break
                
            if day_pnl > max_d_pnl: max_d_pnl = day_pnl
            
            # Pass check + 50% consistency rule
            if cum >= 4000.0 and max_d_pnl <= 2000.0:
                pass_run = True
                passed += 1
                pass_days.append(step + 1)
                max_dds_on_pass.append(peak_dd)
                break
                
        if busted and not pass_run:
            ruined += 1
        elif not pass_run and not busted:
            timeout += 1
            
    p_arr = np.array(pass_days) if pass_days else np.array([0])
    dd_arr = np.array(max_dds_on_pass) if max_dds_on_pass else np.array([0])
    
    pass_pct = passed / total_trials * 100
    ruin_pct = ruined / total_trials * 100
    resolved_pass_pct = passed / max(1, passed + ruined) * 100
    med_days = float(np.median(p_arr)) if passed > 0 else 999.0
    p25_days = float(np.percentile(p_arr, 25)) if passed > 0 else 999.0
    p10_days = float(np.percentile(p_arr, 10)) if passed > 0 else 999.0
    min_days = int(p_arr.min()) if passed > 0 else 999
    avg_dd = float(dd_arr.mean()) if passed > 0 else 999.0
    
    return {
        "name": name,
        "total_trials": total_trials,
        "passed": passed,
        "ruined": ruined,
        "timeout": timeout,
        "pass_pct": round(pass_pct, 1),
        "ruin_pct": round(ruin_pct, 1),
        "resolved_pass_pct": round(resolved_pass_pct, 1),
        "med_days": round(med_days, 1),
        "med_weeks": round(med_days / 5.0, 1),
        "p25_days": round(p25_days, 1),
        "p10_days": round(p10_days, 1),
        "min_days": min_days,
        "avg_dd": round(avg_dd, 2)
    }

print("\n" + "="*95)
print("EXPERIMENT: REDUCING RUIN TO NEAR-ZERO & MAXIMIZING PASS PROBABILITY")
print("="*95)

grid = [
    # 1. Unmanaged Fixed 6 MNQ Baseline (Static Floor)
    ("1. Fixed 6 MNQ Baseline (No Ratchet, Static Floor)", 
     dict(base_size=6, use_cushion_staging=False, use_defensive_ratchet=False, is_static_floor=True)),

    # 2. Fixed 6 MNQ with Defensive Ratchet (Cut to 2 MNQ when <= -$400)
    ("2. Fixed 6 MNQ + Defensive Ratchet (2 MNQ when <= -$400)", 
     dict(base_size=6, defensive_size=2, defensive_threshold=-400.0, use_cushion_staging=False, use_defensive_ratchet=True, is_static_floor=True)),

    # 3. Fixed 5 MNQ Conservative Tier + Defensive Ratchet
    ("3. Conservative 5 MNQ + Defensive Ratchet (2 MNQ)", 
     dict(base_size=5, defensive_size=2, defensive_threshold=-350.0, use_cushion_staging=False, use_defensive_ratchet=True, is_static_floor=True)),

    # 4. Asymmetric Cushion Staging: 5 MNQ (Base) -> 8 MNQ (+$1k) -> 12 MNQ (+$2.2k)
    ("4. Asymmetric Cushion (5 -> 8 -> 12 MNQ, No Defensive Ratchet)", 
     dict(base_size=5, stage2_size=8, stage2_threshold=1000.0, stage3_size=12, stage3_threshold=2200.0, use_cushion_staging=True, use_defensive_ratchet=False, is_static_floor=True)),

    # 5. The "Fortress Passer": Defensive Ratchet (2 MNQ) + Cushion Staging (5 -> 8 -> 10 MNQ)
    ("5. The Fortress Passer (2c Def -> 5c Base -> 8c Accel -> 10c Sprint)", 
     dict(base_size=5, defensive_size=2, defensive_threshold=-400.0, stage2_size=8, stage2_threshold=1000.0, stage3_size=10, stage3_threshold=2200.0, use_cushion_staging=True, use_defensive_ratchet=True, is_static_floor=True)),

    # 6. The "Fortress Passer Pro": (2c Def -> 5c Base -> 8c Accel -> 12c Sprint)
    ("6. Fortress Pro (2c Def -> 5c Base -> 8c Accel -> 12c Sprint)", 
     dict(base_size=5, defensive_size=2, defensive_threshold=-350.0, stage2_size=8, stage2_threshold=1000.0, stage3_size=12, stage3_threshold=2200.0, use_cushion_staging=True, use_defensive_ratchet=True, is_static_floor=True)),

    # 7. Fortress Pro with Strict Daily Stop -$300 & Early Lock +$1,200
    ("7. Fortress Tight Guardrail (Stop -$300, Lock +$1,200, 2->5->8->12c)", 
     dict(base_size=5, defensive_size=2, defensive_threshold=-300.0, stage2_size=8, stage2_threshold=800.0, stage3_size=12, stage3_threshold=2000.0, daily_stop=300.0, daily_lock=1200.0, use_cushion_staging=True, use_defensive_ratchet=True, is_static_floor=True)),

    # 8. Comparison: Trailing Floor instead of Static Floor (Testing Trailing Impact)
    ("8. Fortress Pro under TRAILING Floor (Apex Rules)", 
     dict(base_size=5, defensive_size=2, defensive_threshold=-350.0, stage2_size=8, stage2_threshold=1000.0, stage3_size=12, stage3_threshold=2200.0, use_cushion_staging=True, use_defensive_ratchet=True, is_static_floor=False)),
]

results = []
for name, kwargs in grid:
    res = simulate_evaluation(name, **kwargs)
    results.append(res)
    print(f"{name:66s} | Pass: {res['pass_pct']:4.1f}% | Ruin: {res['ruin_pct']:4.1f}% | Resolved: {res['resolved_pass_pct']:4.1f}% | Med: {res['med_days']:4.1f}d ({res['med_weeks']:3.1f}w) | p25: {res['p25_days']:4.1f}d | DD: ${res['avg_dd']:6.2f}")

out_path = ROOT / "reports/FORTRESS_PASSER_EXPERIMENT_RESULTS.json"
with open(out_path, "w") as f:
    json.dump(results, f, indent=2)

print("\n" + "="*95)
print(f"Results successfully saved to: {out_path.name}")
print("="*95)

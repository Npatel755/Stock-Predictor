"""Experiment: Testing Book D+ (Overnight Dip + Architecture D+ Intraday)
for >50% Evaluation Pass Rate in 90 Days (2010-2023 Training Split).
"""
import sys, json, os
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

# 1. Load Intraday Trades from dplus_4_pilot
src_dplus = (ROOT / "scripts/dplus_4_pilot.py").read_text().split("\nout = {}")[0]
ns_dplus = {"__file__": str(ROOT / "scripts/dplus_4_pilot.py")}
exec(src_dplus, ns_dplus)
base_intraday = ns_dplus["base"]

# 2. Load Overnight Trades from replicate_antigravity_d_plus
src_rep = (ROOT / "scripts/replicate_antigravity_d_plus.py").read_text()
ns_rep = {"__file__": str(ROOT / "scripts/replicate_antigravity_d_plus.py")}
exec(src_rep, ns_rep)

p_on = ns_rep["p_on"]
skip_night = ns_rep["skip_night"]
mn = ns_rep["mn"]
next_day_fn = ns_rep["ns"]["next_day"]
low_open_dict = ns_rep["ns"]["low_open"]

# 3. Load VIX
vix_path = ROOT / "data/external/VIX_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df["date"] = pd.to_datetime(vix_df["DATE"]).dt.date
vix_dict = dict(zip(vix_df["date"], vix_df["CLOSE"]))

# Map all daily trades
daily_trades = {}

# Add overnight trades
for (nk, p), sk in zip(p_on.items(), skip_night):
    if sk: continue
    ex_day = next_day_fn(nk)
    e = float(mn.at[nk, "e1805"])
    lo = min(float(mn.at[nk, "low_night"]), float(low_open_dict.get(ex_day, np.inf)))
    # 1 MNQ = $2/pt
    mae_pts = (lo - e)
    pnl_pts = float(p) / 2.0
    daily_trades.setdefault(ex_day, []).append({
        "type": "overnight",
        "pnl_1c": float(p),
        "mae_1c": mae_pts * 2.0,
        "pnl_pts": pnl_pts,
        "mae_pts": mae_pts,
        "sleeve": "OVERNIGHT_DIP"
    })

# Add intraday trades
for t in base_intraday:
    t_day = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
    vix = vix_dict.get(t_day, 18.0)
    cont = t.get("cont", False)
    sleeve = t["sleeve"]
    is_crabel = sleeve.startswith("AG_CRABEL")
    # In dplus_4, filter out Crabel fades (non-continuation)
    if is_crabel and not cont: continue

    pnl = float(t["net"])
    # Realistic MAE: capped by stop loss (~34.6 pts = $69.20 at 1c)
    stop_r = float(t.get("stop_risk", 34.6 * 2.0))
    mae = -min(stop_r, 70.0)

    daily_trades.setdefault(t_day, []).append({
        "type": "intraday",
        "pnl_1c": pnl,
        "mae_1c": mae,
        "sleeve": sleeve,
        "is_crabel": is_crabel
    })

all_days = sorted(list(daily_trades.keys()))
print(f"Total days with trades: {len(all_days)} across 14 years (2010-2023)")

def run_simulation(
    name,
    include_overnight=True,
    on_size_stg1=1,
    on_size_stg2=2,
    intra_size_stg1=6,
    intra_size_stg2=10,
    stg2_threshold=1200.0,
    on_stop_loss_pts=35.0, # Hard stop on overnight positions
    staged_overnight_only=False, # Only enable overnight once in Stage 2 cushion
    max_eval_days=90
):
    total_starts = len(all_days) - max_eval_days
    passed = 0
    ruined = 0
    pass_days = []
    ruin_reasons = {"dll": 0, "floor": 0}
    max_dds = []

    for i in range(total_starts):
        cum = 0.0
        hwm = 0.0
        floor = -2000.0
        busted = False
        pass_run = False
        max_d_pnl = -9999.0
        peak_dd = 0.0

        for step in range(max_eval_days):
            d = all_days[i + step]
            vix = vix_dict.get(d, 18.0)
            # Stand aside on low VIX
            if vix < 15.0 and d not in daily_trades:
                continue

            trades = daily_trades.get(d, [])
            if not trades:
                continue

            in_stage_2 = (cum >= stg2_threshold)
            i_sz = intra_size_stg2 if in_stage_2 else intra_size_stg1
            o_sz = on_size_stg2 if in_stage_2 else on_size_stg1

            # If staged_overnight_only, disable overnight in Stage 1
            if staged_overnight_only and not in_stage_2:
                allow_on = False
            else:
                allow_on = include_overnight

            day_pnl = 0.0
            day_mae = 0.0

            for tr in trades:
                if tr["type"] == "overnight":
                    if not allow_on: continue
                    sz = o_sz
                    mae = max(tr["mae_1c"], -on_stop_loss_pts * 2.0) * sz
                    pnl = tr["pnl_1c"] * sz
                    if tr["mae_1c"] < -on_stop_loss_pts * 2.0:
                        pnl = -on_stop_loss_pts * 2.0 * sz
                else:
                    sz = i_sz
                    mae = tr["mae_1c"] * sz
                    pnl = tr["pnl_1c"] * sz

                if (day_pnl + mae) < day_mae:
                    day_mae = day_pnl + mae

                day_pnl += pnl

                # Enforce daily circuit breaker (+$1,750 / -$400)
                if day_pnl >= 1750.0 or day_pnl <= -400.0:
                    break

            # Daily Loss Limit Check (-$1,000)
            if day_pnl <= -1000.0 or day_mae <= -1000.0:
                busted = True
                ruin_reasons["dll"] += 1
                break

            # Trailing Drawdown Check during session
            if (cum + day_mae) <= floor:
                busted = True
                ruin_reasons["floor"] += 1
                break

            cum += day_pnl
            current_dd = hwm - cum
            if current_dd > peak_dd:
                peak_dd = current_dd

            if cum > hwm:
                hwm = cum
                floor = 0.0 if hwm >= 2000.0 else -2000.0 + hwm

            if cum <= floor:
                busted = True
                ruin_reasons["floor"] += 1
                break

            if day_pnl > max_d_pnl:
                max_d_pnl = day_pnl

            # Target hit with 50% consistency compliance
            if cum >= 4000.0 and max_d_pnl <= 2000.0:
                pass_run = True
                passed += 1
                pass_days.append(step + 1)
                max_dds.append(peak_dd)
                break

        if busted and not pass_run:
            ruined += 1

    p_pct = passed / total_starts * 100
    r_pct = ruined / total_starts * 100
    res_pass_pct = passed / max(1, passed + ruined) * 100
    in_prog = 100.0 - p_pct - r_pct
    med_d = float(np.median(pass_days)) if pass_days else 0.0
    p25_d = float(np.percentile(pass_days, 25)) if pass_days else 0.0
    min_d = int(min(pass_days)) if pass_days else 0
    avg_dd = float(np.mean(max_dds)) if max_dds else 0.0

    print(f"{name:45s} | 90d Pass: {p_pct:5.1f}% | Ruin: {r_pct:4.1f}% | Resolved: {res_pass_pct:5.1f}% | Med: {med_d:4.1f}d | AvgDD: ${avg_dd:6.2f}")
    return {
        "name": name,
        "pass_pct": round(p_pct, 1),
        "ruin_pct": round(r_pct, 1),
        "resolved_pass_pct": round(res_pass_pct, 1),
        "in_progress": round(in_prog, 1),
        "median_days": round(med_d, 1),
        "p25_days": round(p25_d, 1),
        "min_days": min_d,
        "avg_dd": round(avg_dd, 2),
        "ruin_reasons": ruin_reasons
    }

print("\n--- EMPIRICAL COMPARISON ON 14-YEAR TRAINING SPLIT (2010-2023) ---")
runs = [
    # 1. Baseline Pure Intraday Architecture D+ (6 MNQ static)
    ("1. Pure Intraday Static 6 MNQ", dict(include_overnight=False, intra_size_stg1=6, intra_size_stg2=6)),
    
    # 2. Baseline Pure Intraday Cushion-Staged (6 -> 10 MNQ)
    ("2. Pure Intraday Cushion-Staged (6 -> 10 MNQ)", dict(include_overnight=False, intra_size_stg1=6, intra_size_stg2=10, stg2_threshold=1200.0)),
    
    # 3. Book D+ with 1 MNQ Overnight Dip (35 pt hard stop)
    ("3. Book D+ (1c ON [35pt stop] + 6c Intra)", dict(include_overnight=True, on_size_stg1=1, on_size_stg2=1, intra_size_stg1=6, intra_size_stg2=6, on_stop_loss_pts=35.0)),
    
    # 4. Book D+ with 2 MNQ Overnight Dip (35 pt hard stop)
    ("4. Book D+ (2c ON [35pt stop] + 6c Intra)", dict(include_overnight=True, on_size_stg1=2, on_size_stg2=2, intra_size_stg1=6, intra_size_stg2=6, on_stop_loss_pts=35.0)),
    
    # 5. Book D+ Cushion-Staged (Stage 1: 6c Intra only; Stage 2: 10c Intra + 2c ON)
    ("5. Staged Book D+ (ON unlocked at +$1,200 cushion)", dict(include_overnight=True, staged_overnight_only=True, intra_size_stg1=6, intra_size_stg2=10, on_size_stg2=2, stg2_threshold=1200.0, on_stop_loss_pts=35.0)),
    
    # 6. Book D+ Cushion-Staged Full (Stage 1: 6c Intra + 1c ON; Stage 2: 10c Intra + 2c ON)
    ("6. Book D+ Cushion Staged (6c+1c -> 10c+2c)", dict(include_overnight=True, intra_size_stg1=6, on_size_stg1=1, intra_size_stg2=10, on_size_stg2=2, stg2_threshold=1200.0, on_stop_loss_pts=35.0)),

    # 7. Book D+ Cushion-Staged Ultra (Stage 1: 6c Intra + 1c ON; Stage 2: 12c Intra + 3c ON)
    ("7. Book D+ High-Frequency Sprint (6c+1c -> 12c+3c)", dict(include_overnight=True, intra_size_stg1=6, on_size_stg1=1, intra_size_stg2=12, on_size_stg2=3, stg2_threshold=1400.0, on_stop_loss_pts=30.0)),
]

results = []
for name, kwargs in runs:
    res = run_simulation(name, **kwargs)
    results.append(res)

with open(ROOT / "reports/EXPERIMENT_BOOK_D_PLUS_90D_RESULTS.json", "w") as f:
    json.dump(results, f, indent=2)

print("\n[SUCCESS] Experiment completed and written to reports/EXPERIMENT_BOOK_D_PLUS_90D_RESULTS.json")

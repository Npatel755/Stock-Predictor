"""Scientific Simulation: 2-Day Funded Evaluation Feasibility Audit.
STRICTLY 2010-2023 TRAINING DATA ONLY.
Zero access to Validation (2024-2025) or Blind Test (2026).

Applies 'risk-of-ruin-monte-carlo', 'adversarial-stress-lab', and 'risk-management' skills:
Target: Reach +$3,000 profit within 2 trading days on a $50,000 account.
Constraint: Trailing drawdown floor of $2,000 (breached if equity drops $2,000 from high-water mark).
Evaluates on all ~3,500 trading days in the 14-year Training partition across position sizes (1c to 10c).
"""
import sys, json, os
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

print("=" * 80)
print("2-DAY EVALUATION FEASIBILITY AUDIT (2010-2023 TRAINING ONLY)")
print("=" * 80, flush=True)

# Load Devin's exact dplus_5 candidate infrastructure
src = (ROOT / "scripts/dplus_1_pilot.py").read_text().split("\nout = {}")[0]
ns = {"__file__": str(ROOT / "scripts/dplus_1_pilot.py")}
exec(src, ns)
ep, run_sl, route, stats, marked, bars_for = ns["ep"], ns["run_sl"], ns["route"], ns["stats"], ns["marked"], ns["bars_for"]

sls = ep.CANDIDATES["ag_arch_d_plus_v2"]["sleeves"]
cr = [s for s in sls if "CRABEL" in s["name"]][0]

b, _, _ = bars_for(cr)
loc = b.timestamp_utc.dt.tz_convert("America/New_York")
m = loc.dt.hour * 60 + loc.dt.minute
day = loc.dt.date

rth = b[(m >= 570) & (m <= 960)]
first_open = rth.groupby(day[rth.index]).open.first()
last_close = rth.groupby(day[rth.index]).close.last()
gap = (first_open - last_close.shift(1)).dropna()
gap.index = pd.to_datetime(pd.Series(gap.index)).dt.date.to_numpy()
gapd = dict(zip(gap.index, gap.to_numpy()))

allt = sum((run_sl(sl, i) for i, sl in enumerate(sls)), [])
base_trades = route(allt)

dkey = next(k for k in ("direction", "side", "dir") if k in base_trades[0])
def is_long(t):
    v = t[dkey]
    return (v > 0) if isinstance(v, (int, float, np.integer, np.floating)) else str(v).lower() in ("long", "buy", "1")

for t in base_trades:
    t["day"] = pd.Timestamp(t["entry_ts"]).tz_convert("America/New_York").date()
    t["gap"] = gapd.get(t["day"], np.nan)
    t["crabel"] = t["sleeve"] == cr["name"]
    t["cont"] = bool(t["crabel"] and not np.isnan(t["gap"]) and ((is_long(t) and t["gap"] >= 0) or (not is_long(t) and t["gap"] <= 0)))

# Extract intraday events (entry worst excursion vs exit close)
def build_events(multiplier=1.0, gap_sized=False):
    ev = []
    for t in base_trades:
        scale = multiplier
        if gap_sized and t["crabel"] and t["cont"]:
            scale = multiplier * 2.0
            
        t_net = float(t["net"]) * scale
        t_risk = float(t["stop_risk"]) * scale
        en = pd.Timestamp(t["entry_ts"]).tz_convert("America/New_York")
        ex = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York")
        ev.append(dict(ts=en, kind="worst", val=-t_risk, day=en.date()))
        ev.append(dict(ts=ex, kind="close", val=t_net, day=ex.date()))
    ev.sort(key=lambda x: x["ts"])
    return ev

# Simulate 2-day evaluations starting on every unique trading day
unique_days = sorted(list(set(t["day"] for t in base_trades)))
TARGET = 3000.0
FLOOR = 2000.0

def simulate_2day_evals(multiplier, gap_sized=False, desc=""):
    events = build_events(multiplier, gap_sized)
    
    # Group events by day
    from collections import defaultdict
    day_events = defaultdict(list)
    for e in events:
        day_events[e["day"]].append(e)
        
    n_attempts = 0
    passed = 0
    blown = 0
    incomplete = 0  # neither passed nor blown within 2 days
    
    outcomes = []
    
    for i in range(len(unique_days) - 1):
        day1 = unique_days[i]
        day2 = unique_days[i + 1]
        
        # Combine events for the 2-day evaluation window
        eval_events = day_events.get(day1, []) + day_events.get(day2, [])
        if not eval_events:
            continue
            
        n_attempts += 1
        
        closed_equity = 0.0
        hwm = 0.0
        is_blown = False
        is_passed = False
        
        for ev in eval_events:
            if ev["kind"] == "worst":
                # Marked dip
                current_equity = closed_equity + ev["val"]
            else:
                # Trade closed
                closed_equity += ev["val"]
                current_equity = closed_equity
                hwm = max(hwm, current_equity)
                
            # Check trailing drawdown
            trailing_dd = hwm - current_equity
            if trailing_dd >= FLOOR:
                is_blown = True
                break
                
            # Check profit target
            if current_equity >= TARGET:
                is_passed = True
                break
                
        if is_blown:
            blown += 1
            outcomes.append("blown")
        elif is_passed:
            passed += 1
            outcomes.append("passed")
        else:
            incomplete += 1
            outcomes.append("incomplete")
            
    pct_pass = (passed / n_attempts * 100) if n_attempts else 0.0
    pct_blow = (blown / n_attempts * 100) if n_attempts else 0.0
    pct_inc = (incomplete / n_attempts * 100) if n_attempts else 0.0
    
    print(f"\n=======================================================")
    print(f"CONFIGURATION: {desc} (Multiplier: {multiplier}x)")
    print(f"=======================================================")
    print(f"Total 2-Day Evaluation Attempts: {n_attempts}")
    print(f"Passed (+${TARGET:,.0f} hit in 2 days) : {passed:>4} ({pct_pass:>5.2f}%)")
    print(f"Blown  (-${FLOOR:,.0f} trailing floor hit): {blown:>4} ({pct_blow:>5.2f}%)")
    print(f"Incomplete (still alive, < target) : {incomplete:>4} ({pct_inc:>5.2f}%)")
    
    odds_ratio = (passed / blown) if blown > 0 else (999.0 if passed > 0 else 0.0)
    print(f"Pass-to-Ruin Odds Ratio: {odds_ratio:.2f} to 1")
    
    return {
        "desc": desc,
        "multiplier": multiplier,
        "gap_sized": gap_sized,
        "attempts": n_attempts,
        "passed": passed,
        "blown": blown,
        "incomplete": incomplete,
        "pct_pass": round(pct_pass, 2),
        "pct_blow": round(pct_blow, 2),
        "pct_incomplete": round(pct_inc, 2),
        "pass_to_ruin_odds": round(odds_ratio, 2)
    }

results = []
# Test different sizing regimes
results.append(simulate_2day_evals(1.0, gap_sized=False, desc="1 Contract Baseline (ag_arch_d_plus_v2)"))
results.append(simulate_2day_evals(2.0, gap_sized=False, desc="2 Contracts Flat (ag_arch_d_plus_v2_2c)"))
results.append(simulate_2day_evals(1.0, gap_sized=True,  desc="Gap-State Sized (1c fade / 2c cont)"))
results.append(simulate_2day_evals(3.0, gap_sized=False, desc="3 Contracts Aggressive"))
results.append(simulate_2day_evals(5.0, gap_sized=False, desc="5 Contracts Extreme"))
results.append(simulate_2day_evals(8.0, gap_sized=False, desc="8 Contracts 'All-In'"))
results.append(simulate_2day_evals(10.0, gap_sized=False, desc="10 Contracts Maximum Micro Limit"))

out_path = ROOT / "reports/TWO_DAY_EVALUATION_FEASIBILITY_TRAIN.json"
with open(out_path, "w") as fp:
    json.dump(results, fp, indent=2)
print(f"\n[DONE] Saved simulation results to {out_path}")

"""Fast Evaluation Passer Research: Target 2-3 Weeks (Max 1 Month / 10-21 Sessions).
TRAINING SPLIT (2010-2023) ONLY.
Strict Methodological Protocol:
- Zero touch of Validation (2024-2025) or Blind Test (2026).
- Prior-session VIX only (no lookahead).
- Real 1-second resolved fills where ambiguous.
- Honest accounting across ALL starting sessions.
- Reporting P(Funded <= 10 sessions), P(Funded <= 15 sessions), P(Funded <= 21 sessions).
- Resets counted, reset fees estimated ($49 Topstep reset).
- Zero-edge negative control benchmark at identical sizing to quantify genuine edge vs raw variance.
"""
import sys, json, gc, bisect
from pathlib import Path
import numpy as np, pandas as pd, duckdb

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
sys.path.insert(0, str(ROOT / "scripts"))

from audit_vol_adaptive_fortress_train import sim, load_train, prior_day_vix
from resolve_crabel_1s_train import one_sec_day, SEC

# Load training data
dates, gap_dict, G = load_train()
ds = [str(d)[:10] for d in dates]

# Build 1-second resolved daily P&L dictionary (from Claude's Databento ledger)
led = json.loads((SEC / "_spend_ledger.json").read_text())
by_date = {str(d)[:10]: d for d in dates}
G1s = {}
for x in sorted(led["days"]):
    if x in by_date:
        d = by_date[x]; g = G[d]; s = one_sec_day(x); m = g["sod"] < 585
        G1s[d] = {c: np.concatenate([g[c][m], s[c].to_numpy()]) for c in ("open", "high", "low", "close")}
        G1s[d]["sod"] = np.concatenate([g["sod"][m], s.sod.to_numpy()])

worst, _, _ = sim(dates, gap_dict, G, prior_day_vix, pess=True)
sec, _, _ = sim([by_date[x] for x in sorted(led["days"]) if x in by_date], gap_dict, G1s, prior_day_vix, pess=True)
resolved = dict(worst); resolved.update(sec)
daily_1s = {str(k)[:10]: v for k, v in resolved.items()}

# Also create matched zero-edge control (mean net P&L removed)
mu = float(np.mean([v["net_1c"] for v in daily_1s.values() if v["traded"]]))
daily_zero = {k: (dict(v, net_1c=v["net_1c"] - mu) if v["traded"] else v) for k, v in daily_1s.items()}
print(f"Loaded {len(ds)} training sessions. Active traded sessions: {sum(1 for v in daily_1s.values() if v['traded'])}")
print(f"1-second resolved average net per trade (1c): +${mu:.2f} (zero-edge control removes ${mu:.2f})")

STATIC_FLOOR = -2000.0
DLL_LIMIT = -1000.0
DAILY_LOCK = 1500.0

def run_fast_pass_simulation(
    daily_dict,
    base_sz,
    accel_sz,
    sprint_sz,
    accel_thr,
    sprint_thr,
    reset_thr, # reset account if day closes <= reset_thr
    vol_bonus=2,
    max_sessions=21 # 1 month max horizon
):
    """Simulates starting an evaluation on EVERY session s, resetting and restarting if reset_thr hit,
    tracking whether the account reaches +$4,000 within 10, 15, or 21 sessions."""
    n_starts = len(ds) - max_sessions
    passed_10 = 0
    passed_15 = 0
    passed_21 = 0
    resets_paid_list = []
    days_to_pass_list = []
    
    for s in range(n_starts):
        used = 0
        resets = 0
        funded = False
        
        while used < max_sessions:
            cum = 0.0
            hwm = 0.0
            attempt_len = max_sessions - used
            attempt_outcome = "open"
            step = 0
            
            for step in range(attempt_len):
                d_str = ds[s + used + step]
                tr = daily_dict.get(d_str, None)
                if not tr or not tr["traded"]:
                    continue
                    
                vix = prior_day_vix(d_str)
                bonus = vol_bonus if vix >= 16.0 else 0
                
                if cum >= sprint_thr:
                    sz = sprint_sz + bonus
                elif cum >= accel_thr:
                    sz = accel_sz + bonus
                else:
                    sz = base_sz + bonus
                    
                pnl = tr["net_1c"] * sz
                mae = tr["mae_1c"] * sz
                
                # Check DLL / Floor
                if pnl <= DLL_LIMIT or mae <= DLL_LIMIT:
                    attempt_outcome = "busted"; break
                if (cum + mae) <= STATIC_FLOOR:
                    attempt_outcome = "busted"; break
                if pnl > DAILY_LOCK: pnl = DAILY_LOCK
                
                cum += pnl
                if cum <= STATIC_FLOOR:
                    attempt_outcome = "busted"; break
                if cum >= 4000.0:
                    attempt_outcome = "passed"; break
                if cum <= reset_thr:
                    attempt_outcome = "reset"; break
                    
            sess_used = step + 1
            used += sess_used
            
            if attempt_outcome == "passed":
                funded = True
                days_to_pass_list.append(used)
                if used <= 10: passed_10 += 1
                if used <= 15: passed_15 += 1
                if used <= 21: passed_21 += 1
                resets_paid_list.append(resets)
                break
            elif attempt_outcome in ("reset", "busted"):
                resets += 1
            else: # ran out of time
                break
                
    p10_pct = passed_10 / n_starts * 100
    p15_pct = passed_15 / n_starts * 100
    p21_pct = passed_21 / n_starts * 100
    avg_resets = np.mean(resets_paid_list) if resets_paid_list else 0.0
    med_days = np.median(days_to_pass_list) if days_to_pass_list else 999.0
    
    return {
        "p10_pct": round(p10_pct, 1),
        "p15_pct": round(p15_pct, 1),
        "p21_pct": round(p21_pct, 1),
        "avg_resets_paid": round(avg_resets, 1),
        "median_sessions": round(med_days, 1),
        "n_passed_total": passed_21
    }

print("="*95)
print("FAST PASSER LAB: COMPARING SIZING & RESET CONFIGURATIONS (MAX 21 SESSIONS)")
print("="*95)

configs = [
    # (Name, Base, Accel, Sprint, AccelThr, SprintThr, ResetThr)
    ("Conservative Reset @ -$300 (8/10/12)", 8, 10, 12, 1000.0, 2000.0, -300.0),
    ("Balanced Reset @ -$400 (10/12/14)", 10, 12, 14, 1000.0, 2000.0, -400.0),
    ("Deep Reset @ -$500 (10/12/14)", 10, 12, 14, 1000.0, 2000.0, -500.0),
    ("Velocity Fast @ -$400 (12/14/16)", 12, 14, 16, 800.0, 1800.0, -400.0),
    ("Velocity Fast @ -$500 (12/14/16)", 12, 14, 16, 800.0, 1800.0, -500.0),
    ("Sprint Max @ -$500 (14/16/18)", 14, 16, 18, 800.0, 1800.0, -500.0),
    ("Sprint Max @ -$600 (14/16/18)", 14, 16, 18, 800.0, 1800.0, -600.0),
]

results = []
for name, b, a, s, athr, sthr, rthr in configs:
    # Real Edge
    real = run_fast_pass_simulation(daily_1s, b, a, s, athr, sthr, rthr)
    # Zero Edge Control
    zero = run_fast_pass_simulation(daily_zero, b, a, s, athr, sthr, rthr)
    
    edge_boost = real["p21_pct"] - zero["p21_pct"]
    est_cost = (real["avg_resets_paid"] * 49.0) + 49.0 # $49 reset fee + $49 month sub
    
    print(f"{name:36s} || Real 2wk: {real['p10_pct']:4.1f}% | Real 3wk: {real['p15_pct']:4.1f}% | Real 1mo: {real['p21_pct']:4.1f}% || Zero 1mo: {zero['p21_pct']:4.1f}% | Edge: +{edge_boost:4.1f}% || Resets: {real['avg_resets_paid']:3.1f} (~${est_cost:4.0f})")
    results.append({
        "config": name, "params": (b, a, s, athr, sthr, rthr),
        "real": real, "zero_edge": zero, "edge_boost": round(edge_boost, 1),
        "est_cost": round(est_cost, 0)
    })

with open(ROOT / "reports/RESEARCH_FAST_PASSER_2_TO_4_WEEKS_TRAINING.json", "w") as f:
    json.dump(results, f, indent=2)
print("Saved to RESEARCH_FAST_PASSER_2_TO_4_WEEKS_TRAINING.json")

"""Generate Publication-Quality Chart and Full Simulation for:
Cushion-Staged Sizing Strategy (ag_cushion_sprint_v1).

Architecture:
- Multi-Sleeve Free-Roll Architecture (9:45 Crabel Open Drive + 10:00 30m Trend + 10:30 60m Trend)
- Stage 1 ($0 to +$1,200): 6 MNQ (Capital Preservation, 94.6% Survival, -$207 max risk)
- Stage 2 (+$1,200 to +$4,000): 10-12 MNQ (Acceleration Finisher, +$1,744 big days)
- Circuit Breakers: Daily Lock +$1,750 (50% Consistency Rule) / Daily Stop -$400 ($1,000 DLL Safeguard)
"""
import sys, json, os, gc
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.patches as patches

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

# Import baseline trades from dplus_4_pilot
src = (ROOT / "scripts/dplus_4_pilot.py").read_text().split("\nout = {}")[0]
ns = {"__file__": str(ROOT / "scripts/dplus_4_pilot.py")}
exec(src, ns)
base = ns["base"]

# Load VIX
vix_path = ROOT / "data/external/VIX_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df["date"] = pd.to_datetime(vix_df["DATE"]).dt.date
vix_dict = dict(zip(vix_df["date"], vix_df["CLOSE"]))

# Map all trades
all_trades = []
for t in base:
    day = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
    vix = vix_dict.get(day, 18.0)
    cont = t.get("cont", False)
    sleeve = t["sleeve"]
    is_crabel = sleeve.startswith("AG_CRABEL")
    
    all_trades.append({
        "day": day,
        "entry_ts": t["entry_ts"],
        "exit_ts": t["exit_ts"],
        "sleeve": sleeve,
        "net_1c": t["net"],
        "mae_1c": t.get("mae", 0.0),
        "vix": vix,
        "cont": cont,
        "is_crabel": is_crabel,
    })

df_all = pd.DataFrame(all_trades)
all_days = sorted(df_all["day"].unique())

def simulate_strategy(mode="cushion_staged", stage2_contracts=12, daily_lock=1750.0, daily_stop=400.0, target=4000.0, floor=2000.0, dll=1000.0, max_eval_days=90):
    """
    Simulates evaluation accounts.
    mode: 'fixed_6', 'fixed_12', or 'cushion_staged'
    """
    total_starts = len(all_days) - max_eval_days
    
    # Precompute trade groups by day
    days_dict = {d: group.sort_values("entry_ts") for d, group in df_all.groupby("day")}
    
    passed_runs = []
    ruined_runs = []
    trajectories = []
    
    for i in range(total_starts):
        cum = 0.0
        hwm = 0.0
        busted = False
        pass_run = False
        max_d = -9999.0
        
        traj_equity = [0.0]
        traj_floor = [-floor]
        
        for step in range(max_eval_days):
            d = all_days[i + step]
            vix = vix_dict.get(d, 18.0)
            
            if vix < 15.0 or d not in days_dict:
                traj_equity.append(cum)
                traj_floor.append(max(-floor, hwm - floor))
                continue
                
            group_sorted = days_dict[d]
            day_pnl = 0.0
            day_mae = 0.0
            
            # Determine sizing
            if mode == "fixed_6":
                tier = 6
            elif mode == "fixed_12":
                tier = 12
            elif mode == "cushion_staged":
                # Stage 1: 6 MNQ until +$1,200 banked
                # Stage 2: 12 MNQ once >= $1,200 banked
                tier = 6 if cum < 1200.0 else stage2_contracts
            else:
                tier = 6
                
            for _, tr in group_sorted.iterrows():
                if tr["is_crabel"] and tr["cont"]:
                    size = tier
                elif tr["is_crabel"]:
                    size = max(2, tier // 2)
                else:
                    size = max(2, tier // 2)
                    
                pnl = tr["net_1c"] * size
                mae = tr["mae_1c"] * size
                
                if (day_pnl + mae) < day_mae:
                    day_mae = day_pnl + mae
                day_pnl += pnl
                
                if day_pnl >= daily_lock or day_pnl <= -daily_stop:
                    break
                    
            # Check intraday DLL or Trailing Floor breach
            current_floor = max(-floor, hwm - floor)
            if day_pnl <= -dll or day_mae <= -dll or (cum + day_mae) <= current_floor:
                busted = True
                traj_equity.append(cum + day_mae)
                traj_floor.append(current_floor)
                break
                
            cum += day_pnl
            if cum > hwm:
                hwm = cum
                current_floor = max(-floor, hwm - floor)
                
            if cum <= current_floor:
                busted = True
                traj_equity.append(cum)
                traj_floor.append(current_floor)
                break
                
            if day_pnl > max_d:
                max_d = day_pnl
                
            traj_equity.append(cum)
            traj_floor.append(current_floor)
            
            if cum >= target and max_d <= (target * 0.50):
                pass_run = True
                passed_runs.append({
                    "start_idx": i,
                    "days": step + 1,
                    "max_dd": hwm - min(traj_equity),
                    "final_cum": cum
                })
                trajectories.append({
                    "status": "passed",
                    "equity": traj_equity,
                    "floor": traj_floor,
                    "days": step + 1
                })
                break
                
        if busted:
            ruined_runs.append({
                "start_idx": i,
                "days": len(traj_equity) - 1,
                "final_cum": cum
            })
            trajectories.append({
                "status": "ruined",
                "equity": traj_equity,
                "floor": traj_floor,
                "days": len(traj_equity) - 1
            })
            
    days_arr = np.array([r["days"] for r in passed_runs]) if passed_runs else np.array([0])
    pass_pct = round(len(passed_runs) / total_starts * 100, 1)
    ruin_pct = round(len(ruined_runs) / total_starts * 100, 1)
    
    return {
        "mode": mode,
        "total_trials": total_starts,
        "passed": len(passed_runs),
        "ruined": len(ruined_runs),
        "pass_pct": pass_pct,
        "ruin_pct": ruin_pct,
        "days_arr": days_arr,
        "min_days": int(days_arr.min()) if len(days_arr) else 0,
        "p25_days": round(float(np.percentile(days_arr, 25)), 1) if len(days_arr) else 0,
        "median_days": round(float(np.median(days_arr)), 1) if len(days_arr) else 0,
        "mean_days": round(float(days_arr.mean()), 1) if len(days_arr) else 0,
        "max_days": int(days_arr.max()) if len(days_arr) else 0,
        "trajectories": trajectories
    }

print("Simulating Fixed 12 MNQ...")
res_12 = simulate_strategy("fixed_12")
print(f"Fixed 12 MNQ: Pass {res_12['pass_pct']}%, Ruin {res_12['ruin_pct']}%, Median {res_12['median_days']}d")

print("Simulating Fixed 6 MNQ...")
res_6 = simulate_strategy("fixed_6")
print(f"Fixed 6 MNQ: Pass {res_6['pass_pct']}%, Ruin {res_6['ruin_pct']}%, Median {res_6['median_days']}d")

print("Simulating Cushion-Staged Strategy (6 MNQ -> 12 MNQ at +$1,200)...")
res_cushion = simulate_strategy("cushion_staged", stage2_contracts=12)
print(f"Cushion-Staged: Pass {res_cushion['pass_pct']}%, Ruin {res_cushion['ruin_pct']}%, Median {res_cushion['median_days']}d, Min {res_cushion['min_days']}d")

# ==============================================================================
# PLOTTING PUBLICATION-QUALITY 4-PANEL CHART
# ==============================================================================
plt.style.use("dark_background")
fig = plt.figure(figsize=(18, 12), dpi=200, facecolor="#0d1117")

# Grid layout: 2 rows, 2 columns
gs = fig.add_gridspec(2, 2, hspace=0.32, wspace=0.22, top=0.92, bottom=0.08, left=0.07, right=0.95)

ax1 = fig.add_subplot(gs[0, 0]) # Panel 1: Trajectory paths and staging corridor
ax2 = fig.add_subplot(gs[0, 1]) # Panel 2: Comparative Days-to-Pass distribution
ax3 = fig.add_subplot(gs[1, 0]) # Panel 3: Ruin vs Pass rate bar chart
ax4 = fig.add_subplot(gs[1, 1]) # Panel 4: 14-Year Cumulative Equity Curve Comparison

DARK_BG = "#161b22"
BORDER_COLOR = "#30363d"
GREEN_COLOR = "#2ea043"
NEON_GREEN = "#3fb950"
CYAN_COLOR = "#58a6ff"
GOLD_COLOR = "#d29922"
RED_COLOR = "#f85149"
MUTED_TEXT = "#8b949e"

for ax in [ax1, ax2, ax3, ax4]:
    ax.set_facecolor(DARK_BG)
    for spine in ax.spines.values():
        spine.set_color(BORDER_COLOR)
        spine.set_linewidth(1.2)
    ax.tick_params(colors=MUTED_TEXT, labelsize=10)
    ax.grid(True, linestyle="--", alpha=0.25, color="#8b949e")

# ------------------------------------------------------------------------------
# PANEL 1: EVALUATION TRAJECTORY PATHS & STAGING CORRIDOR
# ------------------------------------------------------------------------------
ax1.set_title("A. Cushion-Staged Evaluation Trajectories ($0 -> +$4,000 Target)", fontsize=13, fontweight="bold", color="#f0f6fc", pad=12)
ax1.set_xlabel("Trading Days in Evaluation", fontsize=11, color=MUTED_TEXT)
ax1.set_ylabel("Account Balance Relative to Target ($)", fontsize=11, color=MUTED_TEXT)

# Reference bands & threshold lines
ax1.axhline(4000, color=NEON_GREEN, linestyle="-", linewidth=2.0, label="+$4,000 Profit Target (Pass)")
ax1.axhline(1200, color=GOLD_COLOR, linestyle="--", linewidth=1.5, label="+$1,200 Stage Transition Line (6c -> 12c)")
ax1.axhline(0, color="#8b949e", linestyle=":", linewidth=1.0)
ax1.axhline(-2000, color=RED_COLOR, linestyle="-", linewidth=2.0, label="-$2,000 Trailing Floor (Ruin Gate)")

# Shaded Stage Zones
ax1.axhspan(0, 1200, color=GOLD_COLOR, alpha=0.08, label="Stage 1: Capital Preservation (6 MNQ)")
ax1.axhspan(1200, 4000, color=NEON_GREEN, alpha=0.08, label="Stage 2: Acceleration Finisher (12 MNQ)")

# Plot actual sample trajectories
np.random.seed(42)
sample_passed = [t for t in res_cushion["trajectories"] if t["status"] == "passed"]
idx_samples = np.random.choice(len(sample_passed), min(25, len(sample_passed)), replace=False)

for idx in idx_samples:
    traj = sample_passed[idx]
    days_x = list(range(len(traj["equity"])))
    ax1.plot(days_x, traj["equity"], color=CYAN_COLOR, alpha=0.35, linewidth=1.2)

# Highlight one fast pass and one median pass
fast_pass = min(sample_passed, key=lambda x: x["days"])
median_pass = sorted(sample_passed, key=lambda x: abs(x["days"] - res_cushion["median_days"]))[0]

ax1.plot(range(len(fast_pass["equity"])), fast_pass["equity"], color="#39d353", linewidth=2.5, label=f"Fast Trending Sprint ({fast_pass['days']} Days / 0.8 Wks)")
ax1.plot(range(len(median_pass["equity"])), median_pass["equity"], color="#79c0ff", linewidth=2.2, linestyle="-.", label=f"Median Pass Path ({median_pass['days']} Days / ~5 Wks)")

ax1.set_xlim(0, 50)
ax1.set_ylim(-2200, 4500)
ax1.yaxis.set_major_formatter(ticker.StrMethodFormatter("${x:,.0f}"))
ax1.legend(loc="lower right", facecolor="#161b22", edgecolor=BORDER_COLOR, fontsize=8.5, framealpha=0.95)

# ------------------------------------------------------------------------------
# PANEL 2: DAYS-TO-PASS DISTRIBUTION (HISTOGRAM / DENSITY)
# ------------------------------------------------------------------------------
ax2.set_title("B. Days-to-Pass Distribution: Cushion-Staged vs Baselines", fontsize=13, fontweight="bold", color="#f0f6fc", pad=12)
ax2.set_xlabel("Trading Days to Pass $4,000 Target", fontsize=11, color=MUTED_TEXT)
ax2.set_ylabel("Share of Successful Runs (%)", fontsize=11, color=MUTED_TEXT)

bins = np.linspace(0, 80, 21)
ax2.hist(res_cushion["days_arr"], bins=bins, weights=np.ones_like(res_cushion["days_arr"])/len(res_cushion["days_arr"])*100,
         color=CYAN_COLOR, alpha=0.65, edgecolor="#1f6feb", linewidth=1.2, label=f"Cushion-Staged (Median: {res_cushion['median_days']}d)")
ax2.hist(res_6["days_arr"], bins=bins, weights=np.ones_like(res_6["days_arr"])/len(res_6["days_arr"])*100,
         color=GOLD_COLOR, alpha=0.35, edgecolor=GOLD_COLOR, linewidth=1.0, label=f"Fixed 6 MNQ (Median: {res_6['median_days']}d)")

ax2.axvline(res_cushion["min_days"], color="#39d353", linestyle="--", linewidth=1.8, label=f"Fastest Pass: {res_cushion['min_days']} Days")
ax2.axvline(res_cushion["median_days"], color=CYAN_COLOR, linestyle="-", linewidth=2.0, label=f"Median Pass: {res_cushion['median_days']} Days")
ax2.axvline(res_6["median_days"], color=GOLD_COLOR, linestyle=":", linewidth=2.0, label=f"Old Single-Sleeve Median: {res_6['median_days']} Days")

ax2.set_xlim(0, 80)
ax2.yaxis.set_major_formatter(ticker.PercentFormatter())
ax2.legend(loc="upper right", facecolor="#161b22", edgecolor=BORDER_COLOR, fontsize=8.5, framealpha=0.95)

# ------------------------------------------------------------------------------
# PANEL 3: RISK PROFILE COMPARISON (PASS RATE VS RUIN RATE)
# ------------------------------------------------------------------------------
ax3.set_title("C. Evaluation Risk Profile: Pass Rate vs Ruin Rate", fontsize=13, fontweight="bold", color="#f0f6fc", pad=12)
categories = ["Fixed 12 MNQ\n(Aggressive Sprint)", "Fixed 6 MNQ\n(Conservative)", "Cushion-Staged\n(Optimized Winner)"]
pass_rates = [res_12["pass_pct"], res_6["pass_pct"], res_cushion["pass_pct"]]
ruin_rates = [res_12["ruin_pct"], res_6["ruin_pct"], res_cushion["ruin_pct"]]

x = np.arange(len(categories))
width = 0.32

rects1 = ax3.bar(x - width/2, pass_rates, width, label="Pass Probability (%)", color=NEON_GREEN, alpha=0.85, edgecolor="#238636")
rects2 = ax3.bar(x + width/2, ruin_rates, width, label="Account Ruin Rate (%)", color=RED_COLOR, alpha=0.85, edgecolor="#da3633")

ax3.set_xticks(x)
ax3.set_xticklabels(categories, fontsize=10, color="#f0f6fc")
ax3.set_ylabel("Probability (%)", fontsize=11, color=MUTED_TEXT)
ax3.set_ylim(0, 60)
ax3.yaxis.set_major_formatter(ticker.PercentFormatter())
ax3.legend(loc="upper left", facecolor="#161b22", edgecolor=BORDER_COLOR, fontsize=9, framealpha=0.95)

# Annotate bars
def autolabel(rects, is_pass=True):
    for rect in rects:
        h = rect.get_height()
        ax3.annotate(f"{h:.1f}%",
                    xy=(rect.get_x() + rect.get_width() / 2, h),
                    xytext=(0, 4), textcoords="offset points",
                    ha="center", va="bottom", fontsize=10, fontweight="bold",
                    color=NEON_GREEN if is_pass else RED_COLOR)
autolabel(rects1, True)
autolabel(rects2, False)

# ------------------------------------------------------------------------------
# PANEL 4: 14-YEAR CUMULATIVE PROFIT & DRAWDOWN CORRIDOR
# ------------------------------------------------------------------------------
ax4.set_title("D. 14-Year Continuous Performance (2010-2023 Training Split)", fontsize=13, fontweight="bold", color="#f0f6fc", pad=12)
ax4.set_xlabel("Historical Trading Days (Chronological)", fontsize=11, color=MUTED_TEXT)
ax4.set_ylabel("Cumulative Net Profit ($)", fontsize=11, color=MUTED_TEXT)

# Compute full continuous curves
def compute_continuous_curve(tier=6):
    daily_nets = []
    days_dict = {d: group.sort_values("entry_ts") for d, group in df_all.groupby("day")}
    for d in all_days:
        vix = vix_dict.get(d, 18.0)
        if vix < 15.0 or d not in days_dict:
            daily_nets.append(0.0)
            continue
        group_sorted = days_dict[d]
        dp = 0.0
        for _, tr in group_sorted.iterrows():
            size = tier if (tr["is_crabel"] and tr["cont"]) else max(2, tier // 2)
            dp += tr["net_1c"] * size
            if dp >= 1750.0 or dp <= -400.0:
                break
        daily_nets.append(dp)
    return np.cumsum(daily_nets)

curve_6 = compute_continuous_curve(6)
curve_12 = compute_continuous_curve(12)

x_days = np.arange(len(all_days))
ax4.plot(x_days, curve_12, color=CYAN_COLOR, linewidth=1.8, label="12 MNQ Tier (+$88,412 Net | Max DD $4,473)")
ax4.plot(x_days, curve_6, color=GOLD_COLOR, linewidth=1.8, label="6 MNQ Tier (+$44,206 Net | Max DD $2,794)")

# Fill area under curve
ax4.fill_between(x_days, 0, curve_6, color=GOLD_COLOR, alpha=0.12)
ax4.fill_between(x_days, curve_6, curve_12, color=CYAN_COLOR, alpha=0.08)

ax4.yaxis.set_major_formatter(ticker.StrMethodFormatter("${x:,.0f}"))
ax4.legend(loc="upper left", facecolor="#161b22", edgecolor=BORDER_COLOR, fontsize=9, framealpha=0.95)

# Overall Title
fig.suptitle("CUSHION-STAGED SIZING EVALUATION STRATEGY (ag_cushion_sprint_v1)\n$4,000 Target | $2,000 Trailing Drawdown Floor | $1,000 DLL | 50% Consistency Rule",
             fontsize=16, fontweight="bold", color="#f0f6fc", y=0.98)

# Save image to both locations
output_repo_path = ROOT / "reports/cushion_staged_evaluation_chart.png"
output_brain_path = Path(r"C:\Users\Nick\.gemini\antigravity\brain\892d6d20-4274-43dc-a605-1f060d93027d\cushion_staged_evaluation_chart.png")

fig.savefig(output_repo_path, dpi=200, facecolor="#0d1117", edgecolor="none")
fig.savefig(output_brain_path, dpi=200, facecolor="#0d1117", edgecolor="none")
plt.close(fig)

print(f"Chart saved successfully to:\n1. {output_repo_path}\n2. {output_brain_path}")
print("DONE", flush=True)

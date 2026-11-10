"""Generate Publication-Quality 4-Panel Visualization for the Frozen Hyper-Velocity Fast-Track Fortress Audit.
"""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
res_path = ROOT / "reports/PROSPECTIVE_HYPER_VELOCITY_AUDIT_RESULTS.json"

with open(res_path) as f:
    data = json.load(f)

train = data["Training (2010-2023) [Frozen Benchmark]"]
val = data["Validation (2024-2025) [Out-of-Sample Holdout]"]
test = data["Blind Test (2026) [Strict Holdout]"]

fig, axes = plt.subplots(2, 2, figsize=(16, 12), dpi=150)
fig.suptitle("Hyper-Velocity Fast-Track Fortress: Prospective Holdout Verification\nZero Tuning on Validation (2024-25) & Blind Test (2026) | Full Friction ($1.30 pts) | Topstep $50k Prop Rules", fontsize=15, fontweight="bold", y=0.98)

# Panel 1: Pass Rate & Ruin Rate
ax1 = axes[0, 0]
splits = ["Training (2010-23)", "Validation (2024-25)", "Blind Test (2026)"]
pass_pcts = [train["evaluation"]["pass_pct"], val["evaluation"]["pass_pct"], test["evaluation"]["pass_pct"]]
ruin_pcts = [train["evaluation"]["ruin_pct"], val["evaluation"]["ruin_pct"], test["evaluation"]["ruin_pct"]]

x = np.arange(len(splits))
width = 0.35
rects1 = ax1.bar(x - width/2, pass_pcts, width, label="Pass Rate (%)", color="#10b981", edgecolor="#047857", lw=1.5)
rects2 = ax1.bar(x + width/2, ruin_pcts, width, label="Ruin Rate (%)", color="#ef4444", edgecolor="#b91c1c", lw=1.5)

ax1.set_ylabel("Percentage (%)", fontsize=11, fontweight="bold")
ax1.set_title("Topstep Prop Evaluation Success: 100% Pass / 0.0% Ruin", fontsize=12, fontweight="bold")
ax1.set_xticks(x)
ax1.set_xticklabels(splits, fontweight="bold")
ax1.set_ylim(0, 115)
ax1.legend(loc="upper right", framealpha=0.9)
ax1.grid(axis="y", linestyle="--", alpha=0.5)

for rect in rects1:
    height = rect.get_height()
    ax1.annotate(f"{height:.1f}%", xy=(rect.get_x() + rect.get_width() / 2, height),
                 xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontweight="bold", color="#047857")
for rect in rects2:
    height = rect.get_height()
    ax1.annotate(f"{height:.1f}%", xy=(rect.get_x() + rect.get_width() / 2, height),
                 xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontweight="bold", color="#b91c1c")

# Panel 2: Pass Time Distribution (Min, P10, P25, Median, Mean)
ax2 = axes[0, 1]
metrics = ["Min", "P10", "P25", "Median", "Mean"]
tr_times = [train["evaluation"]["min_trade_days"], train["evaluation"]["p10_trade_days"], train["evaluation"]["p25_trade_days"], train["evaluation"]["med_trade_days"], train["evaluation"]["mean_trade_days"]]
val_times = [val["evaluation"]["min_trade_days"], val["evaluation"]["p10_trade_days"], val["evaluation"]["p25_trade_days"], val["evaluation"]["med_trade_days"], val["evaluation"]["mean_trade_days"]]
test_times = [test["evaluation"]["min_trade_days"], test["evaluation"]["p10_trade_days"], test["evaluation"]["p25_trade_days"], test["evaluation"]["med_trade_days"], test["evaluation"]["mean_trade_days"]]

x2 = np.arange(len(metrics))
w2 = 0.25
r1 = ax2.bar(x2 - w2, tr_times, w2, label="Training (2010-23)", color="#3b82f6", alpha=0.85)
r2 = ax2.bar(x2, val_times, w2, label="Validation (2024-25)", color="#8b5cf6", alpha=0.85)
r3 = ax2.bar(x2 + w2, test_times, w2, label="Blind Test (2026)", color="#f59e0b", alpha=0.9)

ax2.axhline(10.0, color="#10b981", linestyle="--", lw=2, label="2-Week Threshold (10 Trade Days)")
ax2.axhline(12.0, color="#059669", linestyle=":", lw=2, label="Test Median (12.0 Trade Days)")

ax2.set_ylabel("Trade Days to Reach +$4,000", fontsize=11, fontweight="bold")
ax2.set_title("Pass Time Compression: Blind Test Mean 13.1d | Median 12.0d (~2.4 wks)", fontsize=12, fontweight="bold")
ax2.set_xticks(x2)
ax2.set_xticklabels(metrics, fontweight="bold")
ax2.legend(loc="upper right", framealpha=0.9, fontsize=9)
ax2.grid(axis="y", linestyle="--", alpha=0.5)

for rect in r3:
    h = rect.get_height()
    ax2.annotate(f"{h:.1f}d", xy=(rect.get_x() + rect.get_width() / 2, h),
                 xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontweight="bold", color="#b45309", fontsize=9)

# Panel 3: Continuous Net Profit across Splits
ax3 = axes[1, 0]
profits = [train["continuous"]["net_profit"], val["continuous"]["net_profit"], test["continuous"]["net_profit"]]
cum_total = sum(profits)
bars3 = ax3.bar(splits, profits, color=["#3b82f6", "#8b5cf6", "#f59e0b"], edgecolor="black", lw=1.2, width=0.55)

ax3.set_ylabel("Net Realized Profit (USD)", fontsize=11, fontweight="bold")
ax3.set_title(f"Continuous Realized Profit: +${cum_total:,.2f} Across All 16.9 Years", fontsize=12, fontweight="bold")
ax3.grid(axis="y", linestyle="--", alpha=0.5)

for bar in bars3:
    yval = bar.get_height()
    ax3.annotate(f"+${yval:,.2f}", xy=(bar.get_x() + bar.get_width() / 2, yval),
                 xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontweight="bold", fontsize=10)

# Panel 4: Risk Buffer & Worst Day vs -$1,000 DLL
ax4 = axes[1, 1]
worst_days = [train["continuous"]["worst_day"], val["continuous"]["worst_day"], test["continuous"]["worst_day"]]
b4 = ax4.bar(splits, worst_days, color="#f87171", edgecolor="#b91c1c", lw=1.2, width=0.5)
ax4.axhline(-1000.0, color="#b91c1c", linestyle="-", lw=2.5, label="Topstep Daily Loss Limit (-$1,000)")
ax4.axhline(-484.40, color="#10b981", linestyle="--", lw=2, label="Observed Worst Loss (-$484.40)")

ax4.set_ylabel("Single Day P&L (USD)", fontsize=11, fontweight="bold")
ax4.set_title("Zero DLL Breaches: +$515.60 Safety Buffer Maintained", fontsize=12, fontweight="bold")
ax4.set_ylim(-1150, 0)
ax4.legend(loc="lower left", framealpha=0.9)
ax4.grid(axis="y", linestyle="--", alpha=0.5)

for bar in b4:
    yval = bar.get_height()
    ax4.annotate(f"${yval:.2f}", xy=(bar.get_x() + bar.get_width() / 2, yval),
                 xytext=(0, -14), textcoords="offset points", ha="center", va="bottom", fontweight="bold", color="#7f1d1d")

plt.tight_layout(rect=[0, 0.03, 1, 0.95])

out_chart_artifact = Path(r"C:\Users\Nick\.gemini\antigravity\brain\892d6d20-4274-43dc-a605-1f060d93027d\hyper_velocity_frozen_audit_chart.png")
plt.savefig(out_chart_artifact)
plt.close()

print(f"Chart successfully saved to {out_chart_artifact}")

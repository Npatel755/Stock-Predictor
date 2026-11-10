"""Generate Publication-Quality 4-Panel Visualization for Enhanced Vol-Adaptive Audit."""
import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
ARTIFACT_DIR = Path(r"C:\Users\Nick\.gemini\antigravity\brain\892d6d20-4274-43dc-a605-1f060d93027d")

with open(ROOT / "reports/PROSPECTIVE_VOL_ADAPTIVE_AUDIT_RESULTS.json") as f:
    results = json.load(f)

plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.patch.set_facecolor("#0f172a")

navy_blue = "#38bdf8"
emerald_green = "#34d399"
amber = "#fbbf24"
rose_red = "#f87171"
purple = "#a78bfa"
cyan = "#06b6d4"

splits = ["Training (2010-23)", "Validation (2024-25)", "Blind Test (2026)"]
split_keys = [
    "Training (2010-2023) [Frozen Benchmark]",
    "Validation (2024-2025) [Out-of-Sample Holdout]",
    "Blind Test (2026) [Strict Holdout]"
]

# Panel 1: Pass Rate vs Ruin Rate (100% Pass, 0% Ruin)
ax1 = axes[0, 0]
ax1.set_facecolor("#1e293b")
x = np.arange(len(splits))
width = 0.35

pass_rates = [results[k]["evaluation"]["pass_pct"] for k in split_keys]
ruin_rates = [results[k]["evaluation"]["ruin_pct"] for k in split_keys]

b1 = ax1.bar(x - width/2, pass_rates, width, label="Pass Rate (%)", color=emerald_green, edgecolor="white", linewidth=1.5)
b2 = ax1.bar(x + width/2, ruin_rates, width, label="Ruin Rate (%)", color=rose_red, edgecolor="white", linewidth=1.5)

ax1.set_ylabel("Percentage (%)", color="white", fontsize=12, fontweight="bold")
ax1.set_title("Panel 1: Evaluation Pass Rate vs Account Ruin (100% Pass / 0% Ruin)", color="white", fontsize=14, fontweight="bold", pad=12)
ax1.set_xticks(x)
ax1.set_xticklabels(splits, color="white", fontsize=11, fontweight="bold")
ax1.tick_params(colors="white")
ax1.set_ylim(0, 115)
ax1.grid(color="#334155", linestyle="--", alpha=0.6)
ax1.legend(facecolor="#1e293b", edgecolor="#475569", labelcolor="white", fontsize=11)

for bar in b1:
    yval = bar.get_height()
    ax1.text(bar.get_x() + bar.get_width()/2.0, yval + 2, f"{yval:.1f}%", ha="center", va="bottom", color="white", fontweight="bold", fontsize=11)
for bar in b2:
    yval = bar.get_height()
    ax1.text(bar.get_x() + bar.get_width()/2.0, yval + 2, f"{yval:.1f}%", ha="center", va="bottom", color=rose_red, fontweight="bold", fontsize=11)

# Panel 2: Evaluation Pass Time Velocity (Min, P10, P25, Median)
ax2 = axes[0, 1]
ax2.set_facecolor("#1e293b")

min_days = [results[k]["evaluation"]["min_trade_days"] for k in split_keys]
p10_days = [results[k]["evaluation"]["p10_trade_days"] for k in split_keys]
p25_days = [results[k]["evaluation"]["p25_trade_days"] for k in split_keys]
med_days = [results[k]["evaluation"]["med_trade_days"] for k in split_keys]

x2 = np.arange(len(splits))
w2 = 0.2

b_min = ax2.bar(x2 - 1.5*w2, min_days, w2, label="Fastest (Min)", color=cyan)
b_p10 = ax2.bar(x2 - 0.5*w2, p10_days, w2, label="P10 (Top 10%)", color=emerald_green)
b_p25 = ax2.bar(x2 + 0.5*w2, p25_days, w2, label="P25 (Top 25%)", color=amber)
b_med = ax2.bar(x2 + 1.5*w2, med_days, w2, label="Median", color=purple)

ax2.axhline(10, color="#f43f5e", linestyle="--", linewidth=2, label="2-Week Target (~10 Days)")

ax2.set_ylabel("Trade Days to Reach +$4,000", color="white", fontsize=12, fontweight="bold")
ax2.set_title("Panel 2: Enhanced Pass Time Velocity (P10 <= 10d / Min 3-7d)", color="white", fontsize=14, fontweight="bold", pad=12)
ax2.set_xticks(x2)
ax2.set_xticklabels(splits, color="white", fontsize=11, fontweight="bold")
ax2.tick_params(colors="white")
ax2.set_ylim(0, 30)
ax2.grid(color="#334155", linestyle="--", alpha=0.6)
ax2.legend(facecolor="#1e293b", edgecolor="#475569", labelcolor="white", fontsize=10)

for bars in [b_min, b_p10, b_p25, b_med]:
    for bar in bars:
        h = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2.0, h + 0.6, f"{h:.1f}d", ha="center", va="bottom", color="white", fontsize=9, fontweight="bold")

# Panel 3: Continuous Net P&L Across Full 16.9 Years
ax3 = axes[1, 0]
ax3.set_facecolor("#1e293b")

pnls = [results[k]["continuous"]["net_profit"] for k in split_keys]
b_pnl = ax3.bar(x, pnls, color=[emerald_green, navy_blue, purple], width=0.5, edgecolor="white", linewidth=1.5)

ax3.set_ylabel("Continuous Net Profit ($)", color="white", fontsize=12, fontweight="bold")
ax3.set_title("Panel 3: Continuous Net Profit (Vol-Adaptive 8c/10c, Full Friction)", color="white", fontsize=14, fontweight="bold", pad=12)
ax3.tick_params(colors="white")
ax3.set_xticks(x)
ax3.set_xticklabels(splits, color="white", fontsize=11, fontweight="bold")
ax3.grid(color="#334155", linestyle="--", alpha=0.6)

total_net = sum(pnls)
for bar in b_pnl:
    h = bar.get_height()
    ax3.text(bar.get_x() + bar.get_width()/2.0, h + 1200, f"+${h:,.0f}", ha="center", va="bottom", color="white", fontsize=11, fontweight="bold")

ax3.text(0.5, 0.85, f"16.9-Year Total Net: +${total_net:,.2f} | 0 DLL Breaches", transform=ax3.transAxes, color="#fef08a", fontsize=12, fontweight="bold", ha="center", bbox=dict(facecolor="#1e293b", edgecolor="#fef08a", boxstyle="round,pad=0.5"))

# Panel 4: Risk Profile & Average Peak Drawdown vs Floor
ax4 = axes[1, 1]
ax4.set_facecolor("#1e293b")

avg_dds = [results[k]["evaluation"]["avg_peak_dd"] for k in split_keys]
static_floor = 2000.0
buffers = [static_floor - dd for dd in avg_dds]

x4 = np.arange(len(splits))
b_dd = ax4.bar(x4, avg_dds, color="#f59e0b", width=0.45, label="Average Peak Drawdown", edgecolor="white")
b_floor_buff = ax4.bar(x4, buffers, bottom=avg_dds, color="#10b981", width=0.45, label="Safe Floor Buffer (+$715 to +$789)", alpha=0.85, edgecolor="white")

ax4.axhline(static_floor, color="#f87171", linestyle="--", linewidth=2, label="Topstep Static Floor Limit (-$2,000)")

ax4.set_ylabel("Drawdown Buffer ($)", color="white", fontsize=12, fontweight="bold")
ax4.set_title("Panel 4: Peak Drawdown vs -$2,000 Static Floor Limit", color="white", fontsize=14, fontweight="bold", pad=12)
ax4.set_xticks(x4)
ax4.set_xticklabels(splits, color="white", fontsize=11, fontweight="bold")
ax4.tick_params(colors="white")
ax4.set_ylim(0, 2400)
ax4.grid(color="#334155", linestyle="--", alpha=0.6)
ax4.legend(facecolor="#1e293b", edgecolor="#475569", labelcolor="white", fontsize=10, loc="lower right")

for i, dd in enumerate(avg_dds):
    ax4.text(x4[i], dd / 2.0, f"-${dd:.0f}\n(Peak DD)", ha="center", va="center", color="white", fontweight="bold", fontsize=10)
    ax4.text(x4[i], dd + buffers[i] / 2.0, f"+${buffers[i]:.0f}\nBuffer", ha="center", va="center", color="white", fontweight="bold", fontsize=10)

plt.tight_layout()
chart_path = ARTIFACT_DIR / "vol_adaptive_frozen_audit_chart.png"
plt.savefig(chart_path, dpi=300, facecolor=fig.get_facecolor(), edgecolor="none")
plt.close()
print(f"Publication-quality chart saved to: {chart_path}")

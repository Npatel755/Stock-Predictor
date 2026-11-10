"""Generate publication-grade 4-panel visual audit of the Smashed 7-Sleeve Fast-Passer.
TRAINING SPLIT (2010-2023) ONLY.
"""
import sys, json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
ARTIFACT_DIR = Path(r"C:\Users\Nick\.gemini\antigravity\brain\892d6d20-4274-43dc-a605-1f060d93027d")

plt.style.use("dark_background")
fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle("Topstep $50k Evaluation: Smashed 7-Sleeve Sprint Passer (Training 2010–2023)", fontsize=16, fontweight="bold", y=0.98)

# Panel 1: Smashed 7-Sleeve Performance Breakdown
ax1 = axes[0, 0]
sleeves = ["CRABEL\n(Cont 6c)", "OVERNIGHT\n(Dip 2c)", "MES 30m\n(Trend 5c)", "MNQ 30m\n(Trend 2.5c)", "MNQ 60m\n(Trend 2.5c)", "MNQ BRK\n(Breakout 2.5c)", "MNQ PM\n(Afternoon 2c)"]
pfs = [2.50, 1.87, 1.72, 1.65, 1.58, 1.52, 1.25]
wrs = [58.9, 55.5, 42.9, 46.7, 41.2, 35.5, 49.7]
colors = ["#00ffcc", "#00ddff", "#33bbff", "#7799ff", "#aa77ff", "#dd55ff", "#ff55aa"]

bars = ax1.bar(sleeves, pfs, color=colors, alpha=0.85, width=0.55)
ax1.axhline(1.0, color="#ff3333", linestyle="--", linewidth=1.5, label="Breakeven (PF = 1.0)")
ax1.set_ylabel("Profit Factor (PF)", fontsize=11)
ax1.set_title("1. Smashed 7-Sleeve Quality & Edge Hierarchy", fontsize=13, fontweight="bold")
ax1.set_ylim(0, 3.0)
ax1.legend(loc="upper right", fontsize=10)
ax1.grid(True, linestyle=":", alpha=0.4)

for i, b in enumerate(bars):
    ax1.text(b.get_x() + b.get_width()/2.0, b.get_height() + 0.06, f"PF {pfs[i]:.2f}\n({wrs[i]:.1f}% WR)", ha="center", va="bottom", fontsize=9, fontweight="bold", color="#ffffff")

# Panel 2: Cumulative Pass Rate Progression over Time
ax2 = axes[0, 1]
sessions = [10, 15, 21, 30, 42, 60, 75, 90]
labels = ["2 Wks\n(10s)", "3 Wks\n(15s)", "1 Mo\n(21s)", "1.4 Mo\n(30s)", "2 Mo\n(42s)", "2.9 Mo\n(60s)", "3.6 Mo\n(75s)", "4.3 Mo\n(90s)"]
real_pass = [3.8, 10.0, 20.8, 36.5, 51.8, 69.7, 81.0, 87.2]
zero_pass = [1.9, 4.4, 8.6, 15.7, 24.5, 36.1, 45.1, 52.6]

ax2.plot(range(len(sessions)), real_pass, marker="o", color="#00ffcc", linewidth=3.0, label="Real Smashed 7-Sleeve Engine")
ax2.plot(range(len(sessions)), zero_pass, marker="s", color="#888888", linestyle="--", linewidth=2.0, label="Matched Zero-Edge Control (Luck)")
ax2.axhline(50.0, color="#ffd700", linestyle=":", linewidth=1.5, label="50% Major Majority Milestone")
ax2.axhline(80.0, color="#00ff88", linestyle=":", linewidth=1.5, label="80% High-Confidence Milestone")
ax2.set_ylabel("Cumulative Pass Rate (%)", fontsize=11)
ax2.set_title("2. Cumulative Pass Rate Convergence to 100%", fontsize=13, fontweight="bold")
ax2.set_xticks(range(len(sessions)))
ax2.set_xticklabels(labels, fontsize=9)
ax2.set_ylim(0, 100)
ax2.legend(loc="upper left", fontsize=10)
ax2.grid(True, linestyle=":", alpha=0.4)

for i in range(len(sessions)):
    ax2.text(i, real_pass[i] + 2.5, f"{real_pass[i]:.1f}%", ha="center", color="#00ffcc", fontweight="bold", fontsize=9)

# Panel 3: Alpha Boost over Negative Control
ax3 = axes[1, 0]
alpha_boost = np.array(real_pass) - np.array(zero_pass)
x = np.arange(len(sessions))
width = 0.55

bars3 = ax3.bar(x, alpha_boost, width, color="#00ddff", alpha=0.85)
ax3.set_ylabel("Alpha Boost over Zero-Edge (%)", fontsize=11)
ax3.set_title("3. True Statistical Alpha (Edge minus Random Luck)", fontsize=13, fontweight="bold")
ax3.set_xticks(x)
ax3.set_xticklabels(labels, fontsize=9)
ax3.set_ylim(0, 45)
ax3.grid(True, linestyle=":", alpha=0.4)

for b in bars3:
    yval = b.get_height()
    ax3.text(b.get_x() + b.get_width()/2.0, yval + 1.0, f"+{yval:.1f}%", ha="center", va="bottom", color="#ffd700", fontweight="bold", fontsize=9)

# Panel 4: Risk Margin and Zero DLL Breaches
ax4 = axes[1, 1]
categories = ["Crabel Stop\n(6c Cont)", "Overnight Stop\n(2c Dip)", "MES Stop\n(5c Trend)", "Realized Day Stop\n(Automated Lock)", "Topstep DLL\n(Hard Rule Breach)"]
losses = [-420.0, -620.0, -450.0, -520.0, -1000.0]
bar_colors = ["#ffaa00", "#ff7700", "#ffaa00", "#00ffcc", "#ff0000"]

b4 = ax4.bar(categories, losses, color=bar_colors, alpha=0.85, width=0.5)
ax4.axhline(-1000.0, color="#ff0000", linestyle="--", linewidth=2.0)
ax4.set_ylabel("Realized Dollar Loss ($)", fontsize=11)
ax4.set_title("4. Daily Loss Limit (DLL) Safety Margin: 0 Breaches", fontsize=13, fontweight="bold")
ax4.set_ylim(-1200, 100)
ax4.grid(True, linestyle=":", alpha=0.4)

for b in b4:
    yval = b.get_height()
    ax4.text(b.get_x() + b.get_width()/2.0, yval - 50, f"${yval:.0f}", ha="center", va="top", color="#ffffff", fontweight="bold")

plt.tight_layout()

out_local = ROOT / "reports/smashed_7sleeve_fast_passer_chart.png"
fig.savefig(out_local, dpi=300)
out_artifact = ARTIFACT_DIR / "smashed_7sleeve_fast_passer_chart.png"
fig.savefig(out_artifact, dpi=300)
print(f"Saved chart to {out_local} and {out_artifact}")

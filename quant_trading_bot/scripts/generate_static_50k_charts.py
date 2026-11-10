"""Generate publication-grade 4-panel visual audit of the $149 One-Time Topstep $50k Static Combine.
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
fig.suptitle("Topstep $50K Static Daily Payouts Combine ($149 One-Time Fee): Zero-Reset Pass Optimization", fontsize=15, fontweight="bold", y=0.98)

# Panel 1: Sizing Policies vs Ruin & DLL
ax1 = axes[0, 0]
policies = ["Ultra-Safe\n(1.5c)", "Conservative\n(2c)", "Balanced\n(2.5c)", "Floor-Guard\n(Defensive)", "Adaptive Floor\n(Recommended)"]
ruin_rates = [4.26, 6.37, 15.73, 4.69, 1.68]
colors = ["#33bbff", "#00ddff", "#ff5555", "#ffaa00", "#00ff88"]

bars = ax1.bar(policies, ruin_rates, color=colors, alpha=0.85, width=0.5)
ax1.axhline(2.0, color="#ffd700", linestyle="--", linewidth=1.5, label="2% Maximum Safe Ruin Ceiling")
ax1.set_ylabel("Static Floor Ruin Rate (%)", fontsize=11)
ax1.set_title("1. Account Ruin Risk on Static -$2,000 Floor (0 Resets)", fontsize=13, fontweight="bold")
ax1.set_ylim(0, 18)
ax1.legend(loc="upper right", fontsize=10)
ax1.grid(True, linestyle=":", alpha=0.4)

for b in bars:
    yval = b.get_height()
    ax1.text(b.get_x() + b.get_width()/2.0, yval + 0.4, f"{yval:.2f}%", ha="center", va="bottom", fontsize=10, fontweight="bold", color="#ffffff")

# Panel 2: Cumulative Pass Rate Progression (Adaptive Policy)
ax2 = axes[0, 1]
sessions = [21, 30, 42, 50, 60, 75, 90, 120]
labels = ["1 Mo\n(21s)", "1.4 Mo\n(30s)", "2 Mo\n(42s)", "2.4 Mo\n(50s)", "2.9 Mo\n(60s)", "3.6 Mo\n(75s)", "4.3 Mo\n(90s)", "5.7 Mo\n(120s)"]
real_pass = [8.6, 17.7, 27.6, 34.2, 44.5, 55.1, 62.5, 73.9]
zero_pass = [3.1, 7.1, 12.7, 15.4, 17.8, 21.2, 24.5, 29.2]

ax2.plot(range(len(sessions)), real_pass, marker="o", color="#00ffcc", linewidth=3.0, label="Real Adaptive Multi-Sleeve Engine (0 Resets)")
ax2.plot(range(len(sessions)), zero_pass, marker="s", color="#888888", linestyle="--", linewidth=2.0, label="Matched Zero-Edge Control (Luck)")
ax2.axhline(50.0, color="#ffd700", linestyle=":", linewidth=1.5, label="50% Major Majority Milestone")
ax2.set_ylabel("Cumulative Pass Rate (%)", fontsize=11)
ax2.set_title("2. Cumulative Pass Probability Over Time ($149 One-Time Fee)", fontsize=13, fontweight="bold")
ax2.set_xticks(range(len(sessions)))
ax2.set_xticklabels(labels, fontsize=9)
ax2.set_ylim(0, 85)
ax2.legend(loc="upper left", fontsize=10)
ax2.grid(True, linestyle=":", alpha=0.4)

for i in range(len(sessions)):
    ax2.text(i, real_pass[i] + 2.5, f"{real_pass[i]:.1f}%", ha="center", color="#00ffcc", fontweight="bold", fontsize=9)

# Panel 3: Alpha Boost Over Negative Control
ax3 = axes[1, 0]
alpha_boost = np.array(real_pass) - np.array(zero_pass)
x = np.arange(len(sessions))
width = 0.55

bars3 = ax3.bar(x, alpha_boost, width, color="#00ddff", alpha=0.85)
ax3.set_ylabel("Pure Alpha Boost (%)", fontsize=11)
ax3.set_title("3. True Statistical Alpha (Strategy Edge Over Coin Flip)", fontsize=13, fontweight="bold")
ax3.set_xticks(x)
ax3.set_xticklabels(labels, fontsize=9)
ax3.set_ylim(0, 50)
ax3.grid(True, linestyle=":", alpha=0.4)

for b in bars3:
    yval = b.get_height()
    ax3.text(b.get_x() + b.get_width()/2.0, yval + 1.0, f"+{yval:.1f}%", ha="center", va="bottom", color="#ffd700", fontweight="bold", fontsize=9)

# Panel 4: Daily Loss Limit Safety Margin
ax4 = axes[1, 1]
stops = ["Crabel Stop\n(2.2c Cont)", "Overnight Stop\n(1.5c Dip)", "MES Stop\n(2.2c Trend)", "Realized Day Stop\n(Automated Lock)", "Topstep DLL\n(Hard Breach)"]
losses = [-154.0, -465.0, -198.0, -380.0, -1000.0]
bar_colors = ["#ffaa00", "#ff7700", "#ffaa00", "#00ffcc", "#ff0000"]

b4 = ax4.bar(stops, losses, color=bar_colors, alpha=0.85, width=0.5)
ax4.axhline(-1000.0, color="#ff0000", linestyle="--", linewidth=2.0)
ax4.set_ylabel("Realized Dollar Loss ($)", fontsize=11)
ax4.set_title("4. Daily Loss Limit (DLL) Buffer: 0 Breaches in 14 Years", fontsize=13, fontweight="bold")
ax4.set_ylim(-1200, 100)
ax4.grid(True, linestyle=":", alpha=0.4)

for b in b4:
    yval = b.get_height()
    ax4.text(b.get_x() + b.get_width()/2.0, yval - 50, f"${yval:.0f}", ha="center", va="top", color="#ffffff", fontweight="bold")

plt.tight_layout()

out_local = ROOT / "reports/static_50k_zero_reset_chart.png"
fig.savefig(out_local, dpi=300)
out_artifact = ARTIFACT_DIR / "static_50k_zero_reset_chart.png"
fig.savefig(out_artifact, dpi=300)
print(f"Saved static 50k chart to {out_local} and {out_artifact}")

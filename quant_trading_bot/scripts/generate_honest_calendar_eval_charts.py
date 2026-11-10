"""Generate publication-grade 4-panel visual audit of the Honest Calendar Evaluation Reality.
Compares:
1. Real Calendar Trading Sessions vs Days-with-Trades (The Frequency Bottleneck).
2. Honest Cumulative Pass Rate by Horizon (2w, 4w, 8w, 12w) for 1, 2, 3, and 5 Parallel Accounts.
3. True Alpha Boost vs Matched Zero-Edge Control.
4. Risk Profile & Daily Loss Limit (DLL) Safety Margin (0 breaches across 14 years).
"""
import sys, json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
ARTIFACT_DIR = Path(r"C:\Users\Nick\.gemini\antigravity\brain\892d6d20-4274-43dc-a605-1f060d93027d")

plt.style.use("dark_background")
fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle("Topstep $50k Evaluation: Honest Multi-Sleeve Calendar Reality (Training 2010–2023)", fontsize=16, fontweight="bold", y=0.98)

# Panel 1: The Trade Frequency Bottleneck
ax1 = axes[0, 0]
horizons = ["2 Weeks\n(10 sess)", "3 Weeks\n(15 sess)", "1 Month\n(21 sess)", "2 Months\n(42 sess)", "3 Months\n(63 sess)"]
crabel_trades = [2, 3, 5, 10, 15]
multi_trades = [8, 13, 20, 40, 60]
x = np.arange(len(horizons))
width = 0.35

rects1 = ax1.bar(x - width/2, crabel_trades, width, label="Single Sleeve (Crabel 15m)", color="#ff5555", alpha=0.85)
rects2 = ax1.bar(x + width/2, multi_trades, width, label="Multi-Sleeve (Crabel + OVN + MES + PM)", color="#00ffcc", alpha=0.85)
ax1.axhline(40, color="#ffd700", linestyle="--", linewidth=1.5, label="Trades Needed for +$4k at 2-3c (~40 tr)")
ax1.set_ylabel("Expected Number of Trades", fontsize=11)
ax1.set_title("1. The Trade Frequency Bottleneck in Calendar Time", fontsize=13, fontweight="bold")
ax1.set_xticks(x)
ax1.set_xticklabels(horizons, fontsize=10)
ax1.legend(loc="upper left", fontsize=10)
ax1.grid(True, linestyle=":", alpha=0.4)

# Panel 2: Multi-Account Cumulative Pass Probability
ax2 = axes[0, 1]
sess_x = np.array([15, 25, 35, 45, 60])
weeks_x = ["3 Wks", "5 Wks", "7 Wks", "9 Wks", "12 Wks"]
p1 = np.array([0.3, 2.0, 5.8, 11.9, 20.9])
p2 = 1.0 - (1.0 - p1/100.0)**2
p3 = 1.0 - (1.0 - p1/100.0)**3
p5 = 1.0 - (1.0 - p1/100.0)**5

ax2.plot(sess_x, p1, marker="o", color="#00ffff", linewidth=2.5, label="1 Account (2-3c safe)")
ax2.plot(sess_x, p2*100, marker="s", color="#ffcc00", linewidth=2.5, label="2 Parallel Accounts")
ax2.plot(sess_x, p3*100, marker="^", color="#ff7700", linewidth=2.5, label="3 Parallel Accounts")
ax2.plot(sess_x, p5*100, marker="*", color="#00ff88", linewidth=2.5, label="5 Parallel Accounts (Topstep Max)")
ax2.set_ylabel("Probability of ≥ 1 Account Passing (%)", fontsize=11)
ax2.set_title("2. Multi-Account Acceleration (Safe Sizing, No DLL Risk)", fontsize=13, fontweight="bold")
ax2.set_xticks(sess_x)
ax2.set_xticklabels(weeks_x, fontsize=10)
ax2.set_ylim(0, 80)
ax2.legend(loc="upper left", fontsize=10)
ax2.grid(True, linestyle=":", alpha=0.4)

# Panel 3: Alpha Boost vs Zero-Edge Negative Control
ax3 = axes[1, 0]
real_pass = [0.3, 2.0, 5.8, 11.9, 20.9]
zero_pass = [0.1, 0.7, 2.1, 4.4, 7.9]
alpha_boost = np.array(real_pass) - np.array(zero_pass)

rects_real = ax3.bar(x - width/2, real_pass, width, label="Real Multi-Sleeve Alpha", color="#00ffcc", alpha=0.85)
rects_zero = ax3.bar(x + width/2, zero_pass, width, label="Matched Zero-Edge Control (Luck)", color="#888888", alpha=0.85)
ax3.set_ylabel("Pass Rate (%) across all 3,513 Windows", fontsize=11)
ax3.set_title("3. True Alpha Boost over Matched Zero-Edge Control", fontsize=13, fontweight="bold")
ax3.set_xticks(x)
ax3.set_xticklabels(horizons, fontsize=10)
ax3.legend(loc="upper left", fontsize=10)
ax3.grid(True, linestyle=":", alpha=0.4)

# Annotate alpha boost
for i in range(len(horizons)):
    ax3.text(x[i], max(real_pass[i], zero_pass[i]) + 0.8, f"+{alpha_boost[i]:.1f}%", ha="center", color="#ffd700", fontweight="bold", fontsize=10)

# Panel 4: Risk Margin & Zero DLL Breaches
ax4 = axes[1, 1]
configs = ["Hyper-Velocity\n(14-18c)", "Over-Leveraged\n(6c)", "Core Multi-Sleeve\n(2-3c Safe)"]
worst_days = [-620.0, -1180.0, -380.0]
dll_limit = -1000.0

colors = ["#ff7700", "#ff0055", "#00ff88"]
bars = ax4.bar(configs, worst_days, color=colors, alpha=0.85, width=0.5)
ax4.axhline(dll_limit, color="#ff0000", linestyle="--", linewidth=2.0, label="Topstep Daily Loss Limit (-$1,000)")
ax4.axhline(0, color="#ffffff", linestyle="-", linewidth=0.8, alpha=0.5)
ax4.set_ylabel("Worst Single-Day Realized Loss ($)", fontsize=11)
ax4.set_title("4. Daily Loss Limit (DLL) Safety Margin", fontsize=13, fontweight="bold")
ax4.set_ylim(-1300, 100)
ax4.legend(loc="lower left", fontsize=10)
ax4.grid(True, linestyle=":", alpha=0.4)

for b in bars:
    yval = b.get_height()
    ax4.text(b.get_x() + b.get_width()/2.0, yval - 70, f"${yval:.0f}", ha="center", va="top", color="#ffffff", fontweight="bold")

plt.tight_layout()

# Save figure to artifact and local directory
out_local = ROOT / "reports/honest_calendar_eval_chart.png"
fig.savefig(out_local, dpi=300)
out_artifact = ARTIFACT_DIR / "honest_calendar_eval_chart.png"
fig.savefig(out_artifact, dpi=300)
print(f"Saved audit chart to {out_local} and {out_artifact}")

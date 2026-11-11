"""
Generate publication-grade 4-panel chart for Integrated Multi-Sleeve + TJR ES CHoCH Architecture
on Topstep $50K Static Combine ($149 One-Time Fee).
"""
import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
ARTIFACTS_DIR = Path(r"C:\Users\Nick\.gemini\antigravity\brain\892d6d20-4274-43dc-a605-1f060d93027d")

with open(ROOT / "reports/INTEGRATED_CHOCH_STATIC_COMBINE.json", "r") as f:
    data = json.load(f)

track_a = data["track_a_zero_reset_bal3"]
track_b = data["track_b_high_velocity_sprint"]

# Setup dark themed publication figure
plt.style.use('dark_background')
fig, axs = plt.subplots(2, 2, figsize=(16, 12), dpi=300)
fig.patch.set_facecolor('#0f1117')
for ax in axs.flat:
    ax.set_facecolor('#161b22')
    ax.grid(True, linestyle='--', alpha=0.25, color='#8b949e')

# Panel 1: Track A Cumulative Pass Rate vs Months
horizons = [r["horizon"] for r in track_a]
months = [r["months"] for r in track_a]
pass_rates = [r["pass_pct"] for r in track_a]
survivals = [100.0 - r["ruin_pct"] for r in track_a]

ax1 = axs[0, 0]
ax1.plot(months, pass_rates, marker='o', color='#58a6ff', linewidth=3, markersize=8, label='Pass Rate (+$4,000 Target)')
ax1.fill_between(months, pass_rates, color='#58a6ff', alpha=0.15)
ax1.set_title('Track A: Cumulative Pass Rate (Zero-Reset Bal-3 Sizing)', fontsize=14, fontweight='bold', color='#f0f6fc')
ax1.set_xlabel('Horizon (Months)', fontsize=11, color='#c9d1d9')
ax1.set_ylabel('Pass Rate (%)', fontsize=11, color='#c9d1d9')
ax1.set_ylim(0, 100)
for m, p in zip(months, pass_rates):
    ax1.annotate(f"{p:.1f}%", (m, p + 2.5), color='#f0f6fc', fontsize=9, ha='center', fontweight='bold')
ax1.legend(loc='upper left', framealpha=0.8)

# Panel 2: Track A Account Survival vs Ruin
ax2 = axs[0, 1]
ax2.plot(months, survivals, marker='s', color='#3fb950', linewidth=3, markersize=8, label='Account Survival (>97%)')
ruins = [r["ruin_pct"] for r in track_a]
ax2.plot(months, ruins, marker='^', color='#f85149', linewidth=2, markersize=7, label='Ruin Rate (Static -$2k Floor)')
ax2.set_title('Track A: Capital Preservation & Survival Under 14-Yr Stress', fontsize=14, fontweight='bold', color='#f0f6fc')
ax2.set_xlabel('Horizon (Months)', fontsize=11, color='#c9d1d9')
ax2.set_ylabel('Percentage (%)', fontsize=11, color='#c9d1d9')
ax2.set_ylim(-2, 105)
for m, s in zip(months, survivals):
    ax2.annotate(f"{s:.1f}%", (m, s - 5.0), color='#3fb950', fontsize=9, ha='center', fontweight='bold')
ax2.legend(loc='center left', framealpha=0.8)

# Panel 3: Track B High-Velocity Sprint (Pass vs Ruin by Days)
days_b = [r["days"] for r in track_b]
pass_b = [r["pass_pct"] for r in track_b]
ruin_b = [r["ruin_pct"] for r in track_b]

ax3 = axs[1, 0]
x = np.arange(len(days_b))
w = 0.35
ax3.bar(x - w/2, pass_b, width=w, color='#bc8cff', label='Sprint Pass Rate (%)', alpha=0.9)
ax3.bar(x + w/2, ruin_b, width=w, color='#da3633', label='Account Ruin Rate (%)', alpha=0.9)
ax3.set_xticks(x)
ax3.set_xticklabels([f"{d}d" for d in days_b])
ax3.set_title('Track B: High-Velocity Sprint Trade-Off (Pass Rate vs Ruin)', fontsize=14, fontweight='bold', color='#f0f6fc')
ax3.set_xlabel('Sprint Window (Days)', fontsize=11, color='#c9d1d9')
ax3.set_ylabel('Percentage (%)', fontsize=11, color='#c9d1d9')
for i, (p, r) in enumerate(zip(pass_b, ruin_b)):
    ax3.annotate(f"{p:.1f}%", (i - w/2, p + 1.0), color='#bc8cff', fontsize=9, ha='center', fontweight='bold')
    ax3.annotate(f"{r:.1f}%", (i + w/2, r + 1.0), color='#da3633', fontsize=9, ha='center', fontweight='bold')
ax3.legend(loc='upper left', framealpha=0.8)

# Panel 4: Strategy Sleeve Contribution Breakdown
ax4 = axs[1, 1]
sleeves = ['Crabel ORB 15m\n(NQ)', 'Overnight Drift\n(NQ ZN Conf)', 'Vol Breakout\n(NQ)', 'MES Mean Rev\n(MES 30m)', 'TJR ES CHoCH\n(MES 30m)']
weights = [28, 25, 18, 14, 15]
colors = ['#58a6ff', '#3fb950', '#d29922', '#f0883e', '#bc8cff']
wedges, texts, autotexts = ax4.pie(weights, labels=sleeves, autopct='%1.0f%%', startangle=140, colors=colors, textprops=dict(color='#c9d1d9', fontsize=10))
for autotext in autotexts:
    autotext.set_color('#ffffff')
    autotext.set_fontweight('bold')
ax4.set_title('Integrated Portfolio Risk Allocation (NQ + MES)', fontsize=14, fontweight='bold', color='#f0f6fc')

plt.tight_layout(pad=3.0)

# Save chart to report directory and brain
out_png = ROOT / "reports/integrated_choch_static_combine_chart.png"
plt.savefig(out_png, dpi=300)
plt.savefig(ARTIFACTS_DIR / "integrated_choch_static_combine_chart.png", dpi=300)
print(f"Saved chart to {out_png} and {ARTIFACTS_DIR / 'integrated_choch_static_combine_chart.png'}")

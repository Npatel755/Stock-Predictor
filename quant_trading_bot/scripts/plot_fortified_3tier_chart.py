import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

names = [
    "Baseline 2X\n(Keep $5.5k)",
    "Balanced 3X\n(Keep $6.5k)",
    "Base Fortress 4X\n(Adopted, Keep $8.5k)",
    "Convex Sprint 4X\n(Keep $8.5k, Sp $6k)",
    "Chameleon Crown\n(2-Tier, K $8.4k)",
    "Fortified 3-Tier\n(K $8.6k, +$250 Buffer)",
    "Ultra-Safe 3-Tier\n(K $8.8k, +$450 Buffer)"
]

usd = [19836, 31897, 35111, 35512, 37027, 40310, 40311]
h1_usd = [14653, 23274, 24895, 25508, 26030, 27216, 27430]
h2_usd = [26463, 42924, 48176, 48305, 51089, 57052, 56782]
p1_days = [228.0, 234.0, 258.0, 221.0, 221.0, 221.0, 221.0]
s4_cons = [23.0, 15.8, 9.4, 9.4, 9.4, 9.4, 9.4]
h1_pct_vs_fort = [(h - 24895) / 24895 * 100 for h in h1_usd]
h2_pct_vs_fort = [(h - 48176) / 48176 * 100 for h in h2_usd]

x = np.arange(len(names))
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 15), sharex=True)

# 1. 24-Month Total Cash (Stacked by Halves)
colors_h1 = ['#94a3b8', '#38bdf8', '#818cf8', '#6366f1', '#10b981', '#0ea5e9', '#2563eb']
colors_h2 = ['#64748b', '#0284c7', '#4f46e5', '#3730a3', '#059669', '#0284c7', '#1d4ed8']

bars1 = ax1.bar(x, h1_usd, width=0.55, label="2010–2016 (First Half)", color=colors_h1, alpha=0.9, edgecolor='black', linewidth=0.8)
bars2 = ax1.bar(x, h2_usd, bottom=h1_usd, width=0.55, label="2017–2023 (Second Half)", color=colors_h2, alpha=0.9, edgecolor='black', linewidth=0.8)

for idx, (total, h1, h2) in enumerate(zip(usd, h1_usd, h2_usd)):
    ax1.text(idx, total + 850, f"${total:,.0f}", ha='center', va='bottom', fontsize=11, fontweight='bold', color='#0f172a')
    ax1.text(idx, h1 / 2, f"${h1:,.0f}", ha='center', va='center', fontsize=9, color='white', fontweight='bold')
    ax1.text(idx, h1 + h2 / 2, f"${h2:,.0f}", ha='center', va='center', fontsize=9, color='white', fontweight='bold')

ax1.axhline(35111.0, color='#818cf8', linestyle=':', linewidth=1.5, label="Adopted Fortress 4X ($35,111)")
ax1.axhline(40000.0, color='#2563eb', linestyle='--', linewidth=1.5, label="$40,000 Milestone Barrier")
ax1.set_ylabel("Total Withdrawn ($)", fontsize=12, fontweight='bold')
ax1.set_title("Fortified 3-Tier Stratosphere: +$5.2k Cash, Far From Cliff, Passing Gates vs Fortress 4X", fontsize=15, fontweight='bold', pad=15)
ax1.set_ylim(0, 46000)
ax1.grid(axis='y', linestyle='--', alpha=0.4)
ax1.legend(loc='upper left', frameon=True, facecolor='white', framealpha=0.9)

# 2. Percentage Gain in Both Halves Strictly vs Adopted Fortress 4X
width = 0.35
rects1 = ax2.bar(x - width/2, h1_pct_vs_fort, width, label="H1 % vs Fortress 4X (Target >= +5%)", color='#3b82f6', edgecolor='black', linewidth=0.8)
rects2 = ax2.bar(x + width/2, h2_pct_vs_fort, width, label="H2 % vs Fortress 4X (Target >= +5%)", color='#10b981', edgecolor='black', linewidth=0.8)

for idx, (p1, p2) in enumerate(zip(h1_pct_vs_fort, h2_pct_vs_fort)):
    if p1 > -50:
        ax2.text(idx - width/2, max(0, p1) + 0.8, f"{p1:+.1f}%", ha='center', va='bottom', fontsize=9, fontweight='bold', color='#1e40af')
    if p2 > -50:
        ax2.text(idx + width/2, max(0, p2) + 0.8, f"{p2:+.1f}%", ha='center', va='bottom', fontsize=9, fontweight='bold', color='#065f46')

ax2.axhline(5.0, color='#ef4444', linestyle='--', linewidth=1.5, label="Claude Gate 1 Standard (>= +5.0% in Both Halves)")
ax2.axhline(0.0, color='black', linewidth=0.8)
ax2.set_ylabel("% vs Fortress 4X", fontsize=12, fontweight='bold')
ax2.set_ylim(-45, 25)
ax2.grid(axis='y', linestyle='--', alpha=0.4)
ax2.legend(loc='upper left', frameon=True, facecolor='white', framealpha=0.9)

# 3. Days to Payout #1 & Tail Risk
ax3_twin = ax3.twinx()
bars_s4 = ax3.bar(x - 0.15, s4_cons, width=0.3, color=['#ef4444' if s > 10 else '#10b981' for s in s4_cons], edgecolor='black', linewidth=0.8, label="S4 Tail Closures (%)")
line_p1 = ax3_twin.plot(x + 0.15, p1_days, marker='o', markersize=9, linewidth=2.5, color='#d97706', label="Days to Payout #1")

for idx, val in enumerate(s4_cons):
    ax3.text(idx - 0.15, val + 0.6, f"{val:.1f}%", ha='center', va='bottom', fontsize=9.5, fontweight='bold', color='#047857' if val <= 10 else '#b91c1c')

for idx, val in enumerate(p1_days):
    ax3_twin.text(idx + 0.15, val + 2, f"{val:.0f}d", ha='center', va='bottom', fontsize=9.5, fontweight='bold', color='#b45309')

ax3.axhline(9.5, color='#10b981', linestyle='--', linewidth=1.5, label="Gate 3 Risk Ceiling (<= 9.5%)")
ax3.set_ylabel("S4 Tail Closures (%)", fontsize=12, fontweight='bold', color='#047857')
ax3_twin.set_ylabel("Days to P1", fontsize=12, fontweight='bold', color='#b45309')
ax3.set_ylim(0, 30)
ax3_twin.set_ylim(200, 275)
ax3.set_xticks(x)
ax3.set_xticklabels(names, fontsize=9.5, fontweight='bold')
ax3.grid(axis='y', linestyle='--', alpha=0.4)

lines1, labels1 = ax3.get_legend_handles_labels()
lines2, labels2 = ax3_twin.get_legend_handles_labels()
ax3.legend(lines1 + lines2, labels1 + labels2, loc='upper left', frameon=True, facecolor='white', framealpha=0.9)

plt.tight_layout()
out_png = Path("C:/Users/Nick/.gemini/antigravity/brain/892d6d20-4274-43dc-a605-1f060d93027d/fortified_3tier_apex_chart.png")
plt.savefig(out_png, dpi=300)
print("Saved chart to", out_png)

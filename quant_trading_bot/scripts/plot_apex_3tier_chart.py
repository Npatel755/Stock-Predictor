import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# Data from RESEARCH_STRATOSPHERE_CHAMELEON.json
names = [
    "Baseline 2X\n(Keep $5.5k)",
    "Balanced 3X\n(Keep $6.5k)",
    "Base Fortress 4X\n(Keep $8.5k)",
    "Convex Sprint 4X\n(Keep $8.5k, P1@$6k)",
    "Chameleon Crown\n(2-Tier Sprint)",
    "Chameleon Apex\n(3-Tier @ $10.0k)",
    "Chameleon Apex\n(3-Tier @ $9.8k)",
    "Chameleon Apex\n(3-Tier @ $9.6k)"
]

usd = [19836, 31897, 35111, 35512, 37027, 40027, 40618, 40635]
h1_usd = [14653, 23274, 24895, 25508, 26030, 27451, 27539, 27631]
h2_usd = [26463, 42924, 48176, 48305, 51089, 56108, 57342, 57264]
p1_days = [228.0, 234.0, 258.0, 221.0, 221.0, 221.0, 221.0, 221.0]
s4_cons = [23.0, 15.8, 9.4, 9.4, 9.4, 9.4, 9.4, 9.4]
y1_cash = [6295, 9712, 9545, 9739, 9861, 10104, 10120, 10127]

x = np.arange(len(names))
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 15), sharex=True)

# 1. 24-Month Total Cash Withdrawals (Stacked by Halves)
colors_h1 = ['#94a3b8', '#38bdf8', '#818cf8', '#6366f1', '#10b981', '#06b6d4', '#0284c7', '#2563eb']
colors_h2 = ['#64748b', '#0284c7', '#4f46e5', '#3730a3', '#059669', '#0891b2', '#0369a1', '#1d4ed8']

bars1 = ax1.bar(x, h1_usd, width=0.55, label="2010–2016 (First Half)", color=colors_h1, alpha=0.9, edgecolor='black', linewidth=0.8)
bars2 = ax1.bar(x, h2_usd, bottom=h1_usd, width=0.55, label="2017–2023 (Second Half)", color=colors_h2, alpha=0.9, edgecolor='black', linewidth=0.8)

for idx, (total, h1, h2) in enumerate(zip(usd, h1_usd, h2_usd)):
    ax1.text(idx, total + 850, f"${total:,.0f}", ha='center', va='bottom', fontsize=11, fontweight='bold', color='#0f172a')
    ax1.text(idx, h1 / 2, f"${h1:,.0f}", ha='center', va='center', fontsize=9, color='white', fontweight='bold')
    ax1.text(idx, h1 + h2 / 2, f"${h2:,.0f}", ha='center', va='center', fontsize=9, color='white', fontweight='bold')

ax1.axhline(40000.0, color='#2563eb', linestyle='--', linewidth=1.5, label="$40,000 Milestone Barrier")
ax1.set_ylabel("Total Withdrawn ($)", fontsize=12, fontweight='bold')
ax1.set_title("Evolution of Strategy Payouts Breaking $40k (Topstep $50K Static Combine)", fontsize=15, fontweight='bold', pad=15)
ax1.set_ylim(0, 46000)
ax1.grid(axis='y', linestyle='--', alpha=0.4)
ax1.legend(loc='upper left', frameon=True, facecolor='white', framealpha=0.9)

# 2. Year 1 Payout Cash & Days to P1
ax2_twin = ax2.twinx()
bars_y1 = ax2.bar(x - 0.15, y1_cash, width=0.3, color='#8b5cf6', alpha=0.85, edgecolor='black', linewidth=0.8, label="Year 1 Cash ($)")
line_p1 = ax2_twin.plot(x + 0.15, p1_days, marker='o', markersize=9, linewidth=2.5, color='#d97706', label="Days to Payout #1")

for idx, val in enumerate(y1_cash):
    ax2.text(idx - 0.15, val + 150, f"${val:,.0f}", ha='center', va='bottom', fontsize=9.5, fontweight='bold', color='#6d28d9')

for idx, val in enumerate(p1_days):
    ax2_twin.text(idx + 0.15, val + 2, f"{val:.0f}d", ha='center', va='bottom', fontsize=9.5, fontweight='bold', color='#b45309')

ax2.set_ylabel("Year 1 Cash ($)", fontsize=12, fontweight='bold', color='#6d28d9')
ax2_twin.set_ylabel("Days to Payout #1", fontsize=12, fontweight='bold', color='#b45309')
ax2.set_ylim(4000, 12500)
ax2_twin.set_ylim(200, 275)
ax2.grid(axis='y', linestyle='--', alpha=0.4)

lines1, labels1 = ax2.get_legend_handles_labels()
lines2, labels2 = ax2_twin.get_legend_handles_labels()
ax2.legend(lines1 + lines2, labels1 + labels2, loc='upper left', frameon=True, facecolor='white', framealpha=0.9)

# 3. Stress Worst-Case Open Mark Closure (S4 Tail Volatility Risk)
colors_s4 = ['#ef4444' if s > 10.0 else '#10b981' for s in s4_cons]
bars_s4 = ax3.bar(x, s4_cons, width=0.5, color=colors_s4, alpha=0.85, edgecolor='black', linewidth=0.8)
for idx, val in enumerate(s4_cons):
    label = f"{val:.1f}%\n(FAIL)" if val > 10.0 else f"{val:.1f}%\n(PASS)"
    ax3.text(idx, val + 0.6, label, ha='center', va='bottom', fontsize=9.5, fontweight='bold', color=colors_s4[idx])

ax3.axhline(9.5, color='#10b981', linestyle='--', linewidth=1.5, label="Gate 3 Risk Ceiling (<= 9.5%)")
ax3.set_ylabel("S4 Tail Closures (%)", fontsize=12, fontweight='bold')
ax3.set_ylim(0, 30)
ax3.set_xticks(x)
ax3.set_xticklabels(names, fontsize=9.5, fontweight='bold')
ax3.grid(axis='y', linestyle='--', alpha=0.4)
ax3.legend(loc='upper right', frameon=True, facecolor='white', framealpha=0.9)

plt.tight_layout()
out_png = Path("C:/Users/Nick/.gemini/antigravity/brain/892d6d20-4274-43dc-a605-1f060d93027d/chameleon_apex_3tier_chart.png")
plt.savefig(out_png, dpi=300)
print("Saved chart to", out_png)

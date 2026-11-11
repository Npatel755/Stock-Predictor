import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# Data from RESEARCH_FINAL_CHAMELEON_TRIO.json
names = [
    "Baseline 2X\n(Keep $5.5k)",
    "Balanced 3X\n(Keep $6.5k)",
    "Base Fortress 4X\n(Keep $8.5k)",
    "Convex Pure 4X\n(Keep $8.5k)",
    "Convex Sprint 4X\n(Keep $8.5k, P1@$6k)",
    "Chameleon Apex Pure\n(Gate $8.55k, K $8.5k)",
    "Chameleon Fortified\n(Gate $8.55k, Sp $6k)",
    "Chameleon Crown\n(Gate $8.5k, Sp $6k)"
]

usd = [19836, 31897, 35111, 35617, 35512, 36823, 36672, 37027]
p1_days = [228.0, 234.0, 258.0, 257.0, 221.0, 257.0, 221.0, 221.0]
s4_cons = [23.0, 15.8, 9.4, 9.4, 9.4, 9.4, 9.4, 9.4]
h1_usd = [14653, 23274, 24895, 25528, 25508, 26057, 26010, 26030]
h2_usd = [26463, 42924, 48176, 48518, 48305, 50589, 50307, 51089]

x = np.arange(len(names))
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(13, 14), sharex=True)

# 1. 24-Month Total Cash Withdrawals (Stacked by Halves)
colors_h1 = ['#94a3b8', '#38bdf8', '#818cf8', '#6366f1', '#4f46e5', '#ec4899', '#f43f5e', '#10b981']
colors_h2 = ['#64748b', '#0284c7', '#4f46e5', '#4338ca', '#3730a3', '#be185d', '#e11d48', '#059669']

bars1 = ax1.bar(x, h1_usd, width=0.55, label="2010–2016 (First Half)", color=colors_h1, alpha=0.9, edgecolor='black', linewidth=0.8)
bars2 = ax1.bar(x, h2_usd, bottom=h1_usd, width=0.55, label="2017–2023 (Second Half)", color=colors_h2, alpha=0.9, edgecolor='black', linewidth=0.8)

for idx, (total, h1, h2) in enumerate(zip(usd, h1_usd, h2_usd)):
    ax1.text(idx, total + 800, f"${total:,.0f}", ha='center', va='bottom', fontsize=11, fontweight='bold', color='#0f172a')
    ax1.text(idx, h1 / 2, f"${h1:,.0f}", ha='center', va='center', fontsize=9, color='white', fontweight='bold')
    ax1.text(idx, h1 + h2 / 2, f"${h2:,.0f}", ha='center', va='center', fontsize=9, color='white', fontweight='bold')

ax1.set_ylabel("Total Withdrawn ($)", fontsize=12, fontweight='bold')
ax1.set_title("Evolution of Strategy Payouts & Risk Metrics (Topstep $50K Static Combine)", fontsize=15, fontweight='bold', pad=15)
ax1.set_ylim(0, 42000)
ax1.grid(axis='y', linestyle='--', alpha=0.4)
ax1.legend(loc='upper left', frameon=True, facecolor='white', framealpha=0.9)

# 2. Time to First Payout (Days to Payout #1)
ax2.plot(x, p1_days, marker='o', markersize=10, linewidth=2.5, color='#d97706', label="Days to Payout #1 (Median Cal Days)")
for idx, val in enumerate(p1_days):
    ax2.text(idx, val + 3, f"{val:.0f}d", ha='center', va='bottom', fontsize=10, fontweight='bold', color='#b45309')

ax2.axhline(228.0, color='#94a3b8', linestyle=':', linewidth=1.5, label="Baseline Payout Delay (228 days)")
ax2.set_ylabel("Days to Payout #1", fontsize=12, fontweight='bold')
ax2.set_ylim(200, 275)
ax2.grid(axis='y', linestyle='--', alpha=0.4)
ax2.legend(loc='upper right', frameon=True, facecolor='white', framealpha=0.9)

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
ax3.set_xticklabels(names, fontsize=10, fontweight='bold')
ax3.grid(axis='y', linestyle='--', alpha=0.4)
ax3.legend(loc='upper right', frameon=True, facecolor='white', framealpha=0.9)

plt.tight_layout()
out_png = Path("C:/Users/Nick/.gemini/antigravity/brain/892d6d20-4274-43dc-a605-1f060d93027d/chameleon_crown_apex_chart.png")
plt.savefig(out_png, dpi=300)
print("Saved chart to", out_png)

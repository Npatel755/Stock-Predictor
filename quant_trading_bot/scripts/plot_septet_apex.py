import matplotlib.pyplot as plt
import numpy as np

# Set dark theme styling
plt.style.use('dark_background')
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6), dpi=300)

# Data for Strategy Progression
strategies = [
    "Current Base Rule",
    "Balanced 3X",
    "Fortress 4X\n(Adopted)",
    "Chameleon Crown\n($37k)",
    "Fortified 3-Tier\n($40k)",
    "Triple-Stack\n($52k)",
    "Chameleon Septet\n($61.6k APEX)"
]

cash_24m = [25899, 31897, 35178, 37027, 40310, 52016, 61652]
h1_cash = [18787, 23310, 24895, 26030, 27216, 41834, 53298]
h2_cash = [33542, 41125, 48176, 51089, 57052, 65035, 72334]
vol_risk = [16.5, 15.8, 9.4, 9.4, 9.4, 9.4, 9.4]
days_to_p1 = [228, 233, 258, 221, 221, 221, 221]

colors = ['#555555', '#4a90e2', '#f39c12', '#9b59b6', '#e67e22', '#2ecc71', '#00ffcc']

# Plot 1: 24-Month Total Cash Extraction
bars = ax1.bar(strategies, cash_24m, color=colors, width=0.6, edgecolor='white', linewidth=0.8, alpha=0.9)
ax1.set_title("24-Month Funded Cash Extraction ($)", fontsize=14, fontweight='bold', pad=15, color='#ffffff')
ax1.set_ylabel("USD Withdrawn ($)", fontsize=12, color='#e0e0e0')
ax1.grid(axis='y', linestyle='--', alpha=0.25)
ax1.set_ylim(0, 70000)

for bar in bars:
    yval = bar.get_height()
    ax1.text(bar.get_x() + bar.get_width()/2.0, yval + 1000, f"${yval:,.0f}", ha='center', va='bottom', fontsize=10, fontweight='bold', color='white')

# Annotation for apex gain
ax1.annotate(
    '+75.3% vs Fortress 4X\n(+$26,474 Net Cash)',
    xy=(6, 61652), xytext=(4.2, 64000),
    arrowprops=dict(facecolor='#00ffcc', shrink=0.08, width=2, headwidth=8),
    fontsize=11, fontweight='bold', color='#00ffcc',
    bbox=dict(boxstyle="round,pad=0.4", fc="#111111", ec="#00ffcc", lw=1.5)
)

ax1.tick_params(axis='x', rotation=25, labelsize=9)

# Plot 2: Half 1 vs Half 2 Performance & Risk
x = np.arange(len(strategies))
width = 0.35

rects1 = ax2.bar(x - width/2, h1_cash, width, label='Half 1 (2010-2016)', color='#3498db', alpha=0.85, edgecolor='white', linewidth=0.6)
rects2 = ax2.bar(x + width/2, h2_cash, width, label='Half 2 (2017-2023)', color='#2ecc71', alpha=0.85, edgecolor='white', linewidth=0.6)

ax2.set_title("H1 vs H2 Split Comparison (Robustness)", fontsize=14, fontweight='bold', pad=15, color='#ffffff')
ax2.set_ylabel("USD Withdrawn ($)", fontsize=12, color='#e0e0e0')
ax2.set_xticks(x)
ax2.set_xticklabels(strategies, rotation=25)
ax2.tick_params(axis='x', labelsize=9)
ax2.legend(frameon=True, facecolor='#222222', edgecolor='#444444')
ax2.grid(axis='y', linestyle='--', alpha=0.25)
ax2.set_ylim(0, 80000)

for rect in rects1:
    h = rect.get_height()
    ax2.text(rect.get_x() + rect.get_width()/2.0, h + 800, f"${h/1000:.1f}k", ha='center', va='bottom', fontsize=8, color='#a0c8f0')

for rect in rects2:
    h = rect.get_height()
    ax2.text(rect.get_x() + rect.get_width()/2.0, h + 800, f"${h/1000:.1f}k", ha='center', va='bottom', fontsize=8, color='#a0f0c0')

plt.tight_layout()
out_path = "C:/Users/Nick/.gemini/antigravity/brain/892d6d20-4274-43dc-a605-1f060d93027d/chameleon_septet_61k_chart.png"
plt.savefig(out_path, dpi=300)
print(f"Chart saved to {out_path}")

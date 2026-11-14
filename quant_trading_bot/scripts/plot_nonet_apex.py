import matplotlib.pyplot as plt
import numpy as np

# Set dark theme styling
plt.style.use('dark_background')
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6.5), dpi=300)

# Data for Strategy Progression
strategies = [
    "Base Rule\n($25.9k)",
    "Fortress 4X\n($35.2k)",
    "Fortified 3-Tier\n($40.3k)",
    "Triple-Stack\n($52.0k)",
    "Septet Apex\n($61.7k)",
    "Octet Apex\n($63.0k)",
    "Nonet Apex\n(Deep Pacing)"
]

cash_24m = [25899, 35178, 40310, 52016, 61652, 63043, 95067]
h1_cash = [18787, 24895, 27216, 41834, 53298, 54856, 77813]
h2_cash = [33542, 48176, 57052, 65035, 72334, 73511, 117131]

colors = ['#555555', '#f39c12', '#9b59b6', '#2ecc71', '#00ffcc', '#3498db', '#ff3366']

# Plot 1: 24-Month Total Cash Extraction
bars = ax1.bar(strategies, cash_24m, color=colors, width=0.6, edgecolor='white', linewidth=0.8, alpha=0.9)
ax1.set_title("24-Month Funded Cash Extraction Evolution ($)", fontsize=14, fontweight='bold', pad=15, color='#ffffff')
ax1.set_ylabel("USD Withdrawn ($)", fontsize=12, color='#e0e0e0')
ax1.grid(axis='y', linestyle='--', alpha=0.25)
ax1.set_ylim(0, 108000)

for bar in bars:
    yval = bar.get_height()
    ax1.text(bar.get_x() + bar.get_width()/2.0, yval + 1200, f"${yval:,.0f}", ha='center', va='bottom', fontsize=9.5, fontweight='bold', color='white')

# Annotation for apex gain
ax1.annotate(
    '+170.2% vs Fortress 4X\n(+$59,889 Cold Cash)',
    xy=(6, 95067), xytext=(4.0, 99000),
    arrowprops=dict(facecolor='#ff3366', shrink=0.08, width=2, headwidth=8),
    fontsize=11, fontweight='bold', color='#ff3366',
    bbox=dict(boxstyle="round,pad=0.4", fc="#111111", ec="#ff3366", lw=1.5)
)

ax1.tick_params(axis='x', rotation=25, labelsize=9)

# Plot 2: Half 1 vs Half 2 Performance & Risk
x = np.arange(len(strategies))
width = 0.35

rects1 = ax2.bar(x - width/2, h1_cash, width, label='Half 1: 2010-2016 (Choppy/Low Drift)', color='#3498db', alpha=0.85, edgecolor='white', linewidth=0.6)
rects2 = ax2.bar(x + width/2, h2_cash, width, label='Half 2: 2017-2023 (Trend/High Vol)', color='#2ecc71', alpha=0.85, edgecolor='white', linewidth=0.6)

ax2.set_title("Split Balance & Robustness Across 14 Years", fontsize=14, fontweight='bold', pad=15, color='#ffffff')
ax2.set_ylabel("USD Withdrawn ($)", fontsize=12, color='#e0e0e0')
ax2.set_xticks(x)
ax2.set_xticklabels(strategies, rotation=25)
ax2.tick_params(axis='x', labelsize=9)
ax2.legend(frameon=True, facecolor='#222222', edgecolor='#444444')
ax2.grid(axis='y', linestyle='--', alpha=0.25)
ax2.set_ylim(0, 130000)

for rect in rects1:
    h = rect.get_height()
    ax2.text(rect.get_x() + rect.get_width()/2.0, h + 1000, f"${h/1000:.1f}k", ha='center', va='bottom', fontsize=8, color='#a0c8f0')

for rect in rects2:
    h = rect.get_height()
    ax2.text(rect.get_x() + rect.get_width()/2.0, h + 1000, f"${h/1000:.1f}k", ha='center', va='bottom', fontsize=8, color='#a0f0c0')

plt.tight_layout()
out_path = "C:/Users/Nick/.gemini/antigravity/brain/892d6d20-4274-43dc-a605-1f060d93027d/chameleon_nonet_95k_chart.png"
plt.savefig(out_path, dpi=300)
print(f"Chart saved to {out_path}")

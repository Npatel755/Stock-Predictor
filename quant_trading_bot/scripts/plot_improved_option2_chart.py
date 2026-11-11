"""Plot Improved Option 2 (Fortress Fast-4X) Comparison"""
import matplotlib.pyplot as plt
import numpy as np

plt.style.use('dark_background')
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))

# 1. Total 24-Month Cash Payouts
models = [
    'Current Live Base\n(2x @ $4k, K=$6k)',
    'Balanced 3x\n(3x @ $5k, K=$6.5k)',
    'Option 2 Base\n(Fortress 4X, K=$8.5k)',
    'Option 2 Upgraded\n(Fast-4X + P1 @ $6k)'
]
s0_cash = [25899, 31897, 35178, 35061]
colors = ['#757575', '#00E5FF', '#FF9100', '#00E676']

bars1 = ax1.bar(models, s0_cash, color=colors, width=0.5, alpha=0.9)
ax1.set_title('24-Month Net Cash Extracted ($)', fontsize=13, fontweight='bold', pad=10)
ax1.set_ylabel('Total Withdrawn ($)', fontsize=11)
ax1.grid(True, linestyle='--', alpha=0.3, axis='y')
for bar in bars1:
    y = bar.get_height()
    gain = (y / s0_cash[0] - 1) * 100
    label = f'${y:,.0f}' if gain == 0 else f'${y:,.0f}\n(+{gain:.1f}%)'
    ax1.text(bar.get_x() + bar.get_width()/2.0, y + 400, label, ha='center', va='bottom', fontsize=9, fontweight='bold', color='#00E676' if gain > 0 else 'white')
ax1.set_ylim(0, 42000)

# 2. Year 1 Cash Withdrawn (Pulling Cash Forward)
y1_cash = [8277, 9712, 9500, 9504]
bars2 = ax2.bar(models, y1_cash, color=['#757575', '#00E5FF', '#FF9100', '#76FF03'], width=0.5, alpha=0.85)
ax2.set_title('Year 1 Cash Extracted ($) [Speed of Returns]', fontsize=13, fontweight='bold', pad=10)
ax2.set_ylabel('Year 1 Cash ($)', fontsize=11)
ax2.grid(True, linestyle='--', alpha=0.3, axis='y')
for bar in bars2:
    y = bar.get_height()
    gain = (y / y1_cash[0] - 1) * 100
    label = f'${y:,.0f}' if gain == 0 else f'${y:,.0f}\n(+{gain:.1f}%)'
    ax2.text(bar.get_x() + bar.get_width()/2.0, y + 150, label, ha='center', va='bottom', fontsize=9, fontweight='bold', color='#76FF03' if gain > 0 else 'white')
ax2.set_ylim(0, 12500)

# 3. Days to Payout #1 (Faster Capital Payback)
days_p1 = [231.0, 234.0, 263.0, 224.0]
bars3 = ax3.bar(models, days_p1, color=['#757575', '#00E5FF', '#FF5252', '#00E676'], width=0.5, alpha=0.85)
ax3.set_title('Calendar Days to Payout #1 (Initial Capital Payback)', fontsize=13, fontweight='bold', pad=10)
ax3.set_ylabel('Calendar Days', fontsize=11)
ax3.grid(True, linestyle='--', alpha=0.3, axis='y')
for bar in bars3:
    y = bar.get_height()
    diff = y - days_p1[0]
    label = f'{y:.0f} d' if diff == 0 else f'{y:.0f} d\n({diff:+.0f} d)'
    ax3.text(bar.get_x() + bar.get_width()/2.0, y + 3.0, label, ha='center', va='bottom', fontsize=9, fontweight='bold', color='#00E676' if diff < 0 else ('#FF5252' if diff > 0 else 'white'))
ax3.set_ylim(0, 310)

# 4. Conservative Closures (S3 Stress vs S4 Vol Surge)
x = np.arange(len(models))
width = 0.35
s3_cons = [0.050, 0.050, 0.050, 0.050]
s4_cons = [0.165, 0.158, 0.094, 0.094]

rects_s3 = ax4.bar(x - width/2, [c * 100 for c in s3_cons], width, label='S3 Stress Cons Closure (%)', color='#00E5FF', alpha=0.85)
rects_s4 = ax4.bar(x + width/2, [c * 100 for c in s4_cons], width, label='S4 Vol Surge Cons Closure (%)', color='#FF5252', alpha=0.85)

ax4.set_title('Conservative Open-Mark Closure Rates (%)', fontsize=13, fontweight='bold', pad=10)
ax4.set_xticks(x)
ax4.set_xticklabels(models, fontsize=8)
ax4.set_ylabel('Closure Rate (%)', fontsize=11)
ax4.grid(True, linestyle='--', alpha=0.3, axis='y')
ax4.legend(frameon=True, facecolor='#1e1e1e', edgecolor='none')
for r in rects_s3:
    ax4.annotate(f'{r.get_height():.1f}%', (r.get_x() + r.get_width()/2, r.get_height()), xytext=(0, 3), textcoords="offset points", ha='center', fontsize=8, color='#00E5FF', fontweight='bold')
for r in rects_s4:
    ax4.annotate(f'{r.get_height():.1f}%', (r.get_x() + r.get_width()/2, r.get_height()), xytext=(0, 3), textcoords="offset points", ha='center', fontsize=8, color='#FF5252', fontweight='bold')
ax4.set_ylim(0, 22)

plt.tight_layout()
chart_path = 'C:/Users/Nick/.gemini/antigravity/brain/892d6d20-4274-43dc-a605-1f060d93027d/improved_option2_chart.png'
plt.savefig(chart_path, dpi=200, bbox_inches='tight')
print(f"Chart saved to {chart_path}")

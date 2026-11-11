"""Plot Deep Improvement Frontiers for Option 2"""
import matplotlib.pyplot as plt
import numpy as np

plt.style.use('dark_background')
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))

models = [
    'Current Live Base\n(2x @ $4k, K=$6k)',
    'Balanced 3x\n(3x @ $5k, K=$6.5k)',
    'Option 2 Base\n(Fortress 4X, K=$8.5k)',
    'Option 2 Upgraded\n(Fast-4X Sprint P1@$6k)',
    'Option 2 Apex\n(Multi-Milestone A)'
]

s0_cash = [25899, 31897, 35178, 35158, 35076]
colors = ['#757575', '#00E5FF', '#FF9100', '#00E676', '#76FF03']

# 1. 24-Month Total Cash
bars1 = ax1.bar(models, s0_cash, color=colors, width=0.5, alpha=0.9)
ax1.set_title('24-Month Net Cash Extracted ($)', fontsize=13, fontweight='bold', pad=10)
ax1.set_ylabel('Total Withdrawn ($)', fontsize=11)
ax1.grid(True, linestyle='--', alpha=0.3, axis='y')
for bar in bars1:
    y = bar.get_height()
    gain = (y / s0_cash[0] - 1) * 100
    label = f'${y:,.0f}' if gain == 0 else f'${y:,.0f}\n(+{gain:.1f}%)'
    ax1.text(bar.get_x() + bar.get_width()/2.0, y + 400, label, ha='center', va='bottom', fontsize=8.5, fontweight='bold', color='#76FF03' if gain > 30 else ('#00E5FF' if gain > 0 else 'white'))
ax1.set_ylim(0, 42000)

# 2. Calendar Days to Payout #1
days_p1 = [231.0, 234.0, 263.0, 224.0, 216.0]
bars2 = ax2.bar(models, days_p1, color=['#757575', '#00E5FF', '#FF5252', '#00E676', '#76FF03'], width=0.5, alpha=0.85)
ax2.set_title('Calendar Days to Payout #1 (Speed to First Dollar)', fontsize=13, fontweight='bold', pad=10)
ax2.set_ylabel('Calendar Days', fontsize=11)
ax2.grid(True, linestyle='--', alpha=0.3, axis='y')
for bar in bars2:
    y = bar.get_height()
    diff = y - days_p1[0]
    label = f'{y:.0f} d' if diff == 0 else f'{y:.0f} d\n({diff:+.0f} d)'
    ax2.text(bar.get_x() + bar.get_width()/2.0, y + 3.0, label, ha='center', va='bottom', fontsize=8.5, fontweight='bold', color='#76FF03' if diff < 0 else ('#FF5252' if diff > 0 else 'white'))
ax2.set_ylim(0, 310)

# 3. Year 1 Payout Frequency (Number of Payouts in Year 1)
y1_pays = [9.23, 9.19, 8.27, 8.75, 9.12]
bars3 = ax3.bar(models, y1_pays, color=['#757575', '#00E5FF', '#FF5252', '#00E676', '#76FF03'], width=0.5, alpha=0.85)
ax3.set_title('Year 1 Payout Frequency (Payout Count)', fontsize=13, fontweight='bold', pad=10)
ax3.set_ylabel('Number of Payouts in Year 1', fontsize=11)
ax3.grid(True, linestyle='--', alpha=0.3, axis='y')
for bar in bars3:
    y = bar.get_height()
    diff = y - y1_pays[0]
    label = f'{y:.2f}' if abs(diff) < 0.05 else f'{y:.2f}\n({diff:+.2f})'
    ax3.text(bar.get_x() + bar.get_width()/2.0, y + 0.1, label, ha='center', va='bottom', fontsize=8.5, fontweight='bold', color='#76FF03' if diff >= -0.15 else ('#FF5252' if diff < -0.5 else 'white'))
ax3.set_ylim(0, 11)

# 4. Conservative Closures (S3 Stress vs S4 Vol Surge)
x = np.arange(len(models))
width = 0.35
s3_cons = [0.050, 0.050, 0.050, 0.050, 0.050]
s4_cons = [0.165, 0.158, 0.094, 0.094, 0.094]

rects_s3 = ax4.bar(x - width/2, [c * 100 for c in s3_cons], width, label='S3 Stress Cons Closure (%)', color='#00E5FF', alpha=0.85)
rects_s4 = ax4.bar(x + width/2, [c * 100 for c in s4_cons], width, label='S4 Vol Surge Cons Closure (%)', color='#FF5252', alpha=0.85)

ax4.set_title('Conservative Open-Mark Closure Rates (%)', fontsize=13, fontweight='bold', pad=10)
ax4.set_xticks(x)
ax4.set_xticklabels(models, fontsize=7.5)
ax4.set_ylabel('Closure Rate (%)', fontsize=11)
ax4.grid(True, linestyle='--', alpha=0.3, axis='y')
ax4.legend(frameon=True, facecolor='#1e1e1e', edgecolor='none')
for r in rects_s3:
    ax4.annotate(f'{r.get_height():.1f}%', (r.get_x() + r.get_width()/2, r.get_height()), xytext=(0, 3), textcoords="offset points", ha='center', fontsize=8, color='#00E5FF', fontweight='bold')
for r in rects_s4:
    ax4.annotate(f'{r.get_height():.1f}%', (r.get_x() + r.get_width()/2, r.get_height()), xytext=(0, 3), textcoords="offset points", ha='center', fontsize=8, color='#FF5252', fontweight='bold')
ax4.set_ylim(0, 22)

plt.tight_layout()
chart_path = 'C:/Users/Nick/.gemini/antigravity/brain/892d6d20-4274-43dc-a605-1f060d93027d/further_improvement_chart.png'
plt.savefig(chart_path, dpi=200, bbox_inches='tight')
print(f"Chart saved to {chart_path}")

"""Plot Fortress 4X Champion Chart"""
import matplotlib.pyplot as plt
import numpy as np

plt.style.use('dark_background')
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))

# 1. 24-Month Net Cash Extracted
models = ['Current Live Base\n(2x @ $4k, K=$6k)', 'Balanced 3x\n(3x @ $5k, K=$7k)', 'Fortress 4X Champion\n(4x @ $6.5k, K=$8.5k)', 'Apex 5-Tier\n(5x @ $8k, K=$9.0k)']
s0_cash = [25899, 32076, 35178, 35325]
colors = ['#757575', '#00E5FF', '#00E676', '#FFD600']

bars1 = ax1.bar(models, s0_cash, color=colors, width=0.5, alpha=0.9)
ax1.set_title('24-Month Net Cash Payouts ($)', fontsize=13, fontweight='bold', pad=10)
ax1.set_ylabel('Total Withdrawn ($)', fontsize=11)
ax1.grid(True, linestyle='--', alpha=0.3, axis='y')
for bar in bars1:
    y = bar.get_height()
    gain = (y / s0_cash[0] - 1) * 100
    label = f'${y:,.0f}' if gain == 0 else f'${y:,.0f}\n(+{gain:.1f}%)'
    ax1.text(bar.get_x() + bar.get_width()/2.0, y + 400, label, ha='center', va='bottom', fontsize=9, fontweight='bold', color='#00E676' if gain > 0 else 'white')
ax1.set_ylim(0, 42000)

# 2. Both Halves Robustness (2010-16 vs 2017-23)
x = np.arange(len(models))
width = 0.35
h1_cash = [18787, 23435, 25156, 24667]
h2_cash = [33542, 41362, 45948, 46777]

rects_h1 = ax2.bar(x - width/2, h1_cash, width, label='2010–2016 (Half 1)', color='#2979FF', alpha=0.85)
rects_h2 = ax2.bar(x + width/2, h2_cash, width, label='2017–2023 (Half 2)', color='#FF9100', alpha=0.85)

ax2.set_title('Cash Generation Across Both 7-Year Halves ($)', fontsize=13, fontweight='bold', pad=10)
ax2.set_xticks(x)
ax2.set_xticklabels(models, fontsize=8)
ax2.set_ylabel('Cash Extracted ($)', fontsize=11)
ax2.grid(True, linestyle='--', alpha=0.3, axis='y')
ax2.legend(frameon=True, facecolor='#1e1e1e', edgecolor='none')
for r in rects_h1:
    g = (r.get_height() / h1_cash[0] - 1) * 100
    if g > 0:
        ax2.annotate(f'+{g:.1f}%', (r.get_x() + r.get_width()/2, r.get_height()), xytext=(0, 3), textcoords="offset points", ha='center', fontsize=8, color='#2979FF', fontweight='bold')
for r in rects_h2:
    g = (r.get_height() / h2_cash[0] - 1) * 100
    if g > 0:
        ax2.annotate(f'+{g:.1f}%', (r.get_x() + r.get_width()/2, r.get_height()), xytext=(0, 3), textcoords="offset points", ha='center', fontsize=8, color='#FF9100', fontweight='bold')

# 3. Conservative Closures (S3 Stress vs S4 Vol Surge)
s3_cons = [0.050, 0.050, 0.050, 0.050]
s4_cons = [0.165, 0.158, 0.094, 0.094]

rects_s3 = ax3.bar(x - width/2, [c * 100 for c in s3_cons], width, label='S3 Stress Cons Closure (%)', color='#00E5FF', alpha=0.85)
rects_s4 = ax3.bar(x + width/2, [c * 100 for c in s4_cons], width, label='S4 Vol Surge Cons Closure (%)', color='#FF5252', alpha=0.85)

ax3.set_title('Conservative Open-Mark Closure Rates (%)', fontsize=13, fontweight='bold', pad=10)
ax3.set_xticks(x)
ax3.set_xticklabels(models, fontsize=8)
ax3.set_ylabel('Closure Rate (%)', fontsize=11)
ax3.grid(True, linestyle='--', alpha=0.3, axis='y')
ax3.legend(frameon=True, facecolor='#1e1e1e', edgecolor='none')
for r in rects_s3:
    ax3.annotate(f'{r.get_height():.1f}%', (r.get_x() + r.get_width()/2, r.get_height()), xytext=(0, 3), textcoords="offset points", ha='center', fontsize=8, color='#00E5FF', fontweight='bold')
for r in rects_s4:
    ax3.annotate(f'{r.get_height():.1f}%', (r.get_x() + r.get_width()/2, r.get_height()), xytext=(0, 3), textcoords="offset points", ha='center', fontsize=8, color='#FF5252', fontweight='bold')
ax3.set_ylim(0, 22)

# 4. Multi-Account Portfolio Cash Scaling (1 to 5 Accounts)
accounts = [1, 2, 3, 4, 5]
cash_champ = 35178
port_cash = [a * cash_champ for a in accounts]
port_annual = [c / 2 for c in port_cash]

ax4.plot(accounts, port_cash, marker='o', linewidth=3, markersize=8, color='#00E676', label='24-Month Cash Extracted')
ax4.plot(accounts, port_annual, marker='s', linewidth=2.5, markersize=7, color='#00E5FF', linestyle='--', label='Annual Cash Extracted')
ax4.set_title('Multi-Account Scaling (Fortress 4X Champion)', fontsize=13, fontweight='bold', pad=10)
ax4.set_xlabel('Number of Accounts', fontsize=11)
ax4.set_ylabel('Cash Extracted ($)', fontsize=11)
ax4.set_xticks(accounts)
ax4.grid(True, linestyle='--', alpha=0.3)
ax4.legend(loc='upper left', frameon=True, facecolor='#1e1e1e', edgecolor='none')
for a, c in zip(accounts, port_cash):
    ax4.annotate(f'${c:,.0f}', (a, c), textcoords="offset points", xytext=(0, 10), ha='center', fontsize=9, fontweight='bold', color='#00E676')

plt.tight_layout()
chart_path = 'C:/Users/Nick/.gemini/antigravity/brain/892d6d20-4274-43dc-a605-1f060d93027d/fortress_4x_champion_chart.png'
plt.savefig(chart_path, dpi=200, bbox_inches='tight')
print(f"Chart saved to {chart_path}")

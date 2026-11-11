"""Plot Supercharged Funded Strategy Comparison"""
import matplotlib.pyplot as plt
import numpy as np

# Set style
plt.style.use('dark_background')
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))

# 1. 24-Month Cash Withdrawn Across Scenarios
categories = ['Baseline 2x\n(K=$5.5k)', 'Single-Stage 4x\n(K=$7.5k)', 'Single-Stage 4x\n(K=$8.0k)', 'Two-Stage 4x\n(P1@$4k, K=$7.5k)', 'Two-Stage 4x\n(P1@$4k, K=$8.0k)']
s0_cash = [26969, 37988, 38095, 37263, 37377]
s3_cash = [17101, 23135, 23248, 22622, 22631]
s4_cash = [19951, 27375, 27003, 26810, 26471]

x = np.arange(len(categories))
width = 0.25

rects1 = ax1.bar(x - width, s0_cash, width, label='S0 Nominal', color='#00E676', alpha=0.9)
rects2 = ax1.bar(x, s3_cash, width, label='S3 Stress (+2t, -25%)', color='#FF9100', alpha=0.9)
rects3 = ax1.bar(x + width, s4_cash, width, label='S4 Vol Surge (1.5x)', color='#2979FF', alpha=0.9)

ax1.set_title('24-Month Cash Payouts by Stress Regime ($)', fontsize=13, fontweight='bold', pad=10)
ax1.set_xticks(x)
ax1.set_xticklabels(categories, fontsize=9)
ax1.set_ylabel('Net Cash Extracted ($)', fontsize=11)
ax1.grid(True, linestyle='--', alpha=0.3, axis='y')
ax1.legend(frameon=True, facecolor='#1e1e1e', edgecolor='none')
for r in rects1:
    ax1.annotate(f'${r.get_height():,.0f}',
                 xy=(r.get_x() + r.get_width() / 2, r.get_height()),
                 xytext=(0, 3), textcoords="offset points",
                 ha='center', va='bottom', fontsize=8, color='#00E676', fontweight='bold')

# 2. Time to Payout #1 & Payback Speed
models = ['Baseline 2x', 'Two-Stage 3x', 'Two-Stage 4x (K=7.5k)', 'Two-Stage 4x (K=8.0k)']
days_to_p1 = [59.0, 44.0, 44.0, 44.0]
p1_cash = [1500, 1000, 1000, 1000]

colors = ['#FF5252', '#00E5FF', '#76FF03', '#FFD600']
bars = ax2.bar(models, days_to_p1, color=colors, width=0.5, alpha=0.85)
ax2.axhline(44.0, color='#00E5FF', linestyle=':', alpha=0.7, label='Fast Payback (~44 Days)')
ax2.set_title('Median Days to Payout #1 (Fee Payback)', fontsize=13, fontweight='bold', pad=10)
ax2.set_ylabel('Trading Days', fontsize=11)
ax2.grid(True, linestyle='--', alpha=0.3, axis='y')
for bar in bars:
    yval = bar.get_height()
    ax2.text(bar.get_x() + bar.get_width()/2.0, yval + 1.5, f'{yval:.0f} Days\n(~2.1 mo)', ha='center', va='bottom', fontsize=9, fontweight='bold')
ax2.set_ylim(0, 75)

# 3. Ruin Rate & Account Safety (All Models 0.0% Nominal Ruin)
labels_safety = ['Baseline 2x', 'Two-Stage 4x ($7.5k)', 'Two-Stage 4x ($8.0k)']
s0_ruin = [0.0, 0.0, 0.0]
worst_valley = [-1686, -1686, -1686]
static_floor = [-2000, -2000, -2000]

x_pos = np.arange(len(labels_safety))
ax3.bar(x_pos, worst_valley, color='#2979FF', width=0.4, alpha=0.85, label='Worst Valley Ever Reached')
ax3.axhline(-2000, color='#FF1744', linestyle='--', linewidth=2, label='Topstep -$2,000 Static Floor')
ax3.set_title('Worst Lifetime Drawdown vs -$2,000 Static Floor', fontsize=13, fontweight='bold', pad=10)
ax3.set_xticks(x_pos)
ax3.set_xticklabels(labels_safety, fontsize=10)
ax3.set_ylabel('Account Drawdown ($)', fontsize=11)
ax3.set_ylim(-2400, 200)
ax3.grid(True, linestyle='--', alpha=0.3, axis='y')
ax3.legend(loc='lower left', frameon=True, facecolor='#1e1e1e', edgecolor='none')
for i, v in enumerate(worst_valley):
    ax3.text(i, v - 150, f'${v:,.0f}\n(+$314 Buffer)', ha='center', va='top', fontsize=9, color='#00E676', fontweight='bold')

# 4. Multi-Account Portfolio Cash Scaling (1 to 5 Topstep Accounts)
accounts = [1, 2, 3, 4, 5]
cash_per_acct = 37263
portfolio_cash = [a * cash_per_acct for a in accounts]
annual_cash = [c / 2 for c in portfolio_cash]

ax4.plot(accounts, portfolio_cash, marker='o', linewidth=3, markersize=8, color='#00E676', label='24-Month Total Cash')
ax4.plot(accounts, annual_cash, marker='s', linewidth=2.5, markersize=7, color='#00E5FF', linestyle='--', label='Annual Cash Extracted')
ax4.set_title('Multi-Account Scaling Potential (Topstep 5-Acct Limit)', fontsize=13, fontweight='bold', pad=10)
ax4.set_xlabel('Number of Active Accounts', fontsize=11)
ax4.set_ylabel('Cumulative Cash Extracted ($)', fontsize=11)
ax4.set_xticks(accounts)
ax4.grid(True, linestyle='--', alpha=0.3)
ax4.legend(loc='upper left', frameon=True, facecolor='#1e1e1e', edgecolor='none')
for a, c in zip(accounts, portfolio_cash):
    ax4.annotate(f'${c:,.0f}', (a, c), textcoords="offset points", xytext=(0, 10), ha='center', fontsize=9, fontweight='bold', color='#00E676')

plt.tight_layout()
chart_path = 'C:/Users/Nick/.gemini/antigravity/brain/892d6d20-4274-43dc-a605-1f060d93027d/supercharged_funded_strategy_chart.png'
plt.savefig(chart_path, dpi=200, bbox_inches='tight')
print(f"Chart saved to {chart_path}")

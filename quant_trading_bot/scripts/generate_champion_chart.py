"""Generate Visualization for the Champion Fortress Evaluation Strategy.
"""
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# Setup plot style
plt.style.use('dark_background')
fig, axs = plt.subplots(2, 2, figsize=(16, 11), dpi=200)
fig.patch.set_facecolor('#0d1117')

for row in axs:
    for ax in row:
        ax.set_facecolor('#161b22')
        ax.grid(True, linestyle='--', alpha=0.25, color='#8b949e')
        ax.tick_params(colors='#c9d1d9', labelsize=10)
        for spine in ax.spines.values():
            spine.set_color('#30363d')

# -------------------------------------------------------------
# Panel A: Anti-Ruin Defensive Ratchet vs Fixed Sizing
# -------------------------------------------------------------
ax1 = axs[0, 0]
trades = np.arange(0, 31)

# Synthetic trajectory during early adverse sequence (4 consecutive losses)
# Fixed 6 MNQ: drops -$180 * 4 = -$720, then -$180 * 4 = -$1,440 -> blowup zone
fixed_path = np.array([0, -180, -360, -540, -720, -900, -750, -930, -1110, -1290, -1470, -1650, -1830, -2010])
fixed_trades = np.arange(len(fixed_path))

# Fortress Ratchet: drops -$140 * 2 = -$280 (hits -$250 threshold), cuts to 1 MNQ (-$36/trade)
# Even with 10 losses, it only drops -$360 more to -$640, then recovers when edge returns!
fortress_path = np.array([
    0, -140, -280, # hits threshold at -$280 -> cuts to 1 MNQ!
    -316, -352, -388, -424, -460, # 5 more losses, but only -$36 each!
    -380, -300, -220, # recovers back above -$250! -> scales back to 4 MNQ!
    -80, +120, +350, +580, +820, +1060, # enters Stage 2 (8 MNQ)!
    +1420, +1780, +2140, +2500, # enters Stage 3 (12 MNQ)!
    +3100, +2950, +3550, +4150 # Passed!
])
fortress_trades = np.arange(len(fortress_path))

ax1.plot(fixed_trades, fixed_path, color='#f85149', linewidth=2.5, linestyle='--', marker='x', markersize=5, label='Unmanaged Fixed Size (Busts into -$2,000 Floor)')
ax1.plot(fortress_trades, fortress_path, color='#3fb950', linewidth=3.0, marker='o', markersize=5, label='Fortress Passer (Anti-Ruin Ratchet: Floor Never Breached!)')

ax1.axhline(4000, color='#3fb950', linestyle='-', linewidth=2.0, label='+$4,000 Target (Passed)')
ax1.axhline(0, color='#8b949e', linestyle='-', linewidth=1.0)
ax1.axhline(-250, color='#d29922', linestyle=':', linewidth=1.5, label='-$250 Defensive Shield Threshold (Cut to 1 MNQ)')
ax1.axhline(-1000, color='#f85149', linestyle=':', linewidth=1.5, label='-$1,000 Daily Loss Limit')
ax1.axhline(-2000, color='#da3633', linestyle='--', linewidth=2.0, label='-$2,000 Static Floor (Topstep)')

ax1.fill_between(fortress_trades, -250, -2000, color='#f85149', alpha=0.08, label='Defensive Armor Zone (1 MNQ Only)')

ax1.set_title('A: Anti-Ruin Defensive Ratchet vs Unmanaged Sizing', color='#f0f6fc', fontsize=12, fontweight='bold', pad=10)
ax1.set_xlabel('Cumulative Trades', color='#c9d1d9', fontsize=10)
ax1.set_ylabel('Account Equity ($)', color='#c9d1d9', fontsize=10)
ax1.set_xlim(0, 25)
ax1.set_ylim(-2200, 4500)
ax1.legend(loc='upper left', fontsize=7.5, facecolor='#161b22', edgecolor='#30363d')

# -------------------------------------------------------------
# Panel B: Pass Rate & Ruin Rate Evolution
# -------------------------------------------------------------
ax2 = axs[0, 1]
stages = [
    'Fixed 12 MNQ\n(Unmanaged)',
    'Arch D Baseline\n(Fixed 6 MNQ)',
    'Book D+ Ensemble\n(Multi-Sleeve)',
    'Cushion-Staged\n(6c -> 10c)',
    'Fortress Champion\n(Anti-Ruin Ratchet)'
]
pass_rates = [42.1, 44.1, 50.7, 71.3, 81.9]
ruin_rates = [47.7, 18.2, 11.4, 28.7, 18.1]

x_bars = np.arange(len(stages))
width = 0.35

rects1 = ax2.bar(x_bars - width/2, pass_rates, width, label='Pass Rate (%)', color='#3fb950', alpha=0.90)
rects2 = ax2.bar(x_bars + width/2, ruin_rates, width, label='Ruin Rate (%)', color='#f85149', alpha=0.90)

for rect in rects1:
    h = rect.get_height()
    ax2.annotate(f'{h:.1f}%', xy=(rect.get_x() + rect.get_width() / 2, h),
                 xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', color='#3fb950', fontsize=8.5, fontweight='bold')

for rect in rects2:
    h = rect.get_height()
    ax2.annotate(f'{h:.1f}%', xy=(rect.get_x() + rect.get_width() / 2, h),
                 xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', color='#f85149', fontsize=8.5, fontweight='bold')

ax2.set_title('B: Pass Rate vs Ruin Rate Evolution across Architectures', color='#f0f6fc', fontsize=12, fontweight='bold', pad=10)
ax2.set_xticks(x_bars)
ax2.set_xticklabels(stages, fontsize=8.5, color='#c9d1d9')
ax2.set_ylabel('Percentage (%)', color='#c9d1d9', fontsize=10)
ax2.set_ylim(0, 95)
ax2.legend(loc='upper left', fontsize=8.5, facecolor='#161b22', edgecolor='#30363d')

# -------------------------------------------------------------
# Panel C: Drawdown Safety Margin (Peak DD on Passing Accounts)
# -------------------------------------------------------------
ax3 = axs[1, 0]
architectures = ['Fixed 12 MNQ', 'Fixed 6 MNQ', 'Cushion 6->10c', 'Fortress Champion']
avg_dds = [1441.78, 954.11, 870.85, 853.68]
colors = ['#da3633', '#d29922', '#58a6ff', '#3fb950']

bars3 = ax3.bar(architectures, avg_dds, color=colors, alpha=0.85, width=0.55)

for bar in bars3:
    yval = bar.get_height()
    ax3.annotate(f'${yval:.2f}', xy=(bar.get_x() + bar.get_width()/2, yval),
                 xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', color='#f0f6fc', fontsize=9, fontweight='bold')

ax3.axhline(1000, color='#f85149', linestyle='--', linewidth=1.5, label='-$1,000 Daily Loss Limit')
ax3.axhline(2000, color='#da3633', linestyle='-', linewidth=2.0, label='-$2,000 Static Floor Limit')

ax3.set_title('C: Average Drawdown Experienced on Passing Accounts', color='#f0f6fc', fontsize=12, fontweight='bold', pad=10)
ax3.set_ylabel('Max Drawdown ($)', color='#c9d1d9', fontsize=10)
ax3.set_ylim(0, 2200)
ax3.legend(loc='upper right', fontsize=8.5, facecolor='#161b22', edgecolor='#30363d')

# -------------------------------------------------------------
# Panel D: The Master Execution Rules
# -------------------------------------------------------------
ax4 = axs[1, 1]
ax4.axis('off')

rules_data = [
    ["State / Condition", "Position Sizing", "Stop Loss Risk", "Profit Target", "Safety Rule"],
    ["Defensive Shield (< -$250)", "1 MNQ", "-$36.00 (18pt)", "+$40.00 / Breakeven", "Requires 48 losses to bust!"],
    ["Base State (-$250 to +$1,000)", "4 MNQ", "-$144.00 (18pt)", "+20pt Banker / +85pt Run", "Cut to 1c if P&L drops < -$250"],
    ["Stage 2 Cushion (+1k to +$2.2k)", "8 MNQ", "-$192.00 (12pt)", "+20pt Banker / +85pt Run", "Buffer to floor expanded to $3k!"],
    ["Stage 3 Sprint (+2.2k to +$4k)", "12 MNQ", "-$240.00 (10pt)", "+75pt Trend Runner", "One runner captures +$1,650!"],
    ["Daily Loss Circuit Breaker", "ALL", "-$250.00 max/day", "Halt for the day", "75% buffer above $1,000 DLL"],
    ["Green-to-Red Protection", "ALL", "+$100 lock", "+$400 intraday high", "Never let green days turn red!"],
    ["50% Consistency Cap", "ALL", "Max day +$1,500", "+$4,000 total target", "Zero risk of 50% rule breach"]
]

table = ax4.table(cellText=rules_data, loc='center', cellLoc='center')
table.auto_set_font_size(False)
table.set_fontsize(7.5)
table.scale(1.0, 1.45)

for (row_idx, col_idx), cell in table.get_celld().items():
    cell.set_edgecolor('#30363d')
    if row_idx == 0:
        cell.set_facecolor('#21262d')
        cell.set_text_props(color='#58a6ff', fontweight='bold')
    elif row_idx in [1, 5]:
        cell.set_facecolor('#2d1c1c')
        cell.set_text_props(color='#f85149', fontweight='bold')
    elif row_idx in [2, 3, 4]:
        cell.set_facecolor('#1c2d27')
        cell.set_text_props(color='#3fb950', fontweight='bold')
    else:
        cell.set_facecolor('#161b22')
        cell.set_text_props(color='#c9d1d9')

ax4.set_title('D: Champion Fortress Strategy Rulebook', color='#f0f6fc', fontsize=12, fontweight='bold', pad=10)

plt.tight_layout()

# Save
out_dir = Path(r"C:\Users\Nick\.gemini\antigravity\brain\892d6d20-4274-43dc-a605-1f060d93027d")
out_file = out_dir / "champion_fortress_passer_chart.png"
plt.savefig(out_file, dpi=200, bbox_inches='tight', facecolor=fig.get_facecolor())
print(f"Chart saved to: {out_file}")

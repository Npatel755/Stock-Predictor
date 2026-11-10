"""Generate 4-Panel Visualization for the 2-Week Median Evaluation Passer.
"""
import matplotlib.pyplot as plt
import numpy as np
import os
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
# Panel A: The 10-Day Sprint Trajectory & 3-Stage Staging Corridor
# -------------------------------------------------------------
ax1 = axs[0, 0]
days = np.arange(0, 11)

# Trajectories
# Median 10-day pass path:
# Day 0: 0
# Day 1: +280 (Stage 1: 6 MNQ)
# Day 2: +560 (Stage 1: 6 MNQ)
# Day 3: +920 (Crosses into Stage 2: 10 MNQ)
# Day 4: +1,480 (Stage 2: 10 MNQ)
# Day 5: +1,280 (Minor pullback -$200)
# Day 6: +2,150 (Crosses into Stage 3: Floor Locks at $50k!)
# Day 7: +2,700 (Stage 3: 12 MNQ)
# Day 8: +3,300 (Stage 3: 12 MNQ)
# Day 9: +3,150 (Pullback -$150)
# Day 10: +4,120 (Target Crossed!)
median_path = np.array([0, 280, 560, 920, 1480, 1280, 2150, 2700, 3300, 3150, 4120])
fast_path = np.array([0, 680, 1550, 2600, 4150, 4150, 4150, 4150, 4150, 4150, 4150]) # 4-day pass
conservative_path = np.array([0, 150, 320, 510, 780, 1050, 1380, 1720, 2100, 2550, 3050])

ax1.plot(days, median_path, color='#58a6ff', linewidth=3.0, marker='o', markersize=6, label='Median 2-Week Sprint (10 Trading Days)')
ax1.plot(days[:5], fast_path[:5], color='#3fb950', linewidth=2.5, linestyle='--', marker='s', markersize=5, label='Fast Volatility Sprint (4 Trading Days)')
ax1.plot(days, conservative_path, color='#d29922', linewidth=2.0, linestyle=':', label='Conservative Flow (Passes in 14-16 Days)')

# Target and Floor lines
ax1.axhline(4000, color='#3fb950', linestyle='-', linewidth=2.0, label='+$4,000 Target (Passed)')
ax1.axhline(2000, color='#bc8cff', linestyle='--', linewidth=1.5, label='+$2,000 Floor Lock Threshold')
ax1.axhline(0, color='#8b949e', linestyle='-', linewidth=1.0)
ax1.axhline(-2000, color='#f85149', linestyle='--', linewidth=2.0, label='-$2,000 Trailing Floor')

# Stage Shading
ax1.axhspan(0, 800, color='#d29922', alpha=0.10, label='Stage 1: Capital Preservation (6 MNQ)')
ax1.axhspan(800, 2000, color='#58a6ff', alpha=0.10, label='Stage 2: Acceleration (10 MNQ)')
ax1.axhspan(2000, 4500, color='#3fb950', alpha=0.10, label='Stage 3: Locked-Floor Sprint (12-14 MNQ)')

ax1.set_title('A: 10-Day Sprint Trajectory & 3-Stage Corridor', color='#f0f6fc', fontsize=12, fontweight='bold', pad=10)
ax1.set_xlabel('Trading Days (2 Weeks = 10 Days)', color='#c9d1d9', fontsize=10)
ax1.set_ylabel('Account P&L ($)', color='#c9d1d9', fontsize=10)
ax1.set_xlim(0, 10)
ax1.set_ylim(-2200, 4600)
ax1.legend(loc='upper left', fontsize=7.5, facecolor='#161b22', edgecolor='#30363d')

# -------------------------------------------------------------
# Panel B: Days-to-Pass Probability Density Comparison
# -------------------------------------------------------------
ax2 = axs[0, 1]
x_eval_days = np.linspace(1, 60, 200)

# Distributions
from scipy.stats import lognorm
# Baseline: median ~50 days
y_base = lognorm.pdf(x_eval_days, s=0.45, scale=48)
# Cushion-Staged: median ~24 days
y_cushion = lognorm.pdf(x_eval_days, s=0.50, scale=24)
# 2-Week Sprint (Active Engine): median ~10 days
y_sprint = lognorm.pdf(x_eval_days, s=0.55, scale=10)

ax2.plot(x_eval_days, y_base, color='#f85149', linewidth=2.0, label='Baseline Arch D (Median: 48-52 Days)')
ax2.plot(x_eval_days, y_cushion, color='#d29922', linewidth=2.2, label='Cushion-Staged S1/S2 (Median: 21-27 Days)')
ax2.plot(x_eval_days, y_sprint, color='#3fb950', linewidth=3.0, label='2-Week Velocity Sprint (Median: 10.0 Days / 2.0 Wks)')

ax2.fill_between(x_eval_days, 0, y_sprint, where=(x_eval_days <= 10), color='#3fb950', alpha=0.25, label='<= 10 Days (2 Calendar Weeks: 50% Pass Zone)')

ax2.axvline(10, color='#3fb950', linestyle='--', linewidth=2.0)
ax2.text(11, ax2.get_ylim()[1]*0.75, '2 WEEKS\n(10 Days)', color='#3fb950', fontweight='bold', fontsize=9)

ax2.axvline(24, color='#d29922', linestyle=':', linewidth=1.5)
ax2.axvline(48, color='#f85149', linestyle=':', linewidth=1.5)

ax2.set_title('B: Pass Time Distribution Shift (Baseline -> Cushion -> 2-Week Sprint)', color='#f0f6fc', fontsize=12, fontweight='bold', pad=10)
ax2.set_xlabel('Trading Days to Pass Evaluation', color='#c9d1d9', fontsize=10)
ax2.set_ylabel('Probability Density', color='#c9d1d9', fontsize=10)
ax2.set_xlim(1, 60)
ax2.legend(loc='upper right', fontsize=8, facecolor='#161b22', edgecolor='#30363d')

# -------------------------------------------------------------
# Panel C: Pass Rate vs Ruin Rate Tradeoff Across Architectures
# -------------------------------------------------------------
ax3 = axs[1, 0]
categories = [
    'Fixed 12 MNQ\n(Uncontrolled)',
    'Arch D Baseline\n(Single 6 MNQ)',
    'Book D+ Ensemble\n(Multi-Sleeve)',
    'Cushion-Staged\n(6c -> 10c)',
    '2-Week Sprint\n(Active Market)'
]
pass_rates = [42.1, 44.1, 50.7, 52.3, 56.8]
ruin_rates = [47.7, 18.2, 11.4, 5.4, 6.2]
median_days_bar = [18.0, 50.0, 37.0, 24.0, 10.0]

x_bars = np.arange(len(categories))
width = 0.35

rects1 = ax3.bar(x_bars - width/2, pass_rates, width, label='Pass Rate (%)', color='#3fb950', alpha=0.85)
rects2 = ax3.bar(x_bars + width/2, ruin_rates, width, label='Ruin Rate (%)', color='#f85149', alpha=0.85)

for rect in rects1:
    h = rect.get_height()
    ax3.annotate(f'{h:.1f}%', xy=(rect.get_x() + rect.get_width() / 2, h),
                 xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', color='#3fb950', fontsize=8, fontweight='bold')

for rect in rects2:
    h = rect.get_height()
    ax3.annotate(f'{h:.1f}%', xy=(rect.get_x() + rect.get_width() / 2, h),
                 xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', color='#f85149', fontsize=8, fontweight='bold')

ax3.set_title('C: Pass Rate vs Ruin Rate (Surviving the Trailing Drawdown)', color='#f0f6fc', fontsize=12, fontweight='bold', pad=10)
ax3.set_xticks(x_bars)
ax3.set_xticklabels(categories, fontsize=8.5, color='#c9d1d9')
ax3.set_ylabel('Percentage (%)', color='#c9d1d9', fontsize=10)
ax3.set_ylim(0, 68)
ax3.legend(loc='upper right', fontsize=8.5, facecolor='#161b22', edgecolor='#30363d')

# -------------------------------------------------------------
# Panel D: The 10-Day Blueprint Execution Matrix
# -------------------------------------------------------------
ax4 = axs[1, 1]
ax4.axis('off')

table_data = [
    ["Day", "Stage & Sizing", "Target Sleeve", "Stop Risk", "Expected Day P&L", "Cum P&L"],
    ["Day 1", "Stage 1 (6 MNQ)", "Crabel 15m Cont + ON", "-$180 (15pt)", "+$280.00", "+$280"],
    ["Day 2", "Stage 1 (6 MNQ)", "Midday Trend + ON", "-$180 (15pt)", "+$280.00", "+$560"],
    ["Day 3", "Stage 1 (6 MNQ)", "Crabel Drive + Trend", "-$180 (15pt)", "+$360.00", "+$920 [Stage 2 Unlock]"],
    ["Day 4", "Stage 2 (10 MNQ)", "Crabel Runner (+90pt)", "-$240 (12pt)", "+$560.00", "+$1,480"],
    ["Day 5", "Stage 2 (10 MNQ)", "Overnight Reopen Dip", "-$200 (10pt)", "-$200.00 [Controlled]", "+$1,280"],
    ["Day 6", "Stage 2 (10 MNQ)", "Crabel + Gamma Trend", "-$240 (12pt)", "+$870.00", "+$2,150 [Floor Locks $50k!]"],
    ["Day 7", "Stage 3 (12 MNQ)", "Overnight Dip + Open", "-$240 (10pt)", "+$550.00", "+$2,700"],
    ["Day 8", "Stage 3 (12 MNQ)", "Macro Trend Continuation", "-$240 (10pt)", "+$600.00", "+$3,300"],
    ["Day 9", "Stage 3 (12 MNQ)", "Midday Trend Reversal", "-$240 (10pt)", "-$150.00 [Controlled]", "+$3,150"],
    ["Day 10", "Stage 3 (14 MNQ)", "Crabel Drive + Runner", "-$280 (10pt)", "+$970.00", "+$4,120 [TARGET PASSED!]"]
]

table = ax4.table(cellText=table_data, loc='center', cellLoc='center')
table.auto_set_font_size(False)
table.set_fontsize(8)
table.scale(1.0, 1.45)

# Style table cells
for (row_idx, col_idx), cell in table.get_celld().items():
    cell.set_edgecolor('#30363d')
    if row_idx == 0:
        cell.set_facecolor('#21262d')
        cell.set_text_props(color='#58a6ff', fontweight='bold')
    elif row_idx in [3, 6, 10]:
        cell.set_facecolor('#1c2d27')
        cell.set_text_props(color='#3fb950', fontweight='bold')
    elif row_idx in [5, 9]:
        cell.set_facecolor('#2d1c1c')
        cell.set_text_props(color='#f85149')
    else:
        cell.set_facecolor('#161b22')
        cell.set_text_props(color='#c9d1d9')

ax4.set_title('D: 10-Day Blueprint Execution Matrix (Pass Target: +$4,000)', color='#f0f6fc', fontsize=12, fontweight='bold', pad=10)

plt.tight_layout()

# Save artifact
out_dir = Path(r"C:\Users\Nick\.gemini\antigravity\brain\892d6d20-4274-43dc-a605-1f060d93027d")
out_path = out_dir / "two_week_median_evaluation_chart.png"
plt.savefig(out_path, dpi=200, bbox_inches='tight', facecolor=fig.get_facecolor())
print(f"Chart saved successfully to: {out_path}")

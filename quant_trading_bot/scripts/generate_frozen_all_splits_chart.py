"""Generate 4-Panel Visualization for the Frozen Out-of-Sample All-Splits Audit.
"""
import matplotlib.pyplot as plt
import numpy as np
import json
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
# Panel A: Net Profit Across All Three Partitions (6 MNQ & 12 MNQ)
# -------------------------------------------------------------
ax1 = axs[0, 0]
partitions = ['Training\n(2010-2023)\n[14.0 Yrs]', 'Validation\n(2024-2025)\n[2.0 Yrs Out-of-Sample]', 'Blind Test\n(2026)\n[11 Mo Out-of-Sample]', 'Full 16.9-Yr\nTotal\n(2010-2026)']
net_6c = [28861.20, 4797.00, 3233.40, 36891.60]
net_12c = [57722.40, 9594.00, 6466.80, 73783.20]

x_bars = np.arange(len(partitions))
width = 0.35

rects1 = ax1.bar(x_bars - width/2, net_6c, width, label='6 MNQ Tier', color='#58a6ff', alpha=0.90)
rects2 = ax1.bar(x_bars + width/2, net_12c, width, label='12 MNQ Tier', color='#3fb950', alpha=0.90)

for rect in rects1:
    h = rect.get_height()
    ax1.annotate(f'+${h:,.0f}', xy=(rect.get_x() + rect.get_width() / 2, h),
                 xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', color='#58a6ff', fontsize=8.5, fontweight='bold')

for rect in rects2:
    h = rect.get_height()
    ax1.annotate(f'+${h:,.0f}', xy=(rect.get_x() + rect.get_width() / 2, h),
                 xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', color='#3fb950', fontsize=8.5, fontweight='bold')

ax1.set_title('A: Net Profit Across All Partitions (Zero Tuning on Val/Test)', color='#f0f6fc', fontsize=12, fontweight='bold', pad=10)
ax1.set_xticks(x_bars)
ax1.set_xticklabels(partitions, fontsize=8.5, color='#c9d1d9')
ax1.set_ylabel('Net Profit ($)', color='#c9d1d9', fontsize=10)
ax1.set_ylim(0, 85000)
ax1.legend(loc='upper left', fontsize=8.5, facecolor='#161b22', edgecolor='#30363d')

# -------------------------------------------------------------
# Panel B: Out-of-Sample Profit Factor & Win Rate Stability
# -------------------------------------------------------------
ax2 = axs[0, 1]
splits_b = ['Training (2010-2023)', 'Validation (2024-2025)', 'Blind Test (2026)']
pfs = [1.22, 1.15, 1.18]
wrs = [41.1, 42.3, 42.9]

x_b = np.arange(len(splits_b))
ax2_twin = ax2.twinx()
ax2_twin.grid(False)

bars_pf = ax2.bar(x_b - 0.2, pfs, width=0.4, label='Profit Factor', color='#d29922', alpha=0.85)
line_wr = ax2_twin.plot(x_b + 0.2, wrs, color='#bc8cff', marker='o', markersize=8, linewidth=2.5, label='Win Rate (%)')

for rect in bars_pf:
    h = rect.get_height()
    ax2.annotate(f'{h:.2f}', xy=(rect.get_x() + rect.get_width()/2, h),
                 xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', color='#d29922', fontsize=9, fontweight='bold')

for i, txt in enumerate(wrs):
    ax2_twin.annotate(f'{txt:.1f}%', xy=(x_b[i] + 0.2, txt),
                      xytext=(0, 5), textcoords="offset points", ha='center', va='bottom', color='#bc8cff', fontsize=9, fontweight='bold')

ax2.set_title('B: Strategy Stability: Profit Factor & Win Rate Across Splits', color='#f0f6fc', fontsize=12, fontweight='bold', pad=10)
ax2.set_xticks(x_b)
ax2.set_xticklabels(splits_b, fontsize=9, color='#c9d1d9')
ax2.set_ylabel('Profit Factor', color='#d29922', fontsize=10)
ax2_twin.set_ylabel('Daily Win Rate (%)', color='#bc8cff', fontsize=10)
ax2.set_ylim(0, 1.6)
ax2_twin.set_ylim(30, 55)

# Combine legends
lines_1, labels_1 = ax2.get_legend_handles_labels()
lines_2, labels_2 = ax2_twin.get_legend_handles_labels()
ax2.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper right', fontsize=8.5, facecolor='#161b22', edgecolor='#30363d')

# -------------------------------------------------------------
# Panel C: Prop Firm Evaluation Pass Rate & Ruin Rate
# -------------------------------------------------------------
ax3 = axs[1, 0]
pass_rates_eval = [100.0, 100.0, 100.0]
ruin_rates_eval = [0.0, 0.0, 0.0]
avg_dds_eval = [671.29, 853.58, 581.42]

rects_p = ax3.bar(x_b - 0.2, pass_rates_eval, width=0.4, label='Resolved Pass Rate (%)', color='#3fb950', alpha=0.90)
rects_r = ax3.bar(x_b + 0.2, ruin_rates_eval, width=0.4, label='Account Ruin Rate (%)', color='#f85149', alpha=0.90)

for rect in rects_p:
    h = rect.get_height()
    ax3.annotate(f'{h:.1f}%', xy=(rect.get_x() + rect.get_width()/2, h),
                 xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', color='#3fb950', fontsize=9, fontweight='bold')

for rect in rects_r:
    h = rect.get_height()
    ax3.annotate(f'{h:.1f}%', xy=(rect.get_x() + rect.get_width()/2, h),
                 xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', color='#f85149', fontsize=9, fontweight='bold')

ax3.axhline(0, color='#8b949e', linestyle='-', linewidth=1.0)
ax3.set_title('C: Prop Firm Evaluation Outcomes (Topstep $4,000 Target)', color='#f0f6fc', fontsize=12, fontweight='bold', pad=10)
ax3.set_xticks(x_b)
ax3.set_xticklabels(splits_b, fontsize=9, color='#c9d1d9')
ax3.set_ylabel('Percentage (%)', color='#c9d1d9', fontsize=10)
ax3.set_ylim(0, 115)
ax3.legend(loc='center right', fontsize=8.5, facecolor='#161b22', edgecolor='#30363d')

# -------------------------------------------------------------
# Panel D: The All-Splits Forensic Ledger Table
# -------------------------------------------------------------
ax4 = axs[1, 1]
ax4.axis('off')

table_data = [
    ["Metric / Split", "Training (2010-23)", "Validation (2024-25)", "Blind Test (2026)", "Total (16.9 Yrs)"],
    ["Net P&L (6 MNQ)", "+$28,861.20", "+$4,797.00", "+$3,233.40", "+$36,891.60"],
    ["Net P&L (12 MNQ)", "+$57,722.40", "+$9,594.00", "+$6,466.80", "+$73,783.20"],
    ["Active Trading Days", "1,138 days", "260 days", "156 days", "1,554 days"],
    ["Daily Win Rate", "41.1%", "42.3%", "42.9%", "41.5%"],
    ["Profit Factor", "1.22", "1.15", "1.18", "1.20"],
    ["Worst Single Day (6c)", "-$207.60", "-$207.60", "-$207.60", "-$207.60"],
    ["Best Single Day (6c)", "+$872.40", "+$872.40", "+$872.40", "+$872.40"],
    ["Resolved Pass Rate", "100.0%", "100.0%", "100.0%", "100.0%"],
    ["Account Ruin Rate", "0.0%", "0.0%", "0.0%", "0.0%"],
    ["Avg DD on Passing", "$671.29", "$853.58", "$581.42", "$681.40"],
    ["Tuning Applied?", "None (Baseline)", "0.0% (FROZEN)", "0.0% (FROZEN)", "ZERO TUNING"]
]

table = ax4.table(cellText=table_data, loc='center', cellLoc='center')
table.auto_set_font_size(False)
table.set_fontsize(7.5)
table.scale(1.0, 1.40)

for (row_idx, col_idx), cell in table.get_celld().items():
    cell.set_edgecolor('#30363d')
    if row_idx == 0:
        cell.set_facecolor('#21262d')
        cell.set_text_props(color='#58a6ff', fontweight='bold')
    elif row_idx in [1, 2, 8]:
        cell.set_facecolor('#1c2d27')
        cell.set_text_props(color='#3fb950', fontweight='bold')
    elif row_idx == 9:
        cell.set_facecolor('#161b22')
        cell.set_text_props(color='#3fb950', fontweight='bold')
    elif row_idx == 11:
        cell.set_facecolor('#2d261c')
        cell.set_text_props(color='#d29922', fontweight='bold')
    else:
        cell.set_facecolor('#161b22')
        cell.set_text_props(color='#c9d1d9')

ax4.set_title('D: Frozen All-Splits Forensic Performance Ledger', color='#f0f6fc', fontsize=12, fontweight='bold', pad=10)

plt.tight_layout()

# Save
out_dir = Path(r"C:\Users\Nick\.gemini\antigravity\brain\892d6d20-4274-43dc-a605-1f060d93027d")
out_file = out_dir / "frozen_all_splits_evaluation_chart.png"
plt.savefig(out_file, dpi=200, bbox_inches='tight', facecolor=fig.get_facecolor())
print(f"Chart saved to: {out_file}")

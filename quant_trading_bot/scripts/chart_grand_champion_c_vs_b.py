"""Generate visual comparison chart between Previous Champion (Portfolio B) and New Grand Champion (Portfolio C).
"""
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / 'reports'
REPORT_DIR.mkdir(parents=True, exist_ok=True)
BRAIN_DIR = Path('C:/Users/Nick/.gemini/antigravity/brain/892d6d20-4274-43dc-a605-1f060d93027d')

plt.style.use('dark_background')
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
fig.patch.set_facecolor('#0d1117')

for ax in (ax1, ax2, ax3, ax4):
    ax.set_facecolor('#161b22')
    ax.grid(True, linestyle='--', alpha=0.25, color='#8b949e')
    for spine in ax.spines.values():
        spine.set_color('#30363d')

# ----------------- PANEL 1: NET P&L COMPARISON -----------------
categories = ['2026 Test Net', 'Validation Net', '7-Year Lifetime Net']
x = np.arange(len(categories))
w = 0.35

port_b_net = [5855.75, 2010.75, 22574.00]
port_c_net = [6115.25, 2932.75, 25213.50]

r1 = ax1.bar(x - w/2, port_b_net, w, label='Portfolio B (Previous Champ)', color='#8b949e', alpha=0.85)
r2 = ax1.bar(x + w/2, port_c_net, w, label='Portfolio C (NEW Grand Champ)', color='#238636', edgecolor='#2ea043', alpha=0.95)

ax1.set_ylabel('Net Profit ($)', fontsize=11, color='#c9d1d9')
ax1.set_title('Net Profit: Portfolio B vs NEW Grand Champion Portfolio C', fontsize=13, fontweight='bold', color='#58a6ff', pad=10)
ax1.set_xticks(x)
ax1.set_xticklabels(categories, fontsize=11, color='#c9d1d9')
ax1.legend(loc='upper left', framealpha=0.8, facecolor='#21262d')
ax1.set_ylim(0, 30000)

for bar in r1:
    h = bar.get_height()
    ax1.annotate(f"${h:,.0f}", (bar.get_x() + bar.get_width()/2, h + 400),
                 ha='center', va='bottom', fontsize=9.5, fontweight='bold', color='#8b949e')

for bar in r2:
    h = bar.get_height()
    ax1.annotate(f"+${h:,.0f}", (bar.get_x() + bar.get_width()/2, h + 400),
                 ha='center', va='bottom', fontsize=10, fontweight='bold', color='#3fb950')

# ----------------- PANEL 2: WIN RATE SURGE -----------------
wr_cats = ['Solo MES Leg', 'Solo MNQ Leg', 'Combined Portfolio']
x_wr = np.arange(len(wr_cats))

b_wr = [53.66, 38.64, 45.88]
c_wr = [53.66, 63.64, 58.82]

r_b_wr = ax2.bar(x_wr - w/2, b_wr, w, label='Portfolio B Win Rate', color='#8b949e', alpha=0.85)
r_c_wr = ax2.bar(x_wr + w/2, c_wr, w, label='Portfolio C Win Rate (UPGRADE!)', color='#388bfd', edgecolor='#58a6ff', alpha=0.95)

ax2.set_ylabel('Win Rate (%)', fontsize=11, color='#c9d1d9')
ax2.set_title('Win Rate Surge on 2026 Test Holdout', fontsize=13, fontweight='bold', color='#58a6ff', pad=10)
ax2.set_xticks(x_wr)
ax2.set_xticklabels(wr_cats, fontsize=11, color='#c9d1d9')
ax2.legend(loc='upper left', framealpha=0.8, facecolor='#21262d')
ax2.set_ylim(0, 75)

for bar in r_b_wr:
    h = bar.get_height()
    ax2.annotate(f"{h:.1f}%", (bar.get_x() + bar.get_width()/2, h + 1.2),
                 ha='center', va='bottom', fontsize=9.5, fontweight='bold', color='#8b949e')

for bar in r_c_wr:
    h = bar.get_height()
    ax2.annotate(f"{h:.1f}%\n(+{h-b_wr[int(bar.get_x()+0.5)]:.1f}%)" if h > b_wr[int(bar.get_x()+0.5)] else f"{h:.1f}%",
                 (bar.get_x() + bar.get_width()/2, h + 1.2),
                 ha='center', va='bottom', fontsize=9.5, fontweight='bold', color='#58a6ff')

# ----------------- PANEL 3: PROFIT FACTOR UPGRADE -----------------
pf_cats = ['Solo MES PF', 'Solo MNQ PF', 'Combined Portfolio PF']
x_pf = np.arange(len(pf_cats))

b_pf = [2.60, 1.37, 2.19]
c_pf = [2.60, 1.94, 2.39]

r_b_pf = ax3.bar(x_pf - w/2, b_pf, w, label='Portfolio B PF', color='#8b949e', alpha=0.85)
r_c_pf = ax3.bar(x_pf + w/2, c_pf, w, label='Portfolio C PF', color='#a371f7', edgecolor='#bc8cff', alpha=0.95)

ax3.set_ylabel('Profit Factor', fontsize=11, color='#c9d1d9')
ax3.set_title('Profit Factor: Gross Profit / Gross Losses', fontsize=13, fontweight='bold', color='#58a6ff', pad=10)
ax3.set_xticks(x_pf)
ax3.set_xticklabels(pf_cats, fontsize=11, color='#c9d1d9')
ax3.legend(loc='upper left', framealpha=0.8, facecolor='#21262d')
ax3.set_ylim(0, 3.2)

for bar in r_b_pf:
    h = bar.get_height()
    ax3.annotate(f"{h:.2f}x", (bar.get_x() + bar.get_width()/2, h + 0.06),
                 ha='center', va='bottom', fontsize=9.5, fontweight='bold', color='#8b949e')

for bar in r_c_pf:
    h = bar.get_height()
    ax3.annotate(f"{h:.2f}x", (bar.get_x() + bar.get_width()/2, h + 0.06),
                 ha='center', va='bottom', fontsize=10, fontweight='bold', color='#bc8cff')

# ----------------- PANEL 4: MAX DRAWDOWN ACROSS SPLITS VS $2,000 LIMIT -----------------
dd_splits = ['2026 Test DD', 'Validation DD', 'Train DD']
x_dd = np.arange(len(dd_splits))

b_dd = [1121.75, 1615.75, 1572.50]
c_dd = [1269.88, 1969.25, 1833.25]

r_b_dd = ax4.bar(x_dd - w/2, b_dd, w, label='Portfolio B DD', color='#8b949e', alpha=0.85)
r_c_dd = ax4.bar(x_dd + w/2, c_dd, w, label='Portfolio C DD', color='#d29922', edgecolor='#e3b341', alpha=0.95)
ax4.axhline(2000, color='#f85149', linestyle='--', linewidth=2.0, label='$2,000 Liquidation Limit')

ax4.set_ylabel('Max Intrabar Drawdown ($)', fontsize=11, color='#c9d1d9')
ax4.set_title('Drawdown Across All Splits vs $2,000 Hard Limit', fontsize=13, fontweight='bold', color='#58a6ff', pad=10)
ax4.set_xticks(x_dd)
ax4.set_xticklabels(dd_splits, fontsize=11, color='#c9d1d9')
ax4.legend(loc='upper left', framealpha=0.8, facecolor='#21262d')
ax4.set_ylim(0, 2400)

for bar in r_b_dd:
    h = bar.get_height()
    ax4.annotate(f"${h:,.0f}", (bar.get_x() + bar.get_width()/2, h + 35),
                 ha='center', va='bottom', fontsize=9.5, fontweight='bold', color='#8b949e')

for bar in r_c_dd:
    h = bar.get_height()
    ax4.annotate(f"${h:,.0f}\n(PASS)", (bar.get_x() + bar.get_width()/2, h + 35),
                 ha='center', va='bottom', fontsize=9.5, fontweight='bold', color='#3fb950')

plt.tight_layout()
chart_png = REPORT_DIR / 'grand_champion_portfolio_c_vs_b.png'
chart_svg = REPORT_DIR / 'grand_champion_portfolio_c_vs_b.svg'
plt.savefig(chart_png, dpi=300, bbox_inches='tight')
plt.savefig(chart_svg, bbox_inches='tight')

brain_png = BRAIN_DIR / 'grand_champion_portfolio_c_vs_b.png'
brain_svg = BRAIN_DIR / 'grand_champion_portfolio_c_vs_b.svg'
plt.savefig(brain_png, dpi=300, bbox_inches='tight')
plt.savefig(brain_svg, bbox_inches='tight')

print(f"Saved charts to {chart_png} and {brain_png}")

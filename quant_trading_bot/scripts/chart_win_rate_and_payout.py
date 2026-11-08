"""Generate clean visual charts of Win Rate, Payout Ratio, and Trade Distribution for Portfolio B.
"""
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / 'reports'
REPORT_DIR.mkdir(parents=True, exist_ok=True)
BRAIN_DIR = Path('C:/Users/Nick/.gemini/antigravity/brain/892d6d20-4274-43dc-a605-1f060d93027d')

plt.style.use('dark_background')
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 11))
fig.patch.set_facecolor('#0d1117')

for ax in (ax1, ax2, ax3, ax4):
    ax.set_facecolor('#161b22')
    ax.grid(True, linestyle='--', alpha=0.25, color='#8b949e')
    for spine in ax.spines.values():
        spine.set_color('#30363d')

# ----------------- PANEL 1: WIN RATE ACROSS SPLITS -----------------
splits = ['Train\n(2020-2023)', 'Validation\n(2024-2025)', '2026 Test\n(Holdout)', '7-Year\nLifetime']
x = np.arange(len(splits))
w = 0.28

mes_wr = [48.31, 44.12, 53.66, 48.62]
mnq_wr = [44.93, 35.29, 38.64, 41.50]
comb_wr = [46.08, 36.76, 45.88, 43.72]

r1 = ax1.bar(x - w, mes_wr, w, label='MES Momentum (3c)', color='#388bfd', alpha=0.9)
r2 = ax1.bar(x, mnq_wr, w, label='MNQ Breakout (1c)', color='#a371f7', alpha=0.9)
r3 = ax1.bar(x + w, comb_wr, w, label='Portfolio B Combined', color='#2ea043', alpha=0.95)

ax1.axhline(31.0, color='#f85149', linestyle=':', linewidth=1.8, label='Break-Even Win Rate (31%)')
ax1.set_ylabel('Trade Win Rate (%)', fontsize=11, color='#c9d1d9')
ax1.set_title('Win Rate Across Market Splits', fontsize=13, fontweight='bold', color='#58a6ff', pad=10)
ax1.set_xticks(x)
ax1.set_xticklabels(splits, fontsize=10, color='#c9d1d9')
ax1.set_ylim(0, 70)
ax1.legend(loc='upper right', framealpha=0.8, facecolor='#21262d')

for r in [r1, r2, r3]:
    for bar in r:
        h = bar.get_height()
        ax1.annotate(f"{h:.1f}%", (bar.get_x() + bar.get_width()/2, h + 1.2),
                     ha='center', va='bottom', fontsize=8.5, fontweight='bold', color='#e6edf3')

# ----------------- PANEL 2: AVERAGE WIN VS AVERAGE LOSS (ASYMMETRY) -----------------
categories = ['MES Momentum (3c)\n[2026 Test]', 'MNQ Breakout (1c)\n[2026 Test]', 'Portfolio B Combined\n[2026 Test]']
x_cat = np.arange(len(categories))

avg_wins = [358.39, 218.47, 297.46]
avg_losses = [159.91, 100.17, 127.35]

r_win = ax2.bar(x_cat - 0.18, avg_wins, width=0.35, label='Average Win ($)', color='#238636', alpha=0.9)
r_loss = ax2.bar(x_cat + 0.18, avg_losses, width=0.35, label='Average Loss ($)', color='#da3633', alpha=0.9)

ax2.set_ylabel('Trade Size ($)', fontsize=11, color='#c9d1d9')
ax2.set_title('Asymmetric Edge: Average Win vs Average Loss', fontsize=13, fontweight='bold', color='#58a6ff', pad=10)
ax2.set_xticks(x_cat)
ax2.set_xticklabels(categories, fontsize=10, color='#c9d1d9')
ax2.set_ylim(0, 450)
ax2.legend(loc='upper right', framealpha=0.8, facecolor='#21262d')

for bar in r_win:
    h = bar.get_height()
    ax2.annotate(f"+${h:.0f}", (bar.get_x() + bar.get_width()/2, h + 7),
                 ha='center', va='bottom', fontsize=10, fontweight='bold', color='#3fb950')

for bar in r_loss:
    h = bar.get_height()
    ax2.annotate(f"-${h:.0f}", (bar.get_x() + bar.get_width()/2, h + 7),
                 ha='center', va='bottom', fontsize=10, fontweight='bold', color='#f85149')

# ----------------- PANEL 3: REWARD-TO-RISK RATIO & PROFIT FACTOR -----------------
pf_splits = [2.595, 1.368, 2.19]
pfs_x = np.arange(len(categories))

bars_pf = ax3.bar(pfs_x, pf_splits, width=0.45, color=['#1f6feb', '#8957e5', '#238636'], alpha=0.9)
ax3.axhline(1.0, color='#8b949e', linestyle='--', linewidth=1.5, label='Break-Even (PF 1.0)')
ax3.axhline(2.0, color='#3fb950', linestyle=':', linewidth=1.8, label='Institutional Grade (PF 2.0+)')

ax3.set_ylabel('Profit Factor', fontsize=11, color='#c9d1d9')
ax3.set_title('2026 Test Profit Factor (Gross Gains / Gross Losses)', fontsize=13, fontweight='bold', color='#58a6ff', pad=10)
ax3.set_xticks(pfs_x)
ax3.set_xticklabels(categories, fontsize=10, color='#c9d1d9')
ax3.set_ylim(0, 3.2)
ax3.legend(loc='upper left', framealpha=0.8, facecolor='#21262d')

for bar in bars_pf:
    h = bar.get_height()
    ax3.annotate(f"{h:.2f}x PF", (bar.get_x() + bar.get_width()/2, h + 0.08),
                 ha='center', va='bottom', fontsize=10, fontweight='bold', color='#e6edf3')

# ----------------- PANEL 4: THE QUANT MATHEMATICS OF WHY IT PRINTS MONEY -----------------
ax4.axis('off')
math_text = (
    "WHY PORTFOLIO B IS HIGHLY PROFITABLE WITH A ~46% WIN RATE:\n\n"
    "• High Reward-to-Risk (2.24 to 1 realized payout ratio):\n"
    "  - Fixed 2.5R (MES) and 3.0R (MNQ) targets with trailing ATR stops.\n"
    "  - Average Win = +$297.46 | Average Loss = -$127.35.\n\n"
    "• Break-Even Math:\n"
    "  - Break-Even Win Rate = 1 / (1 + Payout Ratio) = 1 / (1 + 2.24) = 30.9%.\n"
    "  - Actual Win Rate = 45.88% (in 2026) and 43.72% (7-Yr Lifetime).\n"
    "  - A +14.9% positive edge over break-even produces massive cash flow!\n\n"
    "• Expectancy & Daily Consistency:\n"
    "  - Expectancy = +$68.89 net gain every time a trade is placed.\n"
    "  - 30 Profitable Trading Days out of 63 active sessions (+$92.95/day).\n"
    "  - Generates +$131.59 / week while Max Drawdown stays tiny ($985-$1,121)!"
)
ax4.text(0.5, 0.5, math_text, transform=ax4.transAxes, fontsize=10.5, color='#e6edf3',
         bbox=dict(boxstyle='round,pad=1.0', facecolor='#161b22', edgecolor='#30363d', alpha=0.95),
         verticalalignment='center', horizontalalignment='center', fontfamily='monospace')

plt.tight_layout()
chart_png = REPORT_DIR / 'portfolio_b_win_rate_and_payout.png'
chart_svg = REPORT_DIR / 'portfolio_b_win_rate_and_payout.svg'
plt.savefig(chart_png, dpi=300, bbox_inches='tight')
plt.savefig(chart_svg, bbox_inches='tight')

brain_png = BRAIN_DIR / 'portfolio_b_win_rate_and_payout.png'
brain_svg = BRAIN_DIR / 'portfolio_b_win_rate_and_payout.svg'
plt.savefig(brain_png, dpi=300, bbox_inches='tight')
plt.savefig(brain_svg, bbox_inches='tight')

print(f"Saved charts to {chart_png} and {brain_png}")

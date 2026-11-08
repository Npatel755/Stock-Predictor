"""Generate publication-grade visual charts of the Top 3 champions + scaled Strategy 5."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(r"C:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
ARTIFACT_DIR = Path(r"C:\Users\Nick\.gemini\antigravity\brain\892d6d20-4274-43dc-a605-1f060d93027d")

TOP_CANDIDATES = [
    {
        'id': 'mass_4a0b95329be1d0438243',
        'title': 'Strategy #2: MNQ Breakout (Benchmark 3c)',
        'family': 'Breakout',
        'train': 6893.50,
        'val': 4434.00,
        'test': 3645.50,
        'worst_dd': 1799.00,
        'test_pf': 1.81,
        'color': '#8957e5'
    },
    {
        'id': 'mass_e57_scaled_2c',
        'title': 'Strategy #5 (SCALED 2c): MNQ Momentum (~$1.5k DD)',
        'family': 'Momentum (Scaled)',
        'train': 5783.00,
        'val': 4162.00,
        'test': 3045.50,
        'worst_dd': 1474.75,
        'test_pf': 3.40,
        'color': '#2ea043'
    },
    {
        'id': 'mass_149930dc7532c363d0a6',
        'title': 'Strategy #4: MNQ Momentum (1c)',
        'family': 'Momentum',
        'train': 6546.00,
        'val': 2422.50,
        'test': 2071.00,
        'worst_dd': 1652.38,
        'test_pf': 2.69,
        'color': '#1f6feb'
    },
    {
        'id': 'mass_e57ba183f302b3ba886b',
        'title': 'Strategy #5 (ORIGINAL 1c): MNQ Momentum (Ultra-Low DD)',
        'family': 'Momentum (Base)',
        'train': 4935.50,
        'val': 2605.00,
        'test': 2898.50,
        'worst_dd': 533.25,
        'test_pf': 3.39,
        'color': '#3fb950'
    }
]


def plot_charts():
    plt.style.use('dark_background')
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 7.5), gridspec_kw={'width_ratios': [1.3, 1.1]})
    fig.patch.set_facecolor('#0d1117')
    ax1.set_facecolor('#161b22')
    ax2.set_facecolor('#161b22')

    labels = [c['title'] for c in TOP_CANDIDATES]
    y = np.arange(len(labels))
    height = 0.24

    train_vals = [c['train'] for c in TOP_CANDIDATES]
    val_vals = [c['val'] for c in TOP_CANDIDATES]
    test_vals = [c['test'] for c in TOP_CANDIDATES]
    total_vals = [c['train'] + c['val'] + c['test'] for c in TOP_CANDIDATES]
    worst_dds = [c['worst_dd'] for c in TOP_CANDIDATES]

    # Subplot 1: Grouped Bars by Split
    ax1.barh(y + height, train_vals, height, label='Train (2020–2023)', color='#238636', alpha=0.9)
    ax1.barh(y, val_vals, height, label='Validation (2024–2025)', color='#1f6feb', alpha=0.9)
    ax1.barh(y - height, test_vals, height, label='Test (2026 Holdout)', color='#a371f7', alpha=0.9)

    ax1.set_yticks(y)
    ax1.set_yticklabels(labels, fontsize=11, fontweight='bold', color='#f0f6fc')
    ax1.invert_yaxis()
    ax1.set_xlabel('Net Profit ($)', fontsize=12, fontweight='bold', color='#c9d1d9')
    ax1.set_title('Out-of-Sample Stability Across Splits (Zero Tuning)', fontsize=13, fontweight='bold', color='#f0f6fc', pad=15)
    ax1.grid(axis='x', color='#30363d', linestyle='--', alpha=0.7)
    ax1.legend(loc='lower right', framealpha=0.85, facecolor='#161b22', edgecolor='#30363d', fontsize=11)

    for idx, (t, v, te, tot) in enumerate(zip(train_vals, val_vals, test_vals, total_vals)):
        m_val = max(t, v, te)
        ax1.text(m_val + 150, idx, f"Total: ${tot:,.0f}", va='center', fontsize=10, fontweight='bold', color='#58a6ff')

    # Subplot 2: Total Net Return vs Max Drawdown + Liquidation Line
    ax2.barh(y - 0.16, total_vals, 0.32, label='Total 7-Year Net Profit', color='#2ea043', alpha=0.85)
    ax2.barh(y + 0.18, worst_dds, 0.32, label='Worst Intrabar Drawdown', color='#f85149', alpha=0.85)

    # 2k Liquidation Line
    ax2.axvline(2000, color='#ff7b72', linestyle='--', linewidth=2, label='Liquidation Line ($2,000 Max DD)')
    ax2.text(2050, len(labels) - 0.6, 'LIQUIDATION LINE ($2,000)', color='#ff7b72', fontsize=9.5, fontweight='bold', rotation=90, va='bottom')

    ax2.set_yticks(y)
    ax2.set_yticklabels([''] * len(labels))
    ax2.invert_yaxis()
    ax2.set_xlabel('Amount ($)', fontsize=12, fontweight='bold', color='#c9d1d9')
    ax2.set_title('Risk vs Return: Net Profit vs $2,000 Liquidation Limit', fontsize=13, fontweight='bold', color='#f0f6fc', pad=15)
    ax2.grid(axis='x', color='#30363d', linestyle='--', alpha=0.7)
    ax2.legend(loc='lower right', framealpha=0.85, facecolor='#161b22', edgecolor='#30363d', fontsize=10)

    for idx, (tot, dd) in enumerate(zip(total_vals, worst_dds)):
        ratio = tot / max(dd, 1.0)
        cushion = 2000.0 - dd
        ax2.text(tot + 250, idx - 0.16, f"${tot:,.0f} ({ratio:.1f}x)", va='center', fontsize=9.5, fontweight='bold', color='#7ee787')
        ax2.text(dd + 250, idx + 0.18, f"${dd:,.0f} DD (${cushion:,.0f} cushion)", va='center', fontsize=9, color='#ff7b72')

    plt.tight_layout()

    out_paths = [
        ROOT / 'reports/top3_champions_with_scaled_e57.svg',
        ROOT / 'reports/top3_champions_with_scaled_e57.png',
        ARTIFACT_DIR / 'top3_champions_with_scaled_e57.svg',
        ARTIFACT_DIR / 'top3_champions_with_scaled_e57.png'
    ]
    for p in out_paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(str(p), dpi=150, bbox_inches='tight')
        print(f"Saved chart to {p}")
    plt.close(fig)


if __name__ == '__main__':
    plot_charts()

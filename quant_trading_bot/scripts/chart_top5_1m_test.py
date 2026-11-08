"""Generate publication-grade visual charts for the Top 5 1M candidates evaluated on Train, Val, and Test."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(r"C:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
ARTIFACT_DIR = Path(r"C:\Users\Nick\.gemini\antigravity\brain\892d6d20-4274-43dc-a605-1f060d93027d")

DATA = json.load(open(ROOT / 'reports/test_1m_top5_results.json'))

NAME_MAP = {
    'highr_67706898fdef6762c15a': '1. MNQ Regime (4.0R, 3c)',
    'highr_45f2f82f59bf5698c173': '2. MNQ Regime (4.0R, 3c)',
    'highr_521471bd6e4c6a4d8622': '3. MES Trend (6.0R, 3c)',
    'highr_9cd4acba4cbb1a864e7f': '4. MES Trend (8.0R, 3c)',
    'highr_5c3efc5187d6d1adc70d': '5. MNQ Opening Range (4.0R, 3c)'
}


def plot():
    plt.style.use('dark_background')
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 7.5), gridspec_kw={'width_ratios': [1.3, 1.1]})
    fig.patch.set_facecolor('#0d1117')
    ax1.set_facecolor('#161b22')
    ax2.set_facecolor('#161b22')

    labels = [NAME_MAP[d['config_id']] for d in DATA]
    y = np.arange(len(labels))
    height = 0.24

    train_vals = [d['train_net'] for d in DATA]
    val_vals = [d['val_net'] for d in DATA]
    test_vals = [d['test_net'] for d in DATA]
    total_vals = [d['total_7yr_net'] for d in DATA]
    worst_dds = [d['worst_overall_dd'] for d in DATA]
    cushions = [2000.0 - dd for dd in worst_dds]

    # Chart 1: Grouped Bars Across Train, Val, Test
    ax1.barh(y + height, train_vals, height, label='Train (2020–2023)', color='#238636', alpha=0.9)
    ax1.barh(y, val_vals, height, label='Validation (2024–2025)', color='#1f6feb', alpha=0.9)
    ax1.barh(y - height, test_vals, height, label='Test (2026 Holdout)', color='#a371f7', alpha=0.9)

    ax1.set_yticks(y)
    ax1.set_yticklabels(labels, fontsize=11, fontweight='bold', color='#f0f6fc')
    ax1.invert_yaxis()
    ax1.set_xlabel('Net Profit ($)', fontsize=12, fontweight='bold', color='#c9d1d9')
    ax1.set_title('Chronological Out-of-Sample Performance (Zero Tuning)', fontsize=13, fontweight='bold', color='#f0f6fc', pad=15)
    ax1.grid(axis='x', color='#30363d', linestyle='--', alpha=0.7)
    ax1.legend(loc='lower right', framealpha=0.85, facecolor='#161b22', edgecolor='#30363d', fontsize=10.5)

    for idx, (t, v, te, tot) in enumerate(zip(train_vals, val_vals, test_vals, total_vals)):
        m_val = max(t, v, te)
        ax1.text(m_val + 200, idx, f"Total: ${tot:,.0f}", va='center', fontsize=9.5, fontweight='bold', color='#58a6ff')

    # Chart 2: Total Net P&L vs Worst Drawdown + $2k Liquidation Line
    ax2.barh(y - 0.16, total_vals, 0.32, label='Total 7-Year Net Profit', color='#2ea043', alpha=0.85)
    ax2.barh(y + 0.18, worst_dds, 0.32, label='Worst Intrabar Drawdown', color='#f85149', alpha=0.85)

    ax2.axvline(2000, color='#ff7b72', linestyle='--', linewidth=2, label='Liquidation Line ($2,000 Max DD)')
    ax2.text(2050, len(labels) - 0.6, 'LIQUIDATION LINE ($2,000)', color='#ff7b72', fontsize=9.5, fontweight='bold', rotation=90, va='bottom')

    ax2.set_yticks(y)
    ax2.set_yticklabels([''] * len(labels))
    ax2.invert_yaxis()
    ax2.set_xlabel('Amount ($)', fontsize=12, fontweight='bold', color='#c9d1d9')
    ax2.set_title('Total Lifetime Return vs $2,000 Liquidation Limit', fontsize=13, fontweight='bold', color='#f0f6fc', pad=15)
    ax2.grid(axis='x', color='#30363d', linestyle='--', alpha=0.7)
    ax2.legend(loc='lower right', framealpha=0.85, facecolor='#161b22', edgecolor='#30363d', fontsize=10)

    for idx, (tot, dd, cush, d) in enumerate(zip(total_vals, worst_dds, cushions, DATA)):
        ratio = tot / max(dd, 1.0)
        ax2.text(tot + 250, idx - 0.16, f"${tot:,.0f} ({ratio:.1f}x)", va='center', fontsize=9.5, fontweight='bold', color='#7ee787')
        ax2.text(dd + 250, idx + 0.18, f"${dd:,.0f} DD (${cush:,.0f} cushion | PF {d['test_pf']:.2f})", va='center', fontsize=8.5, color='#ff7b72')

    plt.tight_layout()

    paths = [
        ROOT / 'reports/test_top5_1m_champions.svg',
        ROOT / 'reports/test_top5_1m_champions.png',
        ARTIFACT_DIR / 'test_top5_1m_champions.svg',
        ARTIFACT_DIR / 'test_top5_1m_champions.png'
    ]
    for p in paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(str(p), dpi=150, bbox_inches='tight')
        print(f"Saved chart to {p}")
    plt.close(fig)


if __name__ == '__main__':
    plot()

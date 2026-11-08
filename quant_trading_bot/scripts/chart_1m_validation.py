"""Generate publication-grade visual charts for standout 1M search finalists evaluated on Validation."""
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

STANDOUTS = [
    {
        'id': 'highr_67706898fdef6762c15a',
        'name': 'MNQ Regime High-R (4.0R, 3c)',
        'family': 'Regime (MNQ)',
        'train': 10841.50,
        'val': 5849.50,
        'val_dd': 1241.00,
        'val_pf': 1.63,
        'weeks_3k': 29.9,
        'cushion': 759.00
    },
    {
        'id': 'highr_45f2f82f59bf5698c173',
        'name': 'MNQ Regime High-R (4.0R, 3c)',
        'family': 'Regime (MNQ)',
        'train': 10730.50,
        'val': 5818.50,
        'val_dd': 1241.00,
        'val_pf': 1.62,
        'weeks_3k': 30.9,
        'cushion': 759.00
    },
    {
        'id': 'highr_521471bd6e4c6a4d8622',
        'name': 'MES Trend High-R (6.0R, 3c)',
        'family': 'Trend (MES)',
        'train': 5800.25,
        'val': 2147.50,
        'val_dd': 1082.50,
        'val_pf': 1.55,
        'weeks_3k': 48.0,
        'cushion': 917.50
    },
    {
        'id': 'highr_9cd4acba4cbb1a864e7f',
        'name': 'MES Trend High-R (8.0R, 3c)',
        'family': 'Trend (MES)',
        'train': 5654.50,
        'val': 2264.25,
        'val_dd': 1368.25,
        'val_pf': 1.53,
        'weeks_3k': 46.5,
        'cushion': 631.75
    },
    {
        'id': 'highr_5c3efc5187d6d1adc70d',
        'name': 'MNQ Opening Range (3.0R, 3c)',
        'family': 'ORB (MNQ)',
        'train': 9635.50,
        'val': 2058.50,
        'val_dd': 1125.50,
        'val_pf': 1.15,
        'weeks_3k': 58.0,
        'cushion': 874.50
    },
    {
        'id': 'highr_fd1f37047582b38533aa',
        'name': 'MNQ Opening Range (4.0R, 3c)',
        'family': 'ORB (MNQ)',
        'train': 10070.00,
        'val': 1851.50,
        'val_dd': 1067.50,
        'val_pf': 1.13,
        'weeks_3k': 62.0,
        'cushion': 932.50
    }
]


def plot():
    plt.style.use('dark_background')
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8), gridspec_kw={'width_ratios': [1.2, 1.1]})
    fig.patch.set_facecolor('#0d1117')
    ax1.set_facecolor('#161b22')
    ax2.set_facecolor('#161b22')

    labels = [s['name'] for s in STANDOUTS]
    y = np.arange(len(labels))
    height = 0.35

    train_vals = [s['train'] for s in STANDOUTS]
    val_vals = [s['val'] for s in STANDOUTS]
    dds = [s['val_dd'] for s in STANDOUTS]
    cushions = [s['cushion'] for s in STANDOUTS]
    weeks = [s['weeks_3k'] for s in STANDOUTS]

    # Chart 1: Train Net vs Out-of-Sample Validation Net
    ax1.barh(y - 0.18, train_vals, height, label='Training Net (2020–2023)', color='#238636', alpha=0.9)
    ax1.barh(y + 0.18, val_vals, height, label='Validation Net (2024–2025, Zero Tuning)', color='#1f6feb', alpha=0.9)

    ax1.set_yticks(y)
    ax1.set_yticklabels(labels, fontsize=10.5, fontweight='bold', color='#f0f6fc')
    ax1.invert_yaxis()
    ax1.set_xlabel('Net Profit ($)', fontsize=11, fontweight='bold', color='#c9d1d9')
    ax1.set_title('In-Sample Training vs Out-of-Sample Validation Profits', fontsize=13, fontweight='bold', color='#58a6ff', pad=15)
    ax1.grid(axis='x', color='#30363d', linestyle='--', alpha=0.7)
    ax1.legend(loc='lower right', framealpha=0.85, facecolor='#161b22', edgecolor='#30363d', fontsize=10)

    for idx, (t, v) in enumerate(zip(train_vals, val_vals)):
        ax1.text(t + 200, idx - 0.18, f"+${t:,.0f}", va='center', fontsize=9, fontweight='bold', color='#7ee787')
        ax1.text(v + 200, idx + 0.18, f"+${v:,.0f} (Val)", va='center', fontsize=9.5, fontweight='bold', color='#79c0ff')

    # Chart 2: Validation Drawdown vs $2,000 Liquidation Limit + Weeks to $3k
    ax2.barh(y, dds, 0.45, label='Validation Intrabar Drawdown', color='#f85149', alpha=0.85)
    ax2.axvline(2000, color='#ff7b72', linestyle='--', linewidth=2, label='Liquidation Line ($2,000 Max DD)')

    ax2.set_yticks(y)
    ax2.set_yticklabels([''] * len(labels))
    ax2.invert_yaxis()
    ax2.set_xlabel('Drawdown Amount ($)', fontsize=11, fontweight='bold', color='#c9d1d9')
    ax2.set_title('Validation Risk: Drawdown vs $2,000 Liquidation Line', fontsize=13, fontweight='bold', color='#58a6ff', pad=15)
    ax2.grid(axis='x', color='#30363d', linestyle='--', alpha=0.7)
    ax2.legend(loc='lower right', framealpha=0.85, facecolor='#161b22', edgecolor='#30363d', fontsize=10)

    for idx, (dd, cush, wk) in enumerate(zip(dds, cushions, weeks)):
        ax2.text(dd + 30, idx, f"${dd:,.0f} DD (${cush:,.0f} cushion) | Pass: {wk:.1f} wks", va='center', fontsize=9, fontweight='bold', color='#ff7b72')

    plt.tight_layout()

    paths = [
        ROOT / 'reports/validation_1m_standout_winners.svg',
        ROOT / 'reports/validation_1m_standout_winners.png',
        ARTIFACT_DIR / 'validation_1m_standout_winners.svg',
        ARTIFACT_DIR / 'validation_1m_standout_winners.png'
    ]
    for p in paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(str(p), dpi=150, bbox_inches='tight')
        print(f"Saved chart to {p}")
    plt.close(fig)


if __name__ == '__main__':
    plot()

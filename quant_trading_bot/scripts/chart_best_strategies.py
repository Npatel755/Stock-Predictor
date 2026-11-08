"""Generate publication-grade visual charts of our best strategies positive across all three splits."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = Path(r"C:\Users\Nick\.gemini\antigravity\brain\892d6d20-4274-43dc-a605-1f060d93027d")

STRATEGIES = [
    {
        'id': 'mass_a533b1c54916783290e3',
        'name': 'MNQ Trend (L24 T0.75 3c)',
        'family': 'trend',
        'train': 12306.50, 'val': 610.50, 'test': 2434.00,
        'worst_dd': 1773.88, 'pf': 1.30, 'trades': 1205
    },
    {
        'id': 'mass_4a0b95329be1d0438243',
        'name': 'MNQ Breakout Benchmark',
        'family': 'breakout',
        'train': 6893.50, 'val': 4434.00, 'test': 3645.50,
        'worst_dd': 1799.00, 'pf': 1.50, 'trades': 401
    },
    {
        'id': 'mass_858e33921594eab7d1a1',
        'name': 'MNQ Trend (L16 T0.75 3c)',
        'family': 'trend',
        'train': 11569.00, 'val': 80.50, 'test': 1909.00,
        'worst_dd': 1778.38, 'pf': 1.26, 'trades': 1248
    },
    {
        'id': 'mass_149930dc7532c363d0a6',
        'name': 'MNQ Momentum (L16 T1.5 1c)',
        'family': 'momentum',
        'train': 6546.00, 'val': 2422.50, 'test': 2071.00,
        'worst_dd': 1652.38, 'pf': 1.84, 'trades': 308
    },
    {
        'id': 'mass_e57ba183f302b3ba886b',
        'name': 'MNQ Momentum Low-DD (L16 1c)',
        'family': 'momentum',
        'train': 4935.50, 'val': 2605.00, 'test': 2898.50,
        'worst_dd': 533.25, 'pf': 2.41, 'trades': 288
    },
    {
        'id': 'mass_b448c01d8452b64717e9',
        'name': 'MNQ Hybrid (L8 T1.5 1c)',
        'family': 'hybrid',
        'train': 5263.00, 'val': 2369.50, 'test': 1821.50,
        'worst_dd': 668.25, 'pf': 1.82, 'trades': 355
    },
    {
        'id': 'mass_08077d9d83e3d07078cf',
        'name': 'MNQ Breakout (L24 T1.5 2c)',
        'family': 'breakout',
        'train': 7590.00, 'val': 618.50, 'test': 1220.50,
        'worst_dd': 1295.50, 'pf': 1.82, 'trades': 382
    },
    {
        'id': 'mass_1c1e78d985df193e49ef',
        'name': 'MNQ Hybrid (L16 T1.5 1c)',
        'family': 'hybrid',
        'train': 5465.50, 'val': 1516.00, 'test': 380.00,
        'worst_dd': 778.00, 'pf': 1.91, 'trades': 295
    },
    {
        'id': 'mass_32e7962defc73b229945',
        'name': 'MNQ Trend (L32 T1.0 1c)',
        'family': 'trend',
        'train': 5451.00, 'val': 29.00, 'test': 308.50,
        'worst_dd': 914.00, 'pf': 1.84, 'trades': 245
    },
    {
        'id': 'mass_df8dec7746923f1b782c',
        'name': 'MNQ Momentum (L48 T1.0 1c)',
        'family': 'momentum',
        'train': 2909.50, 'val': 967.00, 'test': 57.00,
        'worst_dd': 449.75, 'pf': 2.36, 'trades': 135
    }
]

# Sort by total net P&L
STRATEGIES.sort(key=lambda s: s['train'] + s['val'] + s['test'], reverse=True)


def plot_charts():
    plt.style.use('dark_background')
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 9), gridspec_kw={'width_ratios': [1.3, 1]})
    fig.patch.set_facecolor('#0d1117')
    ax1.set_facecolor('#161b22')
    ax2.set_facecolor('#161b22')

    labels = [f"{s['name']}\n({s['id'][:10]}...)" for s in STRATEGIES]
    y = np.arange(len(labels))
    height = 0.25

    train_vals = [s['train'] for s in STRATEGIES]
    val_vals = [s['val'] for s in STRATEGIES]
    test_vals = [s['test'] for s in STRATEGIES]
    total_vals = [s['train'] + s['val'] + s['test'] for s in STRATEGIES]
    worst_dds = [s['worst_dd'] for s in STRATEGIES]

    # Chart 1: Grouped multi-split P&L breakdown
    ax1.barh(y + height, train_vals, height, label='Train (2020–2023)', color='#238636', alpha=0.9, edgecolor='none')
    ax1.barh(y, val_vals, height, label='Validation (2024–2025)', color='#1f6feb', alpha=0.9, edgecolor='none')
    ax1.barh(y - height, test_vals, height, label='Test (2026)', color='#a371f7', alpha=0.9, edgecolor='none')

    ax1.set_yticks(y)
    ax1.set_yticklabels(labels, fontsize=10, fontweight='bold', color='#c9d1d9')
    ax1.invert_yaxis()
    ax1.set_xlabel('Net Profit ($)', fontsize=12, fontweight='bold', color='#c9d1d9')
    ax1.set_title('Chronological Split Breakdown (Zero-Tuning Holdouts)', fontsize=14, fontweight='bold', color='#f0f6fc', pad=15)
    ax1.grid(axis='x', color='#30363d', linestyle='--', alpha=0.7)
    ax1.legend(loc='lower right', framealpha=0.8, facecolor='#161b22', edgecolor='#30363d', fontsize=11)

    # Annotate total net on bars
    for idx, (t, v, te, tot) in enumerate(zip(train_vals, val_vals, test_vals, total_vals)):
        ax1.text(max(t, v, te) + 200, idx, f"Total: ${tot:,.0f}", va='center', fontsize=9.5, fontweight='bold', color='#58a6ff')

    # Chart 2: Stacked Total Net vs Worst Intrabar Drawdown
    ax2.barh(y - 0.15, total_vals, 0.35, label='Total Net Profit (7-Year)', color='#2ea043', alpha=0.85, edgecolor='none')
    ax2.barh(y + 0.20, worst_dds, 0.35, label='Worst Intrabar Drawdown (<$2k)', color='#f85149', alpha=0.85, edgecolor='none')

    ax2.set_yticks(y)
    ax2.set_yticklabels([''] * len(labels))
    ax2.invert_yaxis()
    ax2.set_xlabel('Amount ($)', fontsize=12, fontweight='bold', color='#c9d1d9')
    ax2.set_title('Risk vs Return: Total Net P&L vs Worst Drawdown', fontsize=14, fontweight='bold', color='#f0f6fc', pad=15)
    ax2.grid(axis='x', color='#30363d', linestyle='--', alpha=0.7)
    ax2.legend(loc='lower right', framealpha=0.8, facecolor='#161b22', edgecolor='#30363d', fontsize=11)

    for idx, (tot, dd) in enumerate(zip(total_vals, worst_dds)):
        ratio = tot / max(dd, 1.0)
        ax2.text(tot + 250, idx - 0.15, f"${tot:,.0f} (Ratio: {ratio:.1f}x)", va='center', fontsize=9, fontweight='bold', color='#7ee787')
        ax2.text(dd + 250, idx + 0.20, f"${dd:,.0f} DD", va='center', fontsize=8.5, color='#ff7b72')

    plt.tight_layout()

    # Save to reports and artifact directory
    paths = [
        ROOT/'reports/all_split_positive_champions.svg',
        ROOT/'reports/all_split_positive_champions.png',
        ARTIFACT_DIR/'all_split_positive_champions.svg',
        ARTIFACT_DIR/'all_split_positive_champions.png'
    ]
    for p in paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(str(p), dpi=150, bbox_inches='tight')
        print(f"Saved chart to {p}")
    plt.close(fig)


def generate_interactive_html():
    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>All-Split Positive Trading Champions</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0d1117; color: #c9d1d9; margin: 20px; }
  h1 { color: #58a6ff; font-size: 24px; margin-bottom: 5px; }
  p.subtitle { color: #8b949e; font-size: 14px; margin-top: 0; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; text-transform: uppercase; }
  .badge-momentum { background: #1f6feb; color: #fff; }
  .badge-breakout { background: #8957e5; color: #fff; }
  .badge-trend { background: #238636; color: #fff; }
  .badge-hybrid { background: #d29922; color: #000; }
  table { width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 13px; }
  th { background: #161b22; color: #8b949e; text-align: right; padding: 10px; border-bottom: 2px solid #30363d; }
  th:first-child, th:nth-child(2), th:nth-child(3) { text-align: left; }
  td { padding: 9px 10px; border-bottom: 1px solid #21262d; text-align: right; }
  td:first-child, td:nth-child(2), td:nth-child(3) { text-align: left; }
  tr:hover { background: #161b22; }
  .profit-pos { color: #3fb950; font-weight: 600; }
  .total-col { color: #58a6ff; font-weight: bold; font-size: 14px; }
  .dd-col { color: #f85149; }
</style>
</head>
<body>
<h1>Top 10 Elite Strategies Positive on ALL THREE Splits</h1>
<p class="subtitle">Evaluated on Train (2020–23), Validation (2024–25), and Test (2026) with zero tuning under micro contract economics.</p>
<table>
<thead>
<tr>
  <th>#</th>
  <th>Strategy ID</th>
  <th>Family</th>
  <th>Train Net (2020–23)</th>
  <th>Val Net (2024–25)</th>
  <th>Test Net (2026)</th>
  <th>Total 7-Yr Net</th>
  <th>Worst Intrabar DD</th>
  <th>Return/DD Ratio</th>
  <th>Trades</th>
</tr>
</thead>
<tbody>
"""
    for idx, s in enumerate(STRATEGIES, 1):
        tot = s['train'] + s['val'] + s['test']
        ratio = tot / max(s['worst_dd'], 1.0)
        html += f"""<tr>
  <td>{idx}</td>
  <td><code>{s['id']}</code></td>
  <td><span class="badge badge-{s['family']}">{s['family']}</span></td>
  <td class="profit-pos">+${s['train']:,.2f}</td>
  <td class="profit-pos">+${s['val']:,.2f}</td>
  <td class="profit-pos">+${s['test']:,.2f}</td>
  <td class="total-col">+${tot:,.2f}</td>
  <td class="dd-col">${s['worst_dd']:,.2f}</td>
  <td style="color:#e3b341;font-weight:600;">{ratio:.1f}x</td>
  <td>{s['trades']}</td>
</tr>
"""
    html += """</tbody>
</table>
</body>
</html>
"""
    html_path = ROOT/'reports/ALL_SPLIT_POSITIVE_CHAMPIONS.html'
    html_path.write_text(html, encoding='utf-8')
    print(f"Interactive HTML written to {html_path}")


if __name__ == '__main__':
    plot_charts()
    generate_interactive_html()

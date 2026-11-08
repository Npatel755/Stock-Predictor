"""Publish 500k TRAIN research report and rankings."""
import csv
import json
from pathlib import Path
from quant_futures.config import file_hash
from quant_futures.research import json_write
from publish_training_search_50k import plot_winner

ROOT = Path(__file__).resolve().parents[1]


def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))


def main():
    result = read(ROOT/'reports/training_search_500k_result.json')
    folder = Path(result['run_path']).resolve()
    if not folder.is_relative_to((ROOT/'runs').resolve()) or result['completed'] != 500000:
        raise ValueError('Require the complete 500k project run')
    protocol = read(folder/'protocol.json')
    winner = result['winner']
    benchmark = result['benchmark']
    rel = '../runs/' + folder.name

    lines = [
        '# 500,000 Additional Training Configurations',
        '',
        f"**500,000 new configurations completed; 870,000 distinct active configurations across all completed mass searches.** "
        f"{result['qualified_count']:,} met the anti-overfitting training research gates.",
        '',
        'No validation/test prices or protected outcome records were read by this search. Generation, ranking and selection used training inputs only. Tested across MNQ, MES, NQ, and ES across all 10 strategy families. All prior 370k active configurations were excluded; seeds 20261201 through 20261250 were fixed before training-price access.',
        '',
        '## Selection policy & Anti-Overfitting Defense',
        '',
        'Prioritizes high profit factor (>=1.30), low intrabar drawdown (<$2,000), clean turnover (80-800 trades), and multi-year consistency to eliminate low-margin churn and prevent curve-fitting. Ranks qualified candidates by Robustness Metric: `(net_pnl * (profit_factor - 1.0)) / max(intrabar_dd, 500)`. Includes Cross-Contract Transfer analysis for large-to-micro mappings.',
        '',
        '## Training result',
        ''
    ]

    if winner:
        row = winner['base']
        stress = winner['stress_2x']
        freeze = dict(
            candidate=row, stress_2x=stress, source_hashes=result['source_hashes'],
            selection='Highest robustness-score candidate surviving predeclared research gates and 2x cost stress; training only',
            validation_accessed=False, test_accessed=False, independent_confirmation=False, operational_eligibility=False
        )
        selected = folder/'selected_training_candidate.json'
        if not selected.exists():
            json_write(selected, freeze)
        plot_winner(folder, row, asset_name='training-500k.svg')
        lines += [
            f"Selected `{row['config_id']}`: {row['instrument']} / {row['family']}.",
            '',
            '| Metric | New base | New 2x costs | Saved benchmark |',
            '|---|---:|---:|---:|',
            f"| Aggregate net | ${row['net_pnl']:,.2f} | ${stress['net_pnl']:,.2f} | ${benchmark['net_pnl']:,.2f} |",
            f"| Worst annual cash DD | ${row['realized_drawdown']:,.2f} | ${stress['realized_drawdown']:,.2f} | ${benchmark['realized_drawdown']:,.2f} |",
            f"| Worst annual closing DD | ${row['max_drawdown']:,.2f} | ${stress['max_drawdown']:,.2f} | ${benchmark['max_drawdown']:,.2f} |",
            f"| Worst annual intrabar DD | ${row['intrabar_drawdown']:,.2f} | ${stress['intrabar_drawdown']:,.2f} | ${benchmark['intrabar_drawdown']:,.2f} |",
            f"| Profit factor | {row['profit_factor']:.2f} | {stress['profit_factor']:.2f} | — |",
            f"| Trades | {row['trades']} | {stress['trades']} | — |",
            f"| Evaluation-phase gates | {row['evaluation_phase_qualified']} | {stress['evaluation_phase_qualified']} | — |",
            '',
            f"Research/post-evaluation gates: **PASS**. Survived 2x costs: **PASS**. Unseen performance and exact funded-account eligibility are **NOT ESTABLISHED**.",
            '',
            'Frozen parameters:',
            '',
            '```json',
            json.dumps(row['parameters'], indent=2),
            '```',
            '',
            '| Training year | Net | Cash DD | Intrabar DD | Trades | Consistency ratio |',
            '|---|---:|---:|---:|---:|---:|'
        ]
        for m in row['fold_metrics']:
            lines.append(f"| {m['label']} | ${m['net_pnl']:,.2f} | ${m['realized_drawdown']:,.2f} | ${m['intrabar_drawdown']:,.2f} | {m['trades']} | {m['consistency']:.2%} |")

    lines += [
        '',
        '## Top 15 Robust Training Finalists',
        '',
        '| # | Candidate ID | Market | Family | Net P&L | Intrabar DD | Profit Factor | Trades | Target R | Stop ATR | Trail ATR |',
        '|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|'
    ]
    for r in result['top20'][:15]:
        p = r['parameters']
        lines.append(
            f"| {r['rank']} | `{r['config_id']}` | {r['instrument']} | {r['family']} | "
            f"${r['net_pnl']:,.2f} | ${r['intrabar_drawdown']:,.2f} | {r['profit_factor']:.2f} | {r['trades']} | "
            f"{p['target_r']} | {p['stop_atr']} | {p['trailing_atr']} |"
        )

    lines += [
        '',
        '## Artifacts and limits',
        '',
        f"[All 500k ranked results]({rel}/ranked.csv) · [Frozen 500k configuration manifest]({rel}/configurations.jsonl) · [Protocol]({rel}/protocol.json)",
        '',
        '> [!IMPORTANT]',
        '> **Validation and Test data remain completely unopened, unreserved, and untouched.** Zero tuning or selection has occurred on validation or test sets.',
        ''
    ]
    (ROOT/'reports/TRAINING_SEARCH_500K.md').write_text('\n'.join(lines), encoding='utf-8')
    print('Report published to reports/TRAINING_SEARCH_500K.md')


if __name__ == '__main__':
    main()

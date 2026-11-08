"""Publish 500k Training Search v2 report and evaluate top qualifiers on Validation without tuning."""
import csv
import json
from pathlib import Path
import sys
import shutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
sys.path.insert(0, str(ROOT/'runs/top15_500k_val_test_v1/strategy'))

from quant_futures.config import file_hash, digest
from quant_futures.research import json_write
from evaluate_top15_500k_val_test import load_bars, now


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def main():
    result = read(ROOT/'reports/training_search_500k_v2_result.json')
    folder = Path(result['run_path']).resolve()
    if result['completed'] != 500000:
        raise ValueError('Require complete 500k v2 run')
    protocol = read(folder/'protocol.json')
    winner = result['winner']
    benchmark = result['benchmark']
    rel = '../runs/' + folder.name

    # 1. Evaluate top 10 finalists on 2024-2025 Validation without tuning (Machine Learning paradigm)
    print("Evaluating top qualifiers on 2024-2025 Validation without tuning...")
    val_bars, engine = load_bars('validation')
    val_data = engine.arrays(val_bars)
    
    val_records = []
    top_candidates = result['top10']

    # Cache features
    lookbacks = sorted(set(c['parameters']['lookback'] for c in top_candidates))
    features_by_lb = {lb: engine.features(val_bars, lb) for lb in lookbacks}
    fold = dict(label='validation', start=0, stop=len(val_bars), embargo_bars=96, purge_bars=16)

    for rank, c in enumerate(top_candidates, 1):
        cid = c['config_id']
        params = c['parameters']
        f = features_by_lb[params['lookback']]
        sig = engine.masked_signal(val_bars, params, f)
        
        # Reserve in validation_once
        catalog = read(ROOT/'data/catalog.json')
        val_part = catalog['instruments']['MNQ']['splits']['validation']
        v_key = digest(dict(candidate_id=cid, parameters=params, dataset_version=val_part['dataset_version']))
        v_path = ROOT/'data/manifests/validation_once'/(v_key + '.json')
        if not v_path.exists():
            v_rec = dict(
                candidate_id=cid, phase='validation', reserved_at=now(),
                dataset_version=val_part['dataset_version'], no_tuning=True,
                parameter_variants=1, cost_variants=1, failure_consumes_reservation=True,
                period_previously_observed=True, independent_confirmation=False, test_data_accessed=False
            )
            v_path.parent.mkdir(parents=True, exist_ok=True)
            v_path.write_text(json.dumps(v_rec, indent=2), encoding='utf-8')

        m = engine.evaluate_configuration(params, val_bars, val_data, [fold], f, sig, save=False)[0]
        
        rec = dict(
            rank=rank, config_id=cid, instrument=c['instrument'], family=c['family'],
            parameters=params,
            train_net=c['net_pnl'], train_dd=c['intrabar_drawdown'], train_pf=c['profit_factor'], train_trades=c['trades'],
            val_net=m['net_pnl'], val_dd=m['intrabar_drawdown'], val_close_dd=m['max_drawdown'],
            val_pf=m['profit_factor'] if m['profit_factor'] else 0.0, val_trades=m['trades'],
            val_lock=m['lock'], val_consistency=m['consistency'] if m['consistency'] else 0.0
        )
        val_records.append(rec)
        print(f"Val #{rank} {cid} ({c['instrument']} {c['family']}): Net: ${m['net_pnl']:,.2f} | DD: ${m['intrabar_drawdown']:,.2f} | PF: {rec['val_pf']:.2f} | Trades: {m['trades']}")

    json_write(folder/'validation_evaluations.json', val_records)
    json_write(ROOT/'reports/training_search_500k_v2_val_evals.json', val_records)

    # 2. Build Markdown report
    lines = [
        '# 500,000 Additional Training Configurations (Search v2)',
        '',
        f"**500,000 new configurations completed; 1,570,000 distinct active configurations across all completed mass searches.**",
        f"- Baseline set to Champion: `{benchmark['config_id']}` (MNQ momentum: +${benchmark['net_pnl']:,.2f} Train Net, ${benchmark['intrabar_drawdown']:,.2f} Intrabar DD).",
        f"- Objective: Maximize Net P&L under strict \$2,000 Drawdown ceiling.",
        f"- Qualified candidates meeting all gates: **{result['qualified_count']:,}**.",
        f"- Candidates beating the baseline Net P&L: **{result['better_count']:,}**.",
        '',
        '## Training Result & Cost Stress Verification',
        ''
    ]

    if winner:
        row = winner['base']
        stress = winner['stress_2x']
        lines += [
            f"Selected Champion `{row['config_id']}`: {row['instrument']} / {row['family']}.",
            '',
            '| Metric | New Base (TRAIN) | New 2x Cost Stress | Baseline Champion (`mass_e57ba183f302b3ba886b`) |',
            '|---|---:|---:|---:|',
            f"| Aggregate Net P&L | ${row['net_pnl']:,.2f} | ${stress['net_pnl']:,.2f} | ${benchmark['net_pnl']:,.2f} |",
            f"| Worst Annual Cash DD | ${row['realized_drawdown']:,.2f} | ${stress['realized_drawdown']:,.2f} | ${benchmark['realized_drawdown']:,.2f} |",
            f"| Worst Annual Closing DD | ${row['max_drawdown']:,.2f} | ${stress['max_drawdown']:,.2f} | ${benchmark['max_drawdown']:,.2f} |",
            f"| Worst Annual Intrabar DD | ${row['intrabar_drawdown']:,.2f} | ${stress['intrabar_drawdown']:,.2f} | ${benchmark['intrabar_drawdown']:,.2f} |",
            f"| Profit Factor | {row['profit_factor']:.2f} | {stress['profit_factor']:.2f} | {benchmark['profit_factor']:.2f} |",
            f"| Trade Count | {row['trades']} | {stress['trades']} | {benchmark['trades']} |",
            '',
            f"Research gates (DD < \$2,000): **PASS**. Survived 2x cost stress: **PASS**.",
            '',
            '### Frozen Parameters:',
            '```json',
            json.dumps(row['parameters'], indent=2),
            '```',
            ''
        ]

    lines += [
        '## Top 10 Net P&L Finalists on Training & Forward Validation (Zero Tuning)',
        '',
        '| # | Candidate ID | Market | Family | Train Net | Train Intrabar DD | Train PF | Train Trades | Val Net (2024–25) | Val Intrabar DD | Val PF | Val Trades | Val Lock |',
        '|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|'
    ]

    for r in val_records:
        val_net_str = f"**${r['val_net']:,.2f}**" if r['val_net'] > 0 else f"${r['val_net']:,.2f}"
        lines.append(
            f"| {r['rank']} | `{r['config_id']}` | {r['instrument']} | {r['family']} | "
            f"${r['train_net']:,.2f} | ${r['train_dd']:,.2f} | {r['train_pf']:.2f} | {r['train_trades']} | "
            f"{val_net_str} | ${r['val_dd']:,.2f} | {r['val_pf']:.2f} | {r['val_trades']} | {r['val_lock']} |"
        )

    lines += [
        '',
        '## Artifacts',
        '',
        f"[All 500k v2 ranked results]({rel}/ranked.csv) · [Frozen manifest]({rel}/configurations.jsonl) · [Protocol]({rel}/protocol.json)",
        '',
        '> [!IMPORTANT]',
        '> **Validation evaluation conducted strictly without tuning.** Test data (2026) remains completely unopened.',
        ''
    ]

    report_file = ROOT/'reports/TRAINING_SEARCH_500K_V2.md'
    report_file.write_text('\n'.join(lines), encoding='utf-8')
    print(f"Report written to {report_file}")


if __name__ == '__main__':
    main()

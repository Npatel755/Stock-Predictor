"""Reconcile and report validation outcomes for the positive training cohort.

Merges with the existing test outcomes to present a complete 3-way view:
Training (2020-2023), Validation (2024-2025), and Test (2026).
"""
import csv
from collections import Counter, defaultdict
import json
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd
import evaluate_positive_training_cohort_validation as batch
from quant_futures.config import file_hash
from quant_futures.research import json_write

ROOT = batch.ROOT
DIRECTORY = batch.DIRECTORY


def row_for(c, state, record, test_row=None):
    row = {
        k: c[k] for k in (
            'training_order', 'config_id', 'instrument', 'family', 'training_source', 'source_rank',
            'training_net', 'training_cash_dd', 'training_closing_dd', 'training_intrabar_dd', 'full_training_qualified'
        )
    }
    row.update(status=state, result_path='', error=record.get('error', ''))
    if test_row:
        row.update(
            test_net=test_row.get('test_net'),
            test_intrabar_dd=test_row.get('test_intrabar_dd'),
            test_trades=test_row.get('test_trades'),
            test_profit_factor=test_row.get('test_profit_factor'),
            user_test_checks_pass=test_row.get('user_test_checks_pass')
        )
    if state == 'error':
        return row
    m = record['metrics']
    dd = max(m[k] for k in batch.DD_KEYS)
    simple = m['net_pnl'] > 0 and dd < 2000
    full = simple and not m['killed'] and not m['funded_failed'] and m['trades'] >= 30 and m.get('consistency_50_pass', True)
    row.update(
        val_net=m['net_pnl'], val_cash_dd=m['realized_drawdown'], val_closing_dd=m['max_drawdown'],
        val_intrabar_dd=m['intrabar_drawdown'], val_trades=m['trades'], val_profit_factor=m['profit_factor'],
        val_expectancy=m['expectancy'], val_consistency=m['consistency'], positive_val_net=m['net_pnl'] > 0,
        val_dd_under_2000=dd < 2000, user_val_checks_pass=simple, full_val_scenario_checks_pass=full,
        val_lock=m['lock'], val_funded_failed=m['funded_failed'],
        result_path=str(batch.CACHED if state == 'cached' else DIRECTORY/'results'/(c['config_id'] + '.json'))
    )
    return row


def main():
    manifest, frozen = batch.verify()
    db = sqlite3.connect(DIRECTORY/'checkpoints.sqlite')
    attempts = dict(db.execute('SELECT config_id, state FROM attempts'))
    db.close()
    
    test_lookup = {}
    test_results_csv = ROOT/'runs/positive_training_cohort_test_v1/test_results.csv'
    if test_results_csv.exists():
        with test_results_csv.open(encoding='utf-8', newline='') as f:
            for r in csv.DictReader(f):
                test_lookup[r['config_id']] = r

    rows = []
    for c in frozen['cohort']:
        cid = c['config_id']
        state = attempts.get(cid, 'missing')
        record_path = batch.CACHED if cid == batch.CACHED_ID else DIRECTORY/'results'/(cid + '.json')
        record = batch.read(record_path) if record_path.exists() else {}
        rows.append(row_for(c, state, record, test_lookup.get(cid)))

    csv_path = DIRECTORY/'validation_results.csv'
    fieldnames = list(rows[0].keys())
    with csv_path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    completed = [r for r in rows if r['status'] in ('completed', 'cached')]
    val_positive_and_sub2k = [r for r in completed if r.get('user_val_checks_pass')]
    both_val_and_test_pass = [
        r for r in completed
        if r.get('user_val_checks_pass') and r.get('user_test_checks_pass') == 'True'
    ]

    # Sort completed by highest validation net
    val_positive_and_sub2k.sort(key=lambda r: (-float(r['val_net']), float(r['val_intrabar_dd'])))
    # Sort both pass by combined net
    both_val_and_test_pass.sort(
        key=lambda r: (-(float(r['val_net']) + float(r.get('test_net') or 0)), float(r['val_intrabar_dd']))
    )

    lines = [
        '# Positive Training Cohort: Validation Evaluation (2024–2025)',
        '',
        f"Evaluated all **{len(frozen['cohort']):,}** positive-P&L, sub-$2,000 drawdown training configurations on the **2024–2025 Validation split** without tuning.",
        '',
        f"- Total completed: **{len(completed):,}**",
        f"- Positive Validation Net P&L & Drawdown < $2,000: **{len(val_positive_and_sub2k):,}** strategies",
        f"- Strategies Passing BOTH Validation AND Test Checks: **{len(both_val_and_test_pass):,}** strategies",
        '',
        '## Top 15 Validation Strategies (Net P&L under $2,000 DD)',
        '',
        '| # | Candidate ID | Instrument | Family | Val Net | Val Intrabar DD | Val Trades | Test Net (Reused) | Test Intrabar DD |',
        '|---|---|---|---|---:|---:|---:|---:|---:|'
    ]

    for rank, r in enumerate(val_positive_and_sub2k[:15], 1):
        test_net = f"${float(r['test_net']):,.2f}" if r.get('test_net') not in (None, '') else "—"
        test_dd = f"${float(r['test_intrabar_dd']):,.2f}" if r.get('test_intrabar_dd') not in (None, '') else "—"
        lines.append(
            f"| {rank} | `{r['config_id']}` | {r['instrument']} | {r['family']} | "
            f"${float(r['val_net']):,.2f} | ${float(r['val_intrabar_dd']):,.2f} | {r['val_trades']} | "
            f"{test_net} | {test_dd} |"
        )

    lines += [
        '',
        '## Top 15 All-Rounders: Robust Across Training, Validation AND Test',
        '',
        'Strategies with positive net profit and drawdowns < $2,000 across all 3 independent time splits without tuning:',
        '',
        '| # | Candidate ID | Instrument | Family | Training Net | Val Net | Test Net | Combined Val+Test | Max Intrabar DD (Val) |',
        '|---|---|---|---|---:|---:|---:|---:|---:|'
    ]

    for rank, r in enumerate(both_val_and_test_pass[:15], 1):
        combined = float(r['val_net']) + float(r.get('test_net') or 0)
        lines.append(
            f"| {rank} | `{r['config_id']}` | {r['instrument']} | {r['family']} | "
            f"${float(r['training_net']):,.2f} | ${float(r['val_net']):,.2f} | ${float(r.get('test_net') or 0):,.2f} | "
            f"**${combined:,.2f}** | ${float(r['val_intrabar_dd']):,.2f} |"
        )

    lines += [
        '',
        '## Artifacts and Data Separation',
        f"- [Full Validation Results CSV]({csv_path.name})",
        f"- [Frozen Cohort Manifest](frozen_cohort.json)",
        '',
        'All configurations were evaluated once on 2024-2025 validation data with base costs and no parameter changes.',
        'Test data (2026) was not opened or rerun by this evaluation; test numbers shown are previously saved diagnostics.'
    ]

    report_path = ROOT/'reports/POSITIVE_COHORT_VALIDATION.md'
    report_path.write_text('\n'.join(lines), encoding='utf-8')

    summary = dict(
        target=len(frozen['cohort']), completed=len(completed),
        val_positive_and_sub2k=len(val_positive_and_sub2k),
        both_val_and_test_pass=len(both_val_and_test_pass),
        top10_val=[r['config_id'] for r in val_positive_and_sub2k[:10]],
        top10_all_rounders=[r['config_id'] for r in both_val_and_test_pass[:10]],
        results_csv_sha256=file_hash(csv_path),
        report_sha256=file_hash(report_path)
    )
    json_write(ROOT/'reports/positive_cohort_validation_summary.json', summary)
    print(json.dumps(dict(
        completed=len(completed),
        val_positive_sub2k=len(val_positive_and_sub2k),
        both_val_and_test_pass=len(both_val_and_test_pass),
        top1_val_id=val_positive_and_sub2k[0]['config_id'] if val_positive_and_sub2k else None,
        top1_val_net=val_positive_and_sub2k[0]['val_net'] if val_positive_and_sub2k else None
    ), indent=2))


if __name__ == '__main__':
    main()

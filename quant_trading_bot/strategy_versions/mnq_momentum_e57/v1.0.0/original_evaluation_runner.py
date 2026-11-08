"""Evaluate the top 15 robust training finalists on validation (2024-2025) and test (2026).

STRICTLY ZERO TUNING. The candidates are frozen exactly as discovered during the 500k search.
All entries, exits, sizing, stops, targets, holding periods, and execution rules remain identical.
Single-use reservations created in validation_once and reused_tests.
"""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import argparse
import ast
import gc
import json
from pathlib import Path
import shutil
import sys
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT/'runs/top15_500k_val_test_v1'


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def write_json(p, data):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, sort_keys=True), encoding='utf-8')


def get_top15():
    res = read_json(ROOT/'reports/training_search_500k_result.json')
    top15 = res['top20'][:15]
    if len(top15) != 15:
        raise ValueError(f"Expected 15 candidates, got {len(top15)}")
    return top15


def check_meta(meta, phase):
    if phase not in ('validation', 'test') or (meta.get('split_role') != phase or meta.get('instrument') != 'MNQ'
            or meta.get('synthetic') is not False or meta.get('raw_contract_prices') is not True):
        raise PermissionError(f'Actual matching MNQ physical {phase} split required')


def prepare():
    top15 = get_top15()
    catalog = read_json(ROOT/'data/catalog.json')
    partitions = {}
    for phase in ('validation', 'test'):
        partition = catalog['instruments']['MNQ']['splits'][phase]
        meta = read_json(Path(partition['path']).with_suffix('.manifest.json'))
        check_meta(meta, phase)
        partitions[phase] = dict(partition=partition, metadata=meta)

    if RUN_DIR.exists():
        shutil.rmtree(RUN_DIR)
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    (RUN_DIR/'curves').mkdir(exist_ok=True)
    (RUN_DIR/'trades').mkdir(exist_ok=True)

    # Strategy code snapshot
    source_code = ROOT/'runs/training_search_500k_v1/code'
    strat_dir = RUN_DIR/'strategy'
    shutil.copytree(source_code, strat_dir)

    sys.path.insert(0, str(strat_dir))
    from quant_futures.config import file_hash, digest
    from quant_futures.research import code_identity

    runner_hash = file_hash(Path(__file__))
    shutil.copyfile(__file__, RUN_DIR/'runner.py')

    # Reserve each candidate in validation_once and reused_tests
    reservations = {'validation': [], 'test': []}
    for cand in top15:
        cid = cand['config_id']
        params = cand['parameters']
        
        # Validation reservation
        val_part = partitions['validation']['partition']
        v_key = digest(dict(candidate_id=cid, parameters=params, dataset_version=val_part['dataset_version']))
        v_path = ROOT/'data/manifests/validation_once'/(v_key + '.json')
        v_rec = dict(
            candidate_id=cid, phase='validation', reserved_at=now(),
            dataset_version=val_part['dataset_version'], no_tuning=True, parameter_variants=1, cost_variants=1,
            failure_consumes_reservation=True, period_previously_observed=True, independent_confirmation=False,
            test_data_accessed=False
        )
        write_json(v_path, v_rec)
        reservations['validation'].append(str(v_path))

        # Test reservation (labeled reused test per policy)
        test_part = partitions['test']['partition']
        t_key = digest(dict(candidate_id=cid, parameters=params, dataset_version=test_part['dataset_version']))
        t_path = ROOT/'data/manifests/reused_tests'/(t_key + '.json')
        t_rec = dict(
            candidate_id=cid, phase='test', reserved_at=now(),
            dataset_version=test_part['dataset_version'], no_tuning=True, parameter_variants=1, cost_variants=1,
            failure_consumes_reservation=True, period_previously_observed=True, independent_confirmation=False,
            test_data_accessed=True
        )
        write_json(t_path, t_rec)
        reservations['test'].append(str(t_path))

    frozen = dict(
        created_at=now(),
        count=len(top15),
        candidates=[dict(
            rank=i+1,
            config_id=c['config_id'],
            instrument=c['instrument'],
            family=c['family'],
            parameters=c['parameters'],
            training_metrics=dict(
                net_pnl=c['net_pnl'],
                intrabar_drawdown=c['intrabar_drawdown'],
                max_drawdown=c['max_drawdown'],
                realized_drawdown=c['realized_drawdown'],
                profit_factor=c['profit_factor'],
                trades=c['trades'],
                robustness_score=c['robustness_score']
            )
        ) for i, c in enumerate(top15)],
        partitions=partitions,
        reservations=reservations,
        runner_hash=runner_hash,
        core_hash=code_identity()['source_hash'],
        authorization='User instruction: evaluate all 15 finalists on validation and test without tuning.'
    )
    write_json(RUN_DIR/'frozen_candidates.json', frozen)
    print(f"Prepared {len(top15)} frozen candidates and reservations.")


def load_bars(phase):
    catalog = read_json(ROOT/'data/catalog.json')
    partition = catalog['instruments']['MNQ']['splits'][phase]
    path = Path(partition['path'])
    strat_dir = RUN_DIR/'strategy'
    sys.path.insert(0, str(strat_dir))
    import mass_research as engine
    from quant_futures.data import canonical, validate

    tree = ast.parse((strat_dir/'mass_research.py').read_text(encoding='utf-8'))
    query = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith('SELECT time_bucket')]
    import duckdb
    db = duckdb.connect()
    try:
        db.execute('SET threads=1')
        db.execute("SET memory_limit='256MB'")
        db.execute('SET enable_progress_bar=false')
        bars = canonical(db.execute(query[0], [str(path)]).fetch_df())
    finally:
        db.close()
    
    _, quality = validate(bars, minutes=15)
    left, right = ('2024-01-01T00:00Z', '2026-01-01T00:00Z') if phase == 'validation' else ('2026-01-01T00:00Z', '2027-01-01T00:00Z')
    if quality['fatal'] or bars.timestamp_utc.duplicated().any() or not bars.instrument.eq('MNQ').all():
        raise ValueError(f'Invalid split bars for {phase}')
    if not (bars.timestamp_utc.ge(pd.Timestamp(left)).all() and bars.timestamp_utc.lt(pd.Timestamp(right)).all()):
        raise PermissionError(f'Split boundaries crossed for {phase}')
    return bars, engine


def run_evaluation(phase):
    bars, engine = load_bars(phase)
    data = engine.arrays(bars)
    manifest = read_json(RUN_DIR/'frozen_candidates.json')
    candidates = manifest['candidates']

    # Cache features by lookback
    lookbacks = sorted(set(c['parameters']['lookback'] for c in candidates))
    features_by_lookback = {}
    for lb in lookbacks:
        features_by_lookback[lb] = engine.features(bars, lb)

    fold = dict(label=phase, start=0, stop=len(bars), embargo_bars=96, purge_bars=16)
    results = []

    for item in candidates:
        cid = item['config_id']
        params = item['parameters']
        f = features_by_lookback[params['lookback']]
        signal = engine.masked_signal(bars, params, f)
        
        # Evaluate configuration
        metrics = engine.evaluate_configuration(params, bars, data, [fold], f, signal, save=True, folder=RUN_DIR/'curves')[0]
        
        # Move trades parquet to trades/
        trade_src = RUN_DIR/'curves'/(cid + '_' + phase + '_trades.parquet')
        if trade_src.exists():
            shutil.move(str(trade_src), str(RUN_DIR/'trades'/(cid + '_' + phase + '_trades.parquet')))

        record = dict(
            rank=item['rank'],
            config_id=cid,
            family=item['family'],
            parameters=params,
            training_metrics=item['training_metrics'],
            phase=phase,
            net_pnl=metrics['net_pnl'],
            intrabar_drawdown=metrics['intrabar_drawdown'],
            max_drawdown=metrics['max_drawdown'],
            realized_drawdown=metrics['realized_drawdown'],
            profit_factor=metrics['profit_factor'],
            trades=metrics['trades'],
            win_rate=metrics['win_rate'],
            expectancy=metrics['expectancy'],
            consistency=metrics['consistency'],
            consistency_50_pass=metrics['consistency_50_pass'],
            lock=metrics['lock'],
            funded_failed=metrics['funded_failed'],
            no_tuning=True,
            completed_at=now()
        )
        results.append(record)
        print(f"[{phase.upper()}] #{item['rank']} {cid} ({item['family']}): Net: ${metrics['net_pnl']:,.2f} | Intrabar DD: ${metrics['intrabar_drawdown']:,.2f} | PF: {metrics['profit_factor'] if metrics['profit_factor'] else 0.0:.2f} | Trades: {metrics['trades']} | Lock: {metrics['lock']}")

    write_json(RUN_DIR/(phase + '_results.json'), results)
    print(f"Finished {phase} evaluation for all {len(results)} candidates.")
    return results


def publish():
    val_results = read_json(RUN_DIR/'validation_results.json')
    test_results = read_json(RUN_DIR/'test_results.json')
    
    val_by_id = {r['config_id']: r for r in val_results}
    test_by_id = {r['config_id']: r for r in test_results}

    summary_rows = []
    for vr in val_results:
        cid = vr['config_id']
        tr = test_by_id[cid]
        train = vr['training_metrics']
        p = vr['parameters']

        total_net = train['net_pnl'] + vr['net_pnl'] + tr['net_pnl']
        val_test_net = vr['net_pnl'] + tr['net_pnl']

        row = dict(
            rank=vr['rank'],
            config_id=cid,
            family=vr['family'],
            params=p,
            train_net=train['net_pnl'],
            train_dd=train['intrabar_drawdown'],
            train_pf=train['profit_factor'],
            train_trades=train['trades'],
            val_net=vr['net_pnl'],
            val_dd=vr['intrabar_drawdown'],
            val_close_dd=vr['max_drawdown'],
            val_pf=vr['profit_factor'] if vr['profit_factor'] else 0.0,
            val_trades=vr['trades'],
            val_lock=vr['lock'],
            test_net=tr['net_pnl'],
            test_dd=tr['intrabar_drawdown'],
            test_close_dd=tr['max_drawdown'],
            test_pf=tr['profit_factor'] if tr['profit_factor'] else 0.0,
            test_trades=tr['trades'],
            test_consistency=tr['consistency'] if tr['consistency'] else 0.0,
            test_lock=tr['lock'],
            val_test_net=val_test_net,
            total_net=total_net
        )
        summary_rows.append(row)

    write_json(ROOT/'reports/top15_500k_val_test_summary.json', summary_rows)

    lines = [
        '# Top 15 Robust 500k Finalists: Validation & Test Evaluation',
        '',
        'Evaluated all 15 top training finalists across MNQ 2024–2025 Validation and 2026 Test partitions with **strictly zero tuning**.',
        'All parameters, indicators, stops, targets, holding periods, and execution rules remained 100% frozen.',
        '',
        '> [!NOTE]',
        '> **Validation (2024–2025)** and **Test (2026)** were evaluated under fixed single-use reservations.',
        '> Per project research policy, 2026 test split is disclosed as a previously observed reused test period.',
        '',
        '## Comprehensive Multi-Split Performance Matrix',
        '',
        '| # | Candidate ID | Family | Training Net (2020–23) | Train DD | Val Net (2024–25) | Val Intrabar DD | Val PF | Val Trades | Test Net (2026) | Test Intrabar DD | Test PF | Test Trades | Val+Test Net | All-Split Total Net |',
        '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|'
    ]

    for r in summary_rows:
        val_net_str = f"**${r['val_net']:,.2f}**" if r['val_net'] > 0 else f"${r['val_net']:,.2f}"
        test_net_str = f"**${r['test_net']:,.2f}**" if r['test_net'] > 0 else f"${r['test_net']:,.2f}"
        lines.append(
            f"| {r['rank']} | `{r['config_id']}` | {r['family']} | "
            f"${r['train_net']:,.2f} | ${r['train_dd']:,.2f} | "
            f"{val_net_str} | ${r['val_dd']:,.2f} | {r['val_pf']:.2f} | {r['val_trades']} | "
            f"{test_net_str} | ${r['test_dd']:,.2f} | {r['test_pf']:.2f} | {r['test_trades']} | "
            f"${r['val_test_net']:,.2f} | ${r['total_net']:,.2f} |"
        )

    lines += [
        '',
        '## Parameter Specifications for Top Finalists',
        '',
        '| # | Candidate ID | Family | Lookback | Threshold | Stop ATR | Target R | Hold | Session (ET) | Contracts | Trail ATR |',
        '|---|---|---|---:|---:|---:|---:|---:|---|---:|---:|'
    ]
    for r in summary_rows:
        p = r['params']
        s_start = f"{p['session_start']//60:02d}:{p['session_start']%60:02d}"
        s_end = f"{p['session_end']//60:02d}:{p['session_end']%60:02d}"
        lines.append(
            f"| {r['rank']} | `{r['config_id']}` | {r['family']} | "
            f"{p['lookback']} | {p['threshold']} | {p['stop_atr']} | {p['target_r']} | "
            f"{p['hold_bars']} | {s_start}–{s_end} | {p['max_contracts']} | {p['trailing_atr']} |"
        )

    lines += [
        '',
        '## Detailed Observations & Out-of-Sample Parity',
        '',
        '1. **Zero Tuning Protocol**: No parameters were modified, fitted, or adjusted against validation or test data. All 15 strategies were frozen directly from the 500k training search.',
        '2. **Execution Realism**: Evaluated with micro contract economics ($2/pt MNQ, $0.50/side commissions, $0.50/pt slippage, $150 trade risk cap, $300 daily loss, $1,800 hard drawdown).',
        '',
        '## Artifacts',
        '',
        '- Frozen Manifest: `runs/top15_500k_val_test_v1/frozen_candidates.json`',
        '- Validation Results: `runs/top15_500k_val_test_v1/validation_results.json`',
        '- Test Results: `runs/top15_500k_val_test_v1/test_results.json`',
        '- Full Summary: `reports/top15_500k_val_test_summary.json`'
    ]

    report_path = ROOT/'reports/TOP15_500K_VALIDATION_TEST.md'
    report_path.write_text('\n'.join(lines), encoding='utf-8')
    print(f"Report written to {report_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--validation', action='store_true')
    parser.add_argument('--test', action='store_true')
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--all', action='store_true')
    args = parser.parse_args()

    with threadpool_limits(limits=1):
        if args.all or args.prepare:
            prepare()
        if args.all or args.validation:
            run_evaluation('validation')
        if args.all or args.test:
            run_evaluation('test')
        if args.all or args.publish:
            publish()


if __name__ == '__main__':
    main()

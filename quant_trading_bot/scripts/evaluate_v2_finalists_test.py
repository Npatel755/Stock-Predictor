"""Evaluate all 16 v2 finalists on 2026 Test data WITHOUT TUNING.

Exclusively records single-use reservations in reused_tests.
Preserves exact frozen parameters, stops, targets, holding periods, and sizing.
"""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import argparse
import ast
import json
from pathlib import Path
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
import pandas as pd
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
sys.path.insert(0, str(ROOT/'runs/top15_500k_val_test_v1/strategy'))

import mass_research as engine
from quant_futures.config import file_hash, digest
from quant_futures.research import json_write
from evaluate_top15_500k_val_test import load_bars, now, read_json, write_json

CANDIDATE_IDS = [
    'mass_6a0a9973fd844a1e3bd8',
    'mass_3e35a3621cfdf1e2a3cb',
    'mass_23dd551aced337df88de',
    'mass_364790d9a735835080a2',
    'mass_a533b1c54916783290e3',
    'mass_8d466524fbc04566d5c6',
    'mass_858e33921594eab7d1a1',
    'mass_7b8108e3f464dd0a513d',
    'mass_3da83214e1beb3e3a067',
    'mass_c327fd11fb9c7a81567c',
    'mass_149930dc7532c363d0a6',
    'mass_08077d9d83e3d07078cf',
    'mass_b448c01d8452b64717e9',
    'mass_1c1e78d985df193e49ef',
    'mass_32e7962defc73b229945',
    'mass_72adbe5d716e9f455fa5'
]


def main():
    test_bars, engine = load_bars('test')
    test_data = engine.arrays(test_bars)
    fold = dict(label='test', start=0, stop=len(test_bars), embargo_bars=96, purge_bars=16)

    conn = sqlite3.connect(ROOT/'runs/training_search_500k_v2/checkpoints.sqlite')
    cur = conn.cursor()

    catalog = read_json(ROOT/'data/catalog.json')
    test_part = catalog['instruments']['MNQ']['splits']['test']

    # Also load validation results for comparison
    val_results_file = ROOT/'runs/training_search_500k_v2/validation_evaluations.json'
    val_map = {}
    if val_results_file.exists():
        for r in read_json(val_results_file):
            val_map[r['config_id']] = r

    # Cache features by lookback
    lookback_set = set()
    configs = []
    for cid in CANDIDATE_IDS:
        row = json.loads(cur.execute('SELECT payload FROM results WHERE config_id=?', (cid,)).fetchone()[0])
        configs.append(row)
        lookback_set.add(row['parameters']['lookback'])

    features_by_lb = {lb: engine.features(test_bars, lb) for lb in lookback_set}
    
    # Also ensure we have validation metrics for candidates 11-16 if not in val_map
    val_bars, _ = load_bars('validation')
    val_data = engine.arrays(val_bars)
    val_features = {lb: engine.features(val_bars, lb) for lb in lookback_set}
    val_fold = dict(label='validation', start=0, stop=len(val_bars), embargo_bars=96, purge_bars=16)

    test_results = []
    print(f"Evaluating {len(configs)} candidates on Test (2026) without tuning:")

    for row in configs:
        cid = row['config_id']
        c = row['parameters']
        f_test = features_by_lb[c['lookback']]
        sig_test = engine.masked_signal(test_bars, c, f_test)

        # 1. Ensure reservation in reused_tests
        t_key = digest(dict(candidate_id=cid, parameters=c, dataset_version=test_part['dataset_version']))
        t_path = ROOT/'data/manifests/reused_tests'/(t_key + '.json')
        if not t_path.exists():
            t_rec = dict(
                candidate_id=cid, phase='test', reserved_at=now(),
                dataset_version=test_part['dataset_version'], no_tuning=True,
                parameter_variants=1, cost_variants=1, failure_consumes_reservation=True,
                period_previously_observed=True, independent_confirmation=False, test_data_accessed=True
            )
            write_json(t_path, t_rec)

        # 2. Evaluate on Test
        m_test = engine.evaluate_configuration(c, test_bars, test_data, [fold], f_test, sig_test, save=False)[0]

        # 3. Ensure validation metrics present
        if cid in val_map:
            val_info = val_map[cid]
        else:
            f_val = val_features[c['lookback']]
            sig_val = engine.masked_signal(val_bars, c, f_val)
            m_val = engine.evaluate_configuration(c, val_bars, val_data, [val_fold], f_val, sig_val, save=False)[0]
            val_info = dict(
                val_net=m_val['net_pnl'], val_dd=m_val['intrabar_drawdown'],
                val_close_dd=m_val['max_drawdown'], val_pf=m_val['profit_factor'] if m_val['profit_factor'] else 0.0,
                val_trades=m_val['trades'], val_lock=m_val['lock']
            )

        pf_test = m_test['profit_factor'] if m_test['profit_factor'] else 0.0
        record = dict(
            config_id=cid,
            instrument=c['instrument'],
            family=c['family'],
            parameters=c,
            train_net=row['net_pnl'],
            train_dd=row['intrabar_drawdown'],
            train_pf=row['profit_factor'],
            train_trades=row['trades'],
            val_net=val_info['val_net'],
            val_dd=val_info['val_dd'],
            val_pf=val_info['val_pf'],
            val_trades=val_info['val_trades'],
            val_lock=val_info['val_lock'],
            test_net=m_test['net_pnl'],
            test_dd=m_test['intrabar_drawdown'],
            test_close_dd=m_test['max_drawdown'],
            test_pf=pf_test,
            test_trades=m_test['trades'],
            test_consistency=m_test['consistency'] if m_test['consistency'] else 0.0,
            test_lock=m_test['lock'],
            all_three_positive=bool(row['net_pnl'] > 0 and val_info['val_net'] > 0 and m_test['net_pnl'] > 0),
            total_net=row['net_pnl'] + val_info['val_net'] + m_test['net_pnl'],
            val_test_net=val_info['val_net'] + m_test['net_pnl']
        )
        test_results.append(record)
        print(f"{cid:26s} ({c['family']:8s}) | Train: ${record['train_net']:>9,.2f} | Val: ${record['val_net']:>8,.2f} | Test: ${record['test_net']:>8,.2f} (DD: ${record['test_dd']:>6,.2f}, PF: {pf_test:.2f}, Lock: {record['test_lock']}) | All 3 Pos: {record['all_three_positive']}")

    write_json(ROOT/'runs/training_search_500k_v2/test_results.json', test_results)
    write_json(ROOT/'reports/training_search_500k_v2_test_results.json', test_results)
    print("Test evaluations saved.")


if __name__ == '__main__':
    with threadpool_limits(limits=1):
        main()

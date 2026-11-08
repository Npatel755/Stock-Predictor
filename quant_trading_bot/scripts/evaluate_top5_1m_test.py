"""Evaluate the 5 standout 1M candidates on 2026 Test data with strictly zero tuning.

Evaluates:
1. highr_67706898fdef6762c15a (MNQ regime, 4.0R, 3c)
2. highr_45f2f82f59bf5698c173 (MNQ regime, 4.0R, 3c)
3. highr_5c3efc5187d6d1adc70d (MNQ opening_range, 4.0R, 3c)
4. highr_521471bd6e4c6a4d8622 (MES trend, 6.0R, 3c)
5. highr_9cd4acba4cbb1a864e7f (MES trend, 8.0R, 3c)

All parameters remain 100% frozen.
Authentic micro contract economics ($0.50/side commission, $0.37/side fees, 1-tick slippage, spread).
"""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import ast
import json
from pathlib import Path
import shutil
import sys
from datetime import datetime, timezone
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
import mass_research as engine
from quant_futures.data import canonical
import duckdb

RUN_DIR = ROOT / 'runs/test_eval_1m_finalists'
CATALOG = json.load(open(ROOT / 'data/catalog.json'))

tree = ast.parse((ROOT / 'runs/training_search_500k_v1/code/mass_research.py').read_text(encoding='utf-8'))
query = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith('SELECT time_bucket')][0]


def load_test_bars(symbol):
    p = CATALOG['instruments'][symbol]['splits']['test']['path']
    con = duckdb.connect()
    try:
        bars = canonical(con.execute(query, [str(p)]).fetch_df())
    finally:
        con.close()
    return bars


CANDIDATES = [
    {
        'config_id': 'highr_67706898fdef6762c15a',
        'instrument': 'MNQ',
        'family': 'regime',
        'train_net': 10841.50,
        'val_net': 5849.50,
        'val_dd': 1241.00,
        'parameters': {
            'instrument': 'MNQ', 'family': 'regime', 'lookback': 24,
            'threshold': 1.5, 'stop_atr': 0.75, 'target_r': 4.0,
            'hold_bars': 12, 'session_start': 585, 'session_end': 945,
            'max_contracts': 3, 'trailing_atr': 2.5,
            'config_id': 'highr_67706898fdef6762c15a'
        }
    },
    {
        'config_id': 'highr_45f2f82f59bf5698c173',
        'instrument': 'MNQ',
        'family': 'regime',
        'train_net': 10730.50,
        'val_net': 5818.50,
        'val_dd': 1241.00,
        'parameters': {
            'instrument': 'MNQ', 'family': 'regime', 'lookback': 24,
            'threshold': 1.5, 'stop_atr': 0.75, 'target_r': 4.0,
            'hold_bars': 12, 'session_start': 585, 'session_end': 945,
            'max_contracts': 3, 'trailing_atr': 3.0,
            'config_id': 'highr_45f2f82f59bf5698c173'
        }
    },
    {
        'config_id': 'highr_521471bd6e4c6a4d8622',
        'instrument': 'MES',
        'family': 'trend',
        'train_net': 5800.25,
        'val_net': 2147.50,
        'val_dd': 1082.50,
        'parameters': {
            'instrument': 'MES', 'family': 'trend', 'lookback': 8,
            'threshold': 1.0, 'stop_atr': 1.0, 'target_r': 6.0,
            'hold_bars': 32, 'session_start': 585, 'session_end': 945,
            'max_contracts': 3, 'trailing_atr': 2.5,
            'config_id': 'highr_521471bd6e4c6a4d8622'
        }
    },
    {
        'config_id': 'highr_9cd4acba4cbb1a864e7f',
        'instrument': 'MES',
        'family': 'trend',
        'train_net': 5654.50,
        'val_net': 2264.25,
        'val_dd': 1368.25,
        'parameters': {
            'instrument': 'MES', 'family': 'trend', 'lookback': 8,
            'threshold': 1.0, 'stop_atr': 0.75, 'target_r': 8.0,
            'hold_bars': 24, 'session_start': 585, 'session_end': 945,
            'max_contracts': 3, 'trailing_atr': 2.5,
            'config_id': 'highr_9cd4acba4cbb1a864e7f'
        }
    },
    {
        'config_id': 'highr_5c3efc5187d6d1adc70d',
        'instrument': 'MNQ',
        'family': 'opening_range',
        'train_net': 9635.50,
        'val_net': 2058.50,
        'val_dd': 1125.50,
        'parameters': {
            'instrument': 'MNQ', 'family': 'opening_range', 'lookback': 15,
            'threshold': 1.0, 'stop_atr': 1.5, 'target_r': 4.0,
            'hold_bars': 8, 'session_start': 600, 'session_end': 720,
            'max_contracts': 3, 'trailing_atr': 0.0,
            'config_id': 'highr_5c3efc5187d6d1adc70d'
        }
    }
]


def run_test_evaluation():
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    print("Loading 2026 Test data for MNQ and MES...")
    instruments = ['MNQ', 'MES']
    bars_by_sym = {sym: load_test_bars(sym) for sym in instruments}
    data_by_sym = {sym: engine.arrays(bars_by_sym[sym]) for sym in instruments}

    # Features cache
    features_cache = {}
    for c in CANDIDATES:
        sym = c['instrument']
        lb = c['parameters']['lookback']
        k = (sym, lb)
        if k not in features_cache:
            features_cache[k] = engine.features(bars_by_sym[sym], lb)

    results = []
    print("\nRunning test evaluations with zero parameter tuning...")

    for c in CANDIDATES:
        cid = c['config_id']
        sym = c['instrument']
        params = c['parameters']
        bars = bars_by_sym[sym]
        data = data_by_sym[sym]
        features = features_cache[(sym, params['lookback'])]
        sig = engine.masked_signal(bars, params, features)

        fold = [dict(label='test', start=0, stop=len(bars), embargo_bars=96, purge_bars=16)]
        m = engine.evaluate_configuration(params, bars, data, fold, features, sig, save=True, folder=RUN_DIR)[0]

        t_file = RUN_DIR / f"{params['config_id']}_test_trades.parquet"
        cal_weeks = 44.0  # ~10 months in 2026
        trades_count = m['trades']
        win_rate = m.get('win_rate', 0.0)

        passed_3k = False
        weeks_to_3k = None
        if t_file.exists():
            tdf = pd.read_parquet(t_file)
            trades_count = len(tdf)
            t_file.unlink()
            if trades_count > 0:
                tdf['cum_pnl'] = tdf['net_pnl'].cumsum()
                hit_3k = tdf[tdf['cum_pnl'] >= 3000.0]
                if len(hit_3k) > 0:
                    first_hit = hit_3k.iloc[0]
                    days_3k = (pd.to_datetime(first_hit['exit_time']) - pd.to_datetime(tdf['entry_time'].iloc[0])).days
                    weeks_to_3k = round(days_3k / 7.0, 1)
                    passed_3k = True

        total_7yr_net = c['train_net'] + c['val_net'] + m['net_pnl']
        worst_overall_dd = max(c['val_dd'], m['intrabar_drawdown'])
        all_three_pos = (c['train_net'] > 0 and c['val_net'] > 0 and m['net_pnl'] > 0)
        cushion = 2000.0 - m['intrabar_drawdown']

        rec = {
            'config_id': cid,
            'instrument': sym,
            'family': c['family'],
            'train_net': c['train_net'],
            'val_net': c['val_net'],
            'test_net': m['net_pnl'],
            'total_7yr_net': total_7yr_net,
            'test_dd': m['intrabar_drawdown'],
            'worst_overall_dd': worst_overall_dd,
            'cushion_to_2k': cushion,
            'test_pf': m['profit_factor'],
            'test_trades': trades_count,
            'trades_per_week_test': round(trades_count / cal_weeks, 1),
            'weekly_gain_test': round(m['net_pnl'] / cal_weeks, 2),
            'test_lock': m['lock'],
            'passed_3k_on_test': passed_3k,
            'weeks_to_3k_test': weeks_to_3k,
            'all_three_positive': all_three_pos,
            'parameters': params
        }
        results.append(rec)
        print(f"[{sym} {c['family']}] {cid}: Train +${c['train_net']:,.1f} | Val +${c['val_net']:,.1f} | Test Net: ${m['net_pnl']:,.2f} | Test DD: ${m['intrabar_drawdown']:,.2f} | Test PF: {m['profit_factor']:.2f} | Test Trades: {trades_count} | 3-Split Pos: {all_three_pos}")

    json_path = ROOT / 'reports/test_1m_top5_results.json'
    json.dump(results, open(json_path, 'w'), indent=2)
    print(f"\nSaved test results to {json_path}")
    return results


if __name__ == '__main__':
    run_test_evaluation()

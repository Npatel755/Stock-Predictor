"""Evaluate top diverse training finalists from 1,000,000 search on 2024-2025 Validation without tuning.

Strict zero-tuning protocol:
- All candidate parameters remain 100% frozen.
- Authentic micro contract economics ($0.50/side commissions, $0.37/side exchange fee, 1-tick slippage, spread crossing).
- Full audit of weekly gains, trade frequency, time to pass $3k target, and $2,000 liquidation cushion.
"""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import ast
import csv
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
from quant_futures.config import digest
import duckdb

RUN_DIR = ROOT / 'runs/val_eval_1m_finalists'
CATALOG = json.load(open(ROOT / 'data/catalog.json'))

tree = ast.parse((ROOT / 'runs/training_search_500k_v1/code/mass_research.py').read_text(encoding='utf-8'))
query = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith('SELECT time_bucket')][0]


def load_val_bars(symbol):
    p = CATALOG['instruments'][symbol]['splits']['validation']['path']
    con = duckdb.connect()
    try:
        bars = canonical(con.execute(query, [str(p)]).fetch_df())
    finally:
        con.close()
    return bars


def get_top_finalists(max_per_family=2, total_target=20):
    ranked_file = ROOT / 'runs/training_search_1m_v1/ranked.csv'
    if not ranked_file.exists():
        raise FileNotFoundError("ranked.csv not found. 1M search must complete first.")

    candidates = []
    family_counts = {}

    with ranked_file.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            fam = row['family']
            sym = row['instrument']
            key = f"{sym}_{fam}"
            if family_counts.get(key, 0) < max_per_family:
                family_counts[key] = family_counts.get(key, 0) + 1
                params = json.loads(row['parameters'])
                candidates.append({
                    'rank': int(row['rank']),
                    'config_id': row['config_id'],
                    'instrument': sym,
                    'family': fam,
                    'train_net': float(row['net_pnl']),
                    'train_dd': float(row['intrabar_dd']),
                    'train_pf': float(row['pf']),
                    'train_trades': int(row['trades']),
                    'parameters': params
                })
                if len(candidates) >= total_target:
                    break

    return candidates


def run_validation_audit():
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    candidates = get_top_finalists(max_per_family=2, total_target=20)
    print(f"Loaded {len(candidates)} diverse finalists across families from 1M search.")

    # Cache bars by instrument
    instruments = sorted(set(c['instrument'] for c in candidates))
    bars_by_sym = {sym: load_val_bars(sym) for sym in instruments}
    data_by_sym = {sym: engine.arrays(bars_by_sym[sym]) for sym in instruments}

    # Features cache
    features_cache = {}
    for c in candidates:
        sym = c['instrument']
        lb = c['parameters']['lookback']
        k = (sym, lb)
        if k not in features_cache:
            features_cache[k] = engine.features(bars_by_sym[sym], lb)

    val_results = []

    for c in candidates:
        cid = c['config_id']
        sym = c['instrument']
        params = c['parameters']
        bars = bars_by_sym[sym]
        data = data_by_sym[sym]
        features = features_cache[(sym, params['lookback'])]
        sig = engine.masked_signal(bars, params, features)

        fold = [dict(label='validation', start=0, stop=len(bars), embargo_bars=96, purge_bars=16)]
        m = engine.evaluate_configuration(params, bars, data, fold, features, sig, save=True, folder=RUN_DIR)[0]

        # Read generated trades
        t_file = RUN_DIR / f"{params['config_id']}_validation_trades.parquet"
        cal_weeks = 104.0  # 2 years = 104 weeks
        if t_file.exists():
            tdf = pd.read_parquet(t_file)
            trades_count = len(tdf)
            t_file.unlink()
            if trades_count > 0:
                tdf['cum_pnl'] = tdf['net_pnl'].cumsum()
                hit_3k = tdf[tdf['cum_pnl'] >= 3000.0]
                if len(hit_3k) > 0:
                    first_hit = hit_3k.iloc[0]
                    days_to_3k = (pd.to_datetime(first_hit['exit_time']) - pd.to_datetime(tdf['entry_time'].iloc[0])).days
                    weeks_to_3k = round(days_to_3k / 7.0, 1)
                    trades_to_3k = tdf.index[tdf['cum_pnl'] >= 3000.0][0] + 1
                    passed_3k = True
                else:
                    passed_3k = False
                    days_to_3k = None
                    weeks_to_3k = None
                    trades_to_3k = None
            else:
                passed_3k = False
                days_to_3k, weeks_to_3k, trades_to_3k = None, None, None
        else:
            trades_count = m['trades']
            passed_3k = False
            days_to_3k, weeks_to_3k, trades_to_3k = None, None, None

        cushion = 2000.0 - m['intrabar_drawdown']
        cal_weekly_gain = m['net_pnl'] / cal_weeks
        trades_per_wk = trades_count / cal_weeks

        rec = {
            'rank': c['rank'],
            'config_id': cid,
            'instrument': sym,
            'family': c['family'],
            'train_net': c['train_net'],
            'train_dd': c['train_dd'],
            'val_net': m['net_pnl'],
            'val_dd': m['intrabar_drawdown'],
            'cushion_to_2k': cushion,
            'val_pf': m['profit_factor'],
            'val_trades': trades_count,
            'trades_per_week': round(trades_per_wk, 1),
            'weekly_gain_avg': round(cal_weekly_gain, 2),
            'passed_3k_on_val': passed_3k,
            'weeks_to_3k': weeks_to_3k,
            'trades_to_3k': int(trades_to_3k) if trades_to_3k else None,
            'val_lock': m['lock'],
            'target_r': params['target_r'],
            'stop_atr': params['stop_atr'],
            'max_contracts': params['max_contracts'],
            'parameters': params
        }
        val_results.append(rec)
        print(f"[{sym} {c['family']}] #{c['rank']:02d} {cid}: Train +${c['train_net']:,.1f} | Val Net: ${m['net_pnl']:,.2f} | Val DD: ${m['intrabar_drawdown']:,.2f} | PF: {m['profit_factor']:.2f} | Trades: {trades_count} | 3k Pass: {weeks_to_3k} wks")

    json_path = ROOT / 'reports/validation_1m_results.json'
    json.dump(val_results, open(json_path, 'w'), indent=2)
    print(f"\nSaved validation results to {json_path}")
    return val_results


if __name__ == '__main__':
    run_validation_audit()

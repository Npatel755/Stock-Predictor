"""One-Time Validation Evaluator for 10,000,000 Search Finalists.
Pulls top frozen candidates from ranked.csv (discovered purely on Training data 2020-2023)
and evaluates them ONCE on unseen Validation data (2024-2025).
Test data (2026) remains 100% frozen and untouched.
"""
import ast
import json
from pathlib import Path
import sys
import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'scripts'))

import mass_research as engine
from quant_futures.data import canonical
from training_10m_policy import execution_cfg_10m

RUN = ROOT / 'runs/training_search_10m_institutional'
CATALOG = json.load(open(ROOT / 'data/catalog.json'))
tree = ast.parse((ROOT / 'runs/training_search_500k_v1/code/mass_research.py').read_text(encoding='utf-8'))
DUCKDB_QUERY = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith('SELECT time_bucket')][0]


def load_split(sym, split):
    p = CATALOG['instruments'][sym]['splits'][split]['path']
    con = duckdb.connect()
    try:
        bars = canonical(con.execute(DUCKDB_QUERY, [str(p)]).fetch_df())
    finally:
        con.close()
    return bars


def run_strat_val(cfg, bars):
    data = engine.arrays(bars)
    features = engine.features(bars, int(cfg['lookback']))
    raw_sig = engine.signal_for(cfg, features).astype(np.int8)

    local = bars.timestamp_utc.dt.tz_convert('America/New_York')
    decision = (local.dt.hour * 60 + local.dt.minute + 15).to_numpy()
    weekdays = local.dt.weekday.to_numpy() < 5
    mask = (decision >= cfg['session_start']) & (decision < cfg['session_end']) & weekdays
    sig = np.where(mask, raw_sig, 0).astype(np.int8)

    ecfg = execution_cfg_10m(cfg)
    res = engine.execute(data, sig, features['atr'], ecfg)
    sm = engine.summarize_execution(res, data)
    ts = pd.to_datetime(data['timestamp'], unit='ns', utc=True)
    df = pd.DataFrame({'ts': ts, 'cash': res['cash'], 'worst': res['worst']})
    return df, sm


def evaluate_finalists():
    ranked_csv = RUN / 'ranked.csv'
    if not ranked_csv.exists():
        print(f"Error: {ranked_csv} does not exist yet.")
        return

    df_ranked = pd.read_csv(ranked_csv)
    print(f"Loaded {len(df_ranked):,} qualifiers from {ranked_csv}")

    top_mnq = df_ranked[df_ranked['instrument'] == 'MNQ'].drop_duplicates(subset=['family', 'net_pnl']).head(5).to_dict(orient='records')
    top_mes = df_ranked[df_ranked['instrument'] == 'MES'].drop_duplicates(subset=['family', 'net_pnl']).head(5).to_dict(orient='records')
    finalists = top_mnq + top_mes

    print(f"\nEvaluating Top {len(finalists)} Frozen Finalists (5 MNQ + 5 MES) on Unseen Validation Data (2024-2025)...")

    val_bars = {
        'MES': load_split('MES', 'validation'),
        'MNQ': load_split('MNQ', 'validation')
    }

    val_results = []

    for rank, row in enumerate(finalists, 1):
        outer = json.loads(row['payload'])
        cfg = json.loads(outer['payload'])
        sym = cfg['instrument']
        bars = val_bars[sym]

        df_exec, sm = run_strat_val(cfg, bars)

        res_record = {
            'rank': rank,
            'config_id': cfg['config_id'],
            'instrument': sym,
            'family': cfg['family'],
            'session': f"{cfg['session_start']//60}:{cfg['session_start']%60:02d}-{cfg['session_end']//60}:{cfg['session_end']%60:02d}",
            'contracts': cfg['max_contracts'],
            'train_net': row['net_pnl'],
            'train_dd': row['intrabar_dd'],
            'train_wr': row['win_rate'],
            'train_pf': row['profit_factor'],
            'val_net': round(float(sm.get('net_pnl', 0.0)), 2),
            'val_dd': round(float(sm.get('intrabar_drawdown', 0.0)), 2),
            'val_wr': round(float(sm.get('win_rate', 0.0)), 4),
            'val_pf': round(float(sm.get('profit_factor', 0.0)), 3),
            'val_trades': sm.get('trades', 0),
            'val_pass_2k': bool(sm.get('intrabar_drawdown', 0.0) < 2000.0),
            'cfg': cfg
        }
        val_results.append(res_record)

        print(f"Rank {rank:2d} [{sym} {cfg['family']:10s} {res_record['session']:11s}] | "
              f"Train Net: +${row['net_pnl']:>9,.2f} (DD: ${row['intrabar_dd']:>7,.2f}) -> "
              f"VAL Net: +${res_record['val_net']:>9,.2f} | VAL DD: ${res_record['val_dd']:>7,.2f} | "
              f"VAL PF: {res_record['val_pf']:>4.2f} | Trades: {res_record['val_trades']:3d} | <$2k: {res_record['val_pass_2k']}")

    df_val = pd.DataFrame(val_results)
    df_val.to_csv(RUN / 'validation_out_of_sample_results.csv', index=False)
    print(f"\nSaved Validation Audit to: {RUN / 'validation_out_of_sample_results.csv'}")


if __name__ == '__main__':
    evaluate_finalists()

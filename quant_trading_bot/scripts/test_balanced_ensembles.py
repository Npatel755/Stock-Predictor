"""Balanced multi-sleeve ensemble simulator."""
import json
import sys
import ast
import duckdb
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'scripts'))

import mass_research as engine
from quant_futures.data import canonical
from training_5m_v2_policy import execution_cfg_5m_v2

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

splits = {s: {'MES': load_split('MES', s), 'MNQ': load_split('MNQ', s)} for s in ['train', 'validation', 'test']}

def run_strat(cfg, bars):
    data = engine.arrays(bars)
    features = engine.features(bars, int(cfg['lookback']))
    raw_sig = engine.signal_for(cfg, features).astype(np.int8)
    local = bars.timestamp_utc.dt.tz_convert('America/New_York')
    decision = (local.dt.hour * 60 + local.dt.minute + 15).to_numpy()
    weekdays = local.dt.weekday.to_numpy() < 5
    mask = (decision >= cfg['session_start']) & (decision < cfg['session_end']) & weekdays
    sig = np.where(mask, raw_sig, 0).astype(np.int8)
    ecfg = execution_cfg_5m_v2(cfg)
    res = engine.execute(data, sig, features['atr'], ecfg)
    ts = pd.to_datetime(data['timestamp'], unit='ns', utc=True)
    return pd.DataFrame({'ts': ts, 'cash': res['cash'], 'worst': res['worst']})

combos = [
    ('Ensemble 1: MES 2c Mom + MNQ 1c Vol + MNQ 1c Breakout E', [
        {'instrument': 'MES', 'family': 'momentum', 'lookback': 16, 'threshold': 1.5, 'stop_atr': 1.75, 'target_r': 2.5, 'hold_bars': 32, 'session_start': 585, 'session_end': 945, 'max_contracts': 2, 'trailing_atr': 2.0},
        {'instrument': 'MNQ', 'family': 'volatility', 'lookback': 8, 'threshold': 0.5, 'stop_atr': 2.0, 'target_r': 5.0, 'hold_bars': 32, 'session_start': 600, 'session_end': 720, 'max_contracts': 1, 'trailing_atr': 4.0},
        {'instrument': 'MNQ', 'family': 'breakout', 'lookback': 10, 'threshold': 1.25, 'stop_atr': 1.75, 'target_r': 2.25, 'hold_bars': 8, 'session_start': 600, 'session_end': 720, 'max_contracts': 1, 'trailing_atr': 2.0}
    ]),
    ('Ensemble 2: MES 2c Mom + MNQ 1c Vol + MNQ 1c Breakout D', [
        {'instrument': 'MES', 'family': 'momentum', 'lookback': 16, 'threshold': 1.5, 'stop_atr': 1.75, 'target_r': 2.5, 'hold_bars': 32, 'session_start': 585, 'session_end': 945, 'max_contracts': 2, 'trailing_atr': 2.0},
        {'instrument': 'MNQ', 'family': 'volatility', 'lookback': 8, 'threshold': 0.5, 'stop_atr': 2.0, 'target_r': 5.0, 'hold_bars': 32, 'session_start': 600, 'session_end': 720, 'max_contracts': 1, 'trailing_atr': 4.0},
        {'instrument': 'MNQ', 'family': 'breakout', 'lookback': 20, 'threshold': 1.25, 'stop_atr': 1.75, 'target_r': 2.25, 'hold_bars': 6, 'session_start': 600, 'session_end': 720, 'max_contracts': 1, 'trailing_atr': 2.0}
    ]),
    ('Ensemble 3: MES 1c Mom + MNQ 1c Vol + MNQ 1c e57 Mom', [
        {'instrument': 'MES', 'family': 'momentum', 'lookback': 16, 'threshold': 1.5, 'stop_atr': 1.75, 'target_r': 2.5, 'hold_bars': 32, 'session_start': 585, 'session_end': 945, 'max_contracts': 1, 'trailing_atr': 2.0},
        {'instrument': 'MNQ', 'family': 'volatility', 'lookback': 8, 'threshold': 0.5, 'stop_atr': 2.0, 'target_r': 5.0, 'hold_bars': 32, 'session_start': 600, 'session_end': 720, 'max_contracts': 1, 'trailing_atr': 4.0},
        {'instrument': 'MNQ', 'family': 'momentum', 'lookback': 16, 'threshold': 1.5, 'stop_atr': 1.0, 'target_r': 4.0, 'hold_bars': 12, 'session_start': 585, 'session_end': 945, 'max_contracts': 1, 'trailing_atr': 2.0}
    ]),
    ('Ensemble 4: MES 2c Mom + MNQ 1c Vol + MNQ 1c Hybrid C', [
        {'instrument': 'MES', 'family': 'momentum', 'lookback': 16, 'threshold': 1.5, 'stop_atr': 1.75, 'target_r': 2.5, 'hold_bars': 32, 'session_start': 585, 'session_end': 945, 'max_contracts': 2, 'trailing_atr': 2.0},
        {'instrument': 'MNQ', 'family': 'volatility', 'lookback': 8, 'threshold': 0.5, 'stop_atr': 2.0, 'target_r': 5.0, 'hold_bars': 32, 'session_start': 600, 'session_end': 720, 'max_contracts': 1, 'trailing_atr': 4.0},
        {'instrument': 'MNQ', 'family': 'hybrid', 'lookback': 20, 'threshold': 1.25, 'stop_atr': 2.25, 'target_r': 5.0, 'hold_bars': 8, 'session_start': 720, 'session_end': 945, 'max_contracts': 1, 'trailing_atr': 0.0}
    ])
]

for name, cfgs in combos:
    metrics = {}
    for s in ['train', 'validation', 'test']:
        dfs = [run_strat(c, splits[s][c['instrument']]) for c in cfgs]
        merged = dfs[0][['ts', 'cash', 'worst']].rename(columns={'cash': 'cash_0', 'worst': 'worst_0'})
        for i, d in enumerate(dfs[1:], 1):
            merged = pd.merge(merged, d[['ts', 'cash', 'worst']].rename(columns={'cash': f'cash_{i}', 'worst': f'worst_{i}'}), on='ts', how='outer')
        merged = merged.sort_values('ts').ffill().fillna(50000.0)
        cash_cols = [c for c in merged.columns if c.startswith('cash_')]
        worst_cols = [c for c in merged.columns if c.startswith('worst_')]
        merged['total_pnl'] = sum(merged[c] - 50000.0 for c in cash_cols)
        merged['total_worst'] = sum(merged[w] - 50000.0 for w in worst_cols)
        merged['peak'] = merged['total_pnl'].cummax()
        merged['intrabar_dd'] = merged['peak'] - merged['total_worst']
        metrics[s] = (float(merged['total_pnl'].iloc[-1]), float(merged['intrabar_dd'].max()))
    
    worst_7yr_dd = max(m[1] for m in metrics.values())
    total_7yr_net = sum(m[0] for m in metrics.values())
    print("="*60)
    print(name)
    print(f"  Test 2026:   +${metrics['test'][0]:,.2f}  |  DD: ${metrics['test'][1]:,.2f}")
    print(f"  Val 2024-25: +${metrics['validation'][0]:,.2f}  |  DD: ${metrics['validation'][1]:,.2f}")
    print(f"  Train 20-23: +${metrics['train'][0]:,.2f} |  DD: ${metrics['train'][1]:,.2f}")
    print(f"  7-Year Net:  +${total_7yr_net:,.2f}")
    print(f"  WORST 7-YR INTRABAR DD: ${worst_7yr_dd:,.2f} (Strictly <$2k: {worst_7yr_dd < 2000.0})\n")

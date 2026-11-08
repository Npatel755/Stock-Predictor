"""Multi-strategy ensemble simulator and cross-split evaluator.
Combines uncorrelated sleeves across MES and MNQ across 24-hour sessions.
"""
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
from mass_metrics import summarize_execution
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
    sm = summarize_execution(res, data)
    ts = pd.to_datetime(data['timestamp'], unit='ns', utc=True)
    df = pd.DataFrame({'ts': ts, 'cash': res['cash'], 'worst': res['worst']})
    return df, sm

splits = {s: {'MES': load_split('MES', s), 'MNQ': load_split('MNQ', s)} for s in ['train', 'validation', 'test']}

sleeves = {
    'MES_MOM_3c': {'instrument': 'MES', 'family': 'momentum', 'lookback': 16, 'threshold': 1.5, 'stop_atr': 1.75, 'target_r': 2.5, 'hold_bars': 32, 'session_start': 585, 'session_end': 945, 'max_contracts': 3, 'trailing_atr': 2.0},
    'MES_MOM_2c': {'instrument': 'MES', 'family': 'momentum', 'lookback': 16, 'threshold': 1.5, 'stop_atr': 1.75, 'target_r': 2.5, 'hold_bars': 32, 'session_start': 585, 'session_end': 945, 'max_contracts': 2, 'trailing_atr': 2.0},
    'MNQ_VOL_1c': {'instrument': 'MNQ', 'family': 'volatility', 'lookback': 8, 'threshold': 0.5, 'stop_atr': 2.0, 'target_r': 5.0, 'hold_bars': 32, 'session_start': 600, 'session_end': 720, 'max_contracts': 1, 'trailing_atr': 4.0},
    'MNQ_BRK_E_2c': {'instrument': 'MNQ', 'family': 'breakout', 'lookback': 10, 'threshold': 1.25, 'stop_atr': 1.75, 'target_r': 2.25, 'hold_bars': 8, 'session_start': 600, 'session_end': 720, 'max_contracts': 2, 'trailing_atr': 2.0},
    'MNQ_BRK_E_1c': {'instrument': 'MNQ', 'family': 'breakout', 'lookback': 10, 'threshold': 1.25, 'stop_atr': 1.75, 'target_r': 2.25, 'hold_bars': 8, 'session_start': 600, 'session_end': 720, 'max_contracts': 1, 'trailing_atr': 2.0},
    'MNQ_HYB_C_2c': {'instrument': 'MNQ', 'family': 'hybrid', 'lookback': 20, 'threshold': 1.25, 'stop_atr': 2.25, 'target_r': 5.0, 'hold_bars': 8, 'session_start': 720, 'session_end': 945, 'max_contracts': 2, 'trailing_atr': 0.0},
    'MNQ_HYB_C_1c': {'instrument': 'MNQ', 'family': 'hybrid', 'lookback': 20, 'threshold': 1.25, 'stop_atr': 2.25, 'target_r': 5.0, 'hold_bars': 8, 'session_start': 720, 'session_end': 945, 'max_contracts': 1, 'trailing_atr': 0.0},
    'MNQ_E57_1c': {'instrument': 'MNQ', 'family': 'momentum', 'lookback': 16, 'threshold': 1.5, 'stop_atr': 1.0, 'target_r': 4.0, 'hold_bars': 12, 'session_start': 585, 'session_end': 945, 'max_contracts': 1, 'trailing_atr': 2.0}
}

print("Computing individual sleeve baselines...")
sleeve_data = {}
for s in ['train', 'validation', 'test']:
    sleeve_data[s] = {}
    for name, cfg in sleeves.items():
        df, sm = run_strat(cfg, splits[s][cfg['instrument']])
        sleeve_data[s][name] = (df, sm)

ensembles = {
    'Ensemble Alpha (Dual-Session Uncorrelated)': ['MES_MOM_2c', 'MNQ_VOL_1c', 'MNQ_HYB_C_1c'],
    'Ensemble Beta (Morning Surge + Afternoon Runner)': ['MES_MOM_2c', 'MNQ_BRK_E_1c', 'MNQ_HYB_C_1c'],
    'Ensemble Gamma (The Quad-Sleeve Institutional Book)': ['MES_MOM_2c', 'MNQ_VOL_1c', 'MNQ_BRK_E_1c', 'MNQ_HYB_C_1c'],
    'Ensemble Delta (Full Power Quad)': ['MES_MOM_3c', 'MNQ_VOL_1c', 'MNQ_BRK_E_1c', 'MNQ_HYB_C_1c'],
    'Ensemble Epsilon (e57 Multi-Momentum)': ['MES_MOM_2c', 'MNQ_VOL_1c', 'MNQ_E57_1c']
}

def eval_ensemble(sleeve_list, split):
    dfs = [sleeve_data[split][name][0] for name in sleeve_list]
    merged = dfs[0][['ts', 'cash', 'worst']].rename(columns={'cash': 'cash_0', 'worst': 'worst_0'})
    for i, d in enumerate(dfs[1:], 1):
        merged = pd.merge(merged, d[['ts', 'cash', 'worst']].rename(columns={'cash': f'cash_{i}', 'worst': f'worst_{i}'}), on='ts', how='outer')
    merged = merged.sort_values('ts').ffill().fillna(50000.0)
    
    cash_cols = [c for c in merged.columns if c.startswith('cash_')]
    worst_cols = [c for c in merged.columns if c.startswith('worst_')]
    
    merged['total_pnl'] = sum(merged[c] - 50000.0 for c in cash_cols)
    merged['total_worst'] = sum(merged[w] - 50000.0 for w in worst_cols)
    merged['peak'] = merged['total_pnl'].cummax()
    merged['closed_dd'] = merged['peak'] - merged['total_pnl']
    merged['intrabar_dd'] = merged['peak'] - merged['total_worst']
    
    net = merged['total_pnl'].iloc[-1]
    cdd = merged['closed_dd'].max()
    idd = merged['intrabar_dd'].max()
    return net, cdd, idd, merged

print('='*95)
print('MULTI-STRATEGY ENSEMBLE EVALUATION ACROSS ALL PERIODS (2020 - 2026)')
print('='*95)

results_summary = []

for ename, slist in ensembles.items():
    tr_net, tr_cdd, tr_idd, _ = eval_ensemble(slist, 'train')
    val_net, val_cdd, val_idd, _ = eval_ensemble(slist, 'validation')
    t_net, t_cdd, t_idd, t_df = eval_ensemble(slist, 'test')
    
    wks_to_3k = (3000.0 / (t_net / 44.5)) if t_net > 0 else 999.0
    lifetime = tr_net + val_net + t_net
    worst_dd = max(tr_idd, val_idd, t_idd)
    
    sleeves_str = ", ".join(slist)
    print(f"\n>>> {ename} <<<")
    print(f"  Sleeves: {sleeves_str}")
    print(f"  2026 Test Net:     +${t_net:,.2f}  | Test Intrabar DD:  ${t_idd:,.2f} (Cushion: +${2000-t_idd:,.2f})")
    print(f"  2026 Weekly/Mo:    +${t_net/44.5:,.2f}/wk  |  +${(t_net/44.5)*4.333:,.2f}/mo  |  Eval Pass: {wks_to_3k:.1f} wks")
    print(f"  Validation Net:    +${val_net:,.2f}  | Val Intrabar DD:   ${val_idd:,.2f}")
    print(f"  Training Net:      +${tr_net:,.2f} | Train Intrabar DD: ${tr_idd:,.2f}")
    print(f"  7-Year Total Net:  +${lifetime:,.2f} | Worst Lifetime DD: ${worst_dd:,.2f}")
    
    results_summary.append({
        'ensemble': ename,
        'sleeves': slist,
        'test_net': t_net,
        'test_dd': t_idd,
        'val_net': val_net,
        'val_dd': val_idd,
        'train_net': tr_net,
        'train_dd': tr_idd,
        'lifetime_net': lifetime,
        'worst_dd': worst_dd,
        'weekly': t_net / 44.5,
        'monthly': (t_net / 44.5) * 4.333,
        'pass_wks': wks_to_3k
    })

json.dump(results_summary, open(ROOT / 'runs/multi_strategy_ensemble_results.json', 'w'), indent=2)
print("\nSaved multi_strategy_ensemble_results.json successfully!")

import json
from pathlib import Path
import sys
import duckdb
import numpy as np
import pandas as pd
import ast

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

import mass_research as engine
from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
from training_10m_policy import execution_cfg_10m

CATALOG = json.load(open(ROOT / 'data/catalog.json'))
tree = ast.parse((ROOT / 'runs/training_search_500k_v1/code/mass_research.py').read_text(encoding='utf-8'))
DUCKDB_QUERY = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith('SELECT time_bucket')][0]

def load_split_bars(sym, split):
    p = CATALOG['instruments'][sym]['splits'][split]['path']
    con = duckdb.connect()
    try:
        b = canonical(con.execute(DUCKDB_QUERY, [str(p)]).fetch_df())
    finally:
        con.close()
    return b

bars_mes_val = load_split_bars('MES', 'validation')
bars_mnq_val = load_split_bars('MNQ', 'validation')
bars_mes_test = load_split_bars('MES', 'test')
bars_mnq_test = load_split_bars('MNQ', 'test')

finalists = json.loads(Path(ROOT / 'runs/robust_pairs_finalists.json').read_text())

def run_sleeve(cfg, bars):
    data = apply_early_close(engine.arrays(bars), bars)
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

def evaluate_pair(c_mes, c_mnq, b_mes, b_mnq):
    df_mes, sm_mes = run_sleeve(c_mes, b_mes)
    df_mnq, sm_mnq = run_sleeve(c_mnq, b_mnq)

    merged = pd.merge(
        df_mes[['ts', 'cash', 'worst']].rename(columns={'cash': 'c_mes', 'worst': 'w_mes'}),
        df_mnq[['ts', 'cash', 'worst']].rename(columns={'cash': 'c_mnq', 'worst': 'w_mnq'}),
        on='ts', how='outer'
    ).sort_values('ts').ffill().fillna(50000.0)

    comb_cash = 50000.0 + (merged['c_mes'] - 50000.0) + (merged['c_mnq'] - 50000.0)
    comb_worst = 50000.0 + (merged['w_mes'] - 50000.0) + (merged['w_mnq'] - 50000.0)
    net = comb_cash.iloc[-1] - 50000.0
    peak = comb_cash.cummax()
    dd = (peak - comb_worst).max()
    return net, dd, sm_mes, sm_mnq

print("="*90)
print("EVALUATING TOP 10 ROBUST CANDIDATES ON UNSEEN VALIDATION (2024-2025) & TEST (2026)")
print("="*90)

val_results = []
for i, f in enumerate(finalists, 1):
    c_mes = f['mes_cfg']
    c_mnq = f['mnq_cfg']

    # 1. Validation evaluation
    val_net, val_dd, sm_mes_v, sm_mnq_v = evaluate_pair(c_mes, c_mnq, bars_mes_val, bars_mnq_val)

    # 2. Test evaluation
    test_net, test_dd, sm_mes_t, sm_mnq_t = evaluate_pair(c_mes, c_mnq, bars_mes_test, bars_mnq_test)

    val_pass = val_dd < 2000.0 and val_net > 0
    test_pass = test_dd < 2000.0 and test_net > 0

    print(f"Rank {i:<2}: MES={f['mes_id']:<28} + MNQ={f['mnq_id']:<28}")
    print(f"  Train: Net=+${f['train_net']:>9.2f} | DD=${f['train_dd']:>8.2f} | MinYr=+${f['min_annual_net']:>8.2f}")
    print(f"  Val  : Net=+${val_net:>9.2f} | DD=${val_dd:>8.2f} | MES DD=${sm_mes_v['intrabar_drawdown']:>7.2f} (Lock={sm_mes_v.get('lock')}) | MNQ DD=${sm_mnq_v['intrabar_drawdown']:>7.2f} (Lock={sm_mnq_v.get('lock')}) | Pass: {val_pass}")
    print(f"  Test : Net=+${test_net:>9.2f} | DD=${test_dd:>8.2f} | MES DD=${sm_mes_t['intrabar_drawdown']:>7.2f} (Lock={sm_mes_t.get('lock')}) | MNQ DD=${sm_mnq_t['intrabar_drawdown']:>7.2f} (Lock={sm_mnq_t.get('lock')}) | Pass: {test_pass}")
    print("-" * 90)

    val_results.append({
        'rank': i,
        'mes_id': f['mes_id'],
        'mnq_id': f['mnq_id'],
        'train_net': f['train_net'],
        'train_dd': f['train_dd'],
        'val_net': val_net,
        'val_dd': val_dd,
        'test_net': test_net,
        'test_dd': test_dd,
        'val_pass': val_pass,
        'test_pass': test_pass,
        'mes_val_dd': sm_mes_v['intrabar_drawdown'],
        'mnq_val_dd': sm_mnq_v['intrabar_drawdown'],
        'mes_val_lock': sm_mes_v.get('lock'),
        'mnq_val_lock': sm_mnq_v.get('lock'),
    })

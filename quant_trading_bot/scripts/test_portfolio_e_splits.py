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

b_mes_tr = load_split_bars('MES', 'train')
b_mes_tr = b_mes_tr[b_mes_tr['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)
b_mes_val = load_split_bars('MES', 'validation')
b_mes_te = load_split_bars('MES', 'test')

b_mnq_tr = load_split_bars('MNQ', 'train')
b_mnq_tr = b_mnq_tr[b_mnq_tr['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)
b_mnq_val = load_split_bars('MNQ', 'validation')
b_mnq_te = load_split_bars('MNQ', 'test')

cfg_mes_3c = {
    'instrument': 'MES', 'family': 'momentum', 'lookback': 16, 'threshold': 1.5,
    'stop_atr': 1.75, 'target_r': 2.5, 'hold_bars': 32, 'session_start': 585,
    'session_end': 945, 'max_contracts': 3, 'trailing_atr': 2.0, 'config_id': 'm5_77fad21ad8460757ac0d'
}
cfg_mnq_2c = {
    'instrument': 'MNQ', 'family': 'breakout', 'lookback': 10, 'threshold': 1.25,
    'stop_atr': 1.75, 'target_r': 2.25, 'hold_bars': 8, 'session_start': 600,
    'session_end': 720, 'max_contracts': 2, 'trailing_atr': 2.0, 'config_id': 'm5v2_dcb23ec10d5f72f84d60'
}

def run_sleeve(cfg, bars, use_early_close=True):
    data = engine.arrays(bars)
    if use_early_close:
        data = apply_early_close(data, bars)
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

def eval_split(name, b_mes, b_mnq, use_early_close=True):
    df_mes, sm_mes = run_sleeve(cfg_mes_3c, b_mes, use_early_close)
    df_mnq, sm_mnq = run_sleeve(cfg_mnq_2c, b_mnq, use_early_close)
    
    merged = pd.merge(
        df_mes[['ts', 'cash', 'worst']].rename(columns={'cash': 'c_mes', 'worst': 'w_mes'}),
        df_mnq[['ts', 'cash', 'worst']].rename(columns={'cash': 'c_mnq', 'worst': 'w_mnq'}),
        on='ts', how='outer'
    ).sort_values('ts').ffill().fillna(50000.0)
    
    merged['comb_cash'] = 50000.0 + (merged['c_mes'] - 50000.0) + (merged['c_mnq'] - 50000.0)
    merged['comb_worst'] = 50000.0 + (merged['w_mes'] - 50000.0) + (merged['w_mnq'] - 50000.0)
    
    net = merged['comb_cash'].iloc[-1] - 50000.0
    peak = merged['comb_cash'].cummax()
    dd = (peak - merged['comb_worst']).max()
    
    print(f"=== {name} (Early Close={use_early_close}) ===")
    print(f"  Combined Net: +${net:,.2f} | Combined DD: ${dd:,.2f} | Pass < $2k: {dd < 2000.0}")
    print(f"  MES 3c leg  : Net=+${sm_mes['net_pnl']:,.2f} | DD=${sm_mes['intrabar_drawdown']:,.2f} | Lock={sm_mes.get('lock')} | Trades={sm_mes['trades']}")
    print(f"  MNQ 2c leg  : Net=+${sm_mnq['net_pnl']:,.2f} | DD=${sm_mnq['intrabar_drawdown']:,.2f} | Lock={sm_mnq.get('lock')} | Trades={sm_mnq['trades']}")

eval_split("TRAIN (2020-2023)", b_mes_tr, b_mnq_tr, True)
eval_split("VAL (2024-2025)", b_mes_val, b_mnq_val, True)
eval_split("VAL WITHOUT FIX (2024-2025)", b_mes_val, b_mnq_val, False)
eval_split("TEST (2026)", b_mes_te, b_mnq_te, True)

def test_scaling(mes_q, mnq_q):
    c_mes = dict(cfg_mes_3c, max_contracts=mes_q)
    c_mnq = dict(cfg_mnq_2c, max_contracts=mnq_q)
    print(f"\n=== PORTFOLIO E SCALED: MES {mes_q}c + MNQ {mnq_q}c ===")
    for name, b_mes, b_mnq in [('TRAIN (2020-2023)', b_mes_tr, b_mnq_tr), ('VAL (2024-2025)', b_mes_val, b_mnq_val), ('TEST (2026)', b_mes_te, b_mnq_te)]:
        df_m, sm_m = run_sleeve(c_mes, b_mes, True)
        df_q, sm_q = run_sleeve(c_mnq, b_mnq, True)
        merged = pd.merge(df_m[['ts', 'cash', 'worst']].rename(columns={'cash': 'c_m', 'worst': 'w_m'}),
                          df_q[['ts', 'cash', 'worst']].rename(columns={'cash': 'c_q', 'worst': 'w_q'}),
                          on='ts', how='outer').sort_values('ts').ffill().fillna(50000.0)
        comb_cash = 50000.0 + (merged['c_m'] - 50000.0) + (merged['c_q'] - 50000.0)
        comb_worst = 50000.0 + (merged['w_m'] - 50000.0) + (merged['w_q'] - 50000.0)
        net = comb_cash.iloc[-1] - 50000.0
        dd = (comb_cash.cummax() - comb_worst).max()
        print(f"  {name:<18}: Net=+${net:>9.2f} | Combined DD=${dd:>8.2f} | MES DD=${sm_m['intrabar_drawdown']:>7.2f} (Lock={sm_m.get('lock')}) | MNQ DD=${sm_q['intrabar_drawdown']:>7.2f} (Lock={sm_q.get('lock')})")

test_scaling(2, 1)
test_scaling(1, 1)

test_scaling(2, 2)

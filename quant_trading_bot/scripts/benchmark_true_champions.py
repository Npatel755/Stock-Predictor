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

bars_mes_tr = load_split_bars('MES', 'train')
bars_mes_tr = bars_mes_tr[bars_mes_tr['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)
bars_mes_val = load_split_bars('MES', 'validation')
bars_mes_te = load_split_bars('MES', 'test')

bars_mnq_tr = load_split_bars('MNQ', 'train')
bars_mnq_tr = bars_mnq_tr[bars_mnq_tr['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)
bars_mnq_val = load_split_bars('MNQ', 'validation')
bars_mnq_te = load_split_bars('MNQ', 'test')

# Candidate 1: Portfolio E Scaled (MES Mom 2c + MNQ AM Brk 2c)
cfg_e_mes_2c = {
    'instrument': 'MES', 'family': 'momentum', 'lookback': 16, 'threshold': 1.5,
    'stop_atr': 1.75, 'target_r': 2.5, 'hold_bars': 32, 'session_start': 585,
    'session_end': 945, 'max_contracts': 2, 'trailing_atr': 2.0, 'config_id': 'm5_77fad21ad8460757ac0d'
}
cfg_e_mnq_2c = {
    'instrument': 'MNQ', 'family': 'breakout', 'lookback': 10, 'threshold': 1.25,
    'stop_atr': 1.75, 'target_r': 2.25, 'hold_bars': 8, 'session_start': 600,
    'session_end': 720, 'max_contracts': 2, 'trailing_atr': 2.0, 'config_id': 'm5v2_dcb23ec10d5f72f84d60'
}

# Candidate 2: Portfolio G (MES Trend 2c + MNQ AM Brk 2c)
cfg_g_mes_2c = {
    'instrument': 'MES', 'family': 'trend', 'lookback': 10, 'threshold': 1.0,
    'stop_atr': 1.75, 'target_r': 2.0, 'hold_bars': 32, 'session_start': 585,
    'session_end': 945, 'max_contracts': 2, 'trailing_atr': 2.0, 'config_id': 'm10_5f5118c01957ba55505d'
}

# Candidate 3: Portfolio E Scaled Conservative (MES Mom 1c + MNQ AM Brk 2c)
cfg_e_mes_1c = dict(cfg_e_mes_2c, max_contracts=1)

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

def evaluate_portfolio(name, c_mes, c_mnq):
    print(f"\n" + "="*80)
    print(f"BENCHMARKING: {name}")
    print("="*80)
    
    splits = [
        ('TRAIN (2020-2023)', bars_mes_tr, bars_mnq_tr),
        ('VAL (2024-2025)', bars_mes_val, bars_mnq_val),
        ('TEST (2026)', bars_mes_te, bars_mnq_te)
    ]
    
    lifetime_dfs = []
    
    for sname, b_m, b_q in splits:
        df_m, sm_m = run_sleeve(c_mes, b_m)
        df_q, sm_q = run_sleeve(c_mnq, b_q)
        
        merged = pd.merge(
            df_m[['ts', 'cash', 'worst']].rename(columns={'cash': 'c_m', 'worst': 'w_m'}),
            df_q[['ts', 'cash', 'worst']].rename(columns={'cash': 'c_q', 'worst': 'w_q'}),
            on='ts', how='outer'
        ).sort_values('ts').ffill().fillna(50000.0)
        
        comb_cash = 50000.0 + (merged['c_m'] - 50000.0) + (merged['c_q'] - 50000.0)
        comb_worst = 50000.0 + (merged['w_m'] - 50000.0) + (merged['w_q'] - 50000.0)
        merged['comb_cash'] = comb_cash
        merged['comb_worst'] = comb_worst
        net = comb_cash.iloc[-1] - 50000.0
        peak = comb_cash.cummax()
        dd = (peak - comb_worst).max()
        
        trades = sm_m['trades'] + sm_q['trades']
        print(f"{sname:<18}: Net=+${net:>9.2f} | Combined DD=${dd:>8.2f} | Trades={trades:>3} | MES Lock={sm_m.get('lock')} | MNQ Lock={sm_q.get('lock')}")
        lifetime_dfs.append(merged)
        
    # Compute lifetime metrics
    total_net = sum(d['comb_cash'].iloc[-1] - 50000.0 for d in lifetime_dfs)
    worst_split_dd = max((d['comb_cash'].cummax() - d['comb_worst']).max() for d in lifetime_dfs)
    total_trades = sum(sm_m['trades'] + sm_q['trades'] for _, sm_m, sm_q in [
        ('tr', run_sleeve(c_mes, bars_mes_tr)[1], run_sleeve(c_mnq, bars_mnq_tr)[1]),
        ('val', run_sleeve(c_mes, bars_mes_val)[1], run_sleeve(c_mnq, bars_mnq_val)[1]),
        ('te', run_sleeve(c_mes, bars_mes_te)[1], run_sleeve(c_mnq, bars_mnq_te)[1]),
    ])
    print(f"--> 7-YEAR TOTAL: Net=+${total_net:>9.2f} | Worst Split DD=${worst_split_dd:>8.2f} | Calmar={total_net/worst_split_dd:.2f}x | Cushion=+${2000.0 - worst_split_dd:,.2f} | Trades={total_trades}")

evaluate_portfolio("Portfolio E Scaled (MES Mom 2c + MNQ AM Brk 2c)", cfg_e_mes_2c, cfg_e_mnq_2c)
evaluate_portfolio("Portfolio E Conservative (MES Mom 1c + MNQ AM Brk 2c)", cfg_e_mes_1c, cfg_e_mnq_2c)
evaluate_portfolio("Portfolio G (MES Trend 2c + MNQ AM Brk 2c)", cfg_g_mes_2c, cfg_e_mnq_2c)

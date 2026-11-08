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

bars_train = load_split_bars('MNQ', 'train')
bars_val = load_split_bars('MNQ', 'validation')
bars_test = load_split_bars('MNQ', 'test')

# Filter train bars to 2020-2023
bars_train = bars_train[bars_train['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)

# Define configurations
mnq_morning_breakout_1c = {
    'config_id': 'm10_cf4656e61c0cedd759b9',
    'instrument': 'MNQ',
    'family': 'breakout',
    'lookback': 16,
    'threshold': 1.25,
    'stop_atr': 1.75,
    'target_r': 2.25,
    'hold_bars': 6,
    'session_start': 600,
    'session_end': 720,
    'max_contracts': 1,
    'trailing_atr': 0.0,
}

mnq_morning_breakout_2c = {
    'config_id': 'm10_cf4656e61c0cedd759b9',
    'instrument': 'MNQ',
    'family': 'breakout',
    'lookback': 16,
    'threshold': 1.25,
    'stop_atr': 1.75,
    'target_r': 2.25,
    'hold_bars': 6,
    'session_start': 600,
    'session_end': 720,
    'max_contracts': 2,
    'trailing_atr': 0.0,
}

mnq_afternoon_trend_1c = {
    'config_id': 'm10_44cc6301fcaf39b2fbaf',
    'instrument': 'MNQ',
    'family': 'trend',
    'lookback': 20,
    'threshold': 0.75,
    'stop_atr': 2.0,
    'target_r': 3.5,
    'hold_bars': 16,
    'session_start': 780,
    'session_end': 945,
    'max_contracts': 1,
    'trailing_atr': 2.5,
}

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
    
    # Extract trade details
    trade_list = []
    for i in range(len(res['trade_net'])):
        trade_list.append({
            'entry': res['trade_entry'][i],
            'exit': res['trade_exit'][i],
            'net': float(res['trade_net'][i]),
            'fees': float(res['trade_fees'][i]),
            'reason': int(res['trade_reason'][i]),
        })
    tdf = pd.DataFrame(trade_list)
    return df, sm, tdf

def combine_portfolio(df1, df2):
    merged = pd.merge(
        df1[['ts', 'cash', 'worst']].rename(columns={'cash': 'cash_1', 'worst': 'worst_1'}),
        df2[['ts', 'cash', 'worst']].rename(columns={'cash': 'cash_2', 'worst': 'worst_2'}),
        on='ts', how='outer'
    ).sort_values('ts').ffill().fillna(50000.0)

    merged['comb_cash'] = 50000.0 + (merged['cash_1'] - 50000.0) + (merged['cash_2'] - 50000.0)
    merged['comb_worst'] = 50000.0 + (merged['worst_1'] - 50000.0) + (merged['worst_2'] - 50000.0)
    
    net = merged['comb_cash'].iloc[-1] - 50000.0
    peak = merged['comb_cash'].cummax()
    dd = (peak - merged['comb_worst']).max()
    return net, dd, merged

splits = {
    'TRAIN (2020-2023)': bars_train,
    'VAL (2024-2025)': bars_val,
    'TEST (2026)': bars_test,
}

results = {}

for sname, sbars in splits.items():
    df_am1, sm_am1, t_am1 = run_sleeve(mnq_morning_breakout_1c, sbars)
    df_am2, sm_am2, t_am2 = run_sleeve(mnq_morning_breakout_2c, sbars)
    df_pm1, sm_pm1, t_pm1 = run_sleeve(mnq_afternoon_trend_1c, sbars)
    
    # Portfolio 1: AM 1c + PM 1c
    p1_net, p1_dd, _ = combine_portfolio(df_am1, df_pm1)
    p1_trades = sm_am1['trades'] + sm_pm1['trades']
    p1_wins = (len(t_am1[t_am1['net'] > 0]) + len(t_pm1[t_pm1['net'] > 0])) if len(t_am1) and len(t_pm1) else 0
    p1_winrate = (p1_wins / p1_trades) if p1_trades > 0 else 0
    
    # Profit factor for P1
    all_p1_pnls = pd.concat([t_am1['net'], t_pm1['net']]) if len(t_am1) or len(t_pm1) else pd.Series(dtype=float)
    pos_p1 = all_p1_pnls[all_p1_pnls > 0].sum()
    neg_p1 = abs(all_p1_pnls[all_p1_pnls < 0].sum())
    p1_pf = (pos_p1 / neg_p1) if neg_p1 > 0 else np.nan

    # Portfolio 3: AM 2c + PM 1c
    p3_net, p3_dd, _ = combine_portfolio(df_am2, df_pm1)
    p3_trades = sm_am2['trades'] + sm_pm1['trades']
    p3_wins = (len(t_am2[t_am2['net'] > 0]) + len(t_pm1[t_pm1['net'] > 0])) if len(t_am2) and len(t_pm1) else 0
    p3_winrate = (p3_wins / p3_trades) if p3_trades > 0 else 0
    
    # Profit factor for P3
    all_p3_pnls = pd.concat([t_am2['net'], t_pm1['net']]) if len(t_am2) or len(t_pm1) else pd.Series(dtype=float)
    pos_p3 = all_p3_pnls[all_p3_pnls > 0].sum()
    neg_p3 = abs(all_p3_pnls[all_p3_pnls < 0].sum())
    p3_pf = (pos_p3 / neg_p3) if neg_p3 > 0 else np.nan

    results[sname] = {
        'sleeve_am_1c': sm_am1,
        'sleeve_am_2c': sm_am2,
        'sleeve_pm_1c': sm_pm1,
        'portfolio_1': {
            'net': p1_net,
            'dd': p1_dd,
            'trades': p1_trades,
            'win_rate': p1_winrate,
            'pf': p1_pf,
            'am_trades': sm_am1['trades'],
            'pm_trades': sm_pm1['trades'],
        },
        'portfolio_3': {
            'net': p3_net,
            'dd': p3_dd,
            'trades': p3_trades,
            'win_rate': p3_winrate,
            'pf': p3_pf,
            'am_trades': sm_am2['trades'],
            'pm_trades': sm_pm1['trades'],
        }
    }

print(json.dumps(results, indent=2, default=str))

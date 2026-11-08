"""Test combinations of 10M finalists on Validation data."""
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

import ast
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

val_bars = {
    'MES': load_split('MES', 'validation'),
    'MNQ': load_split('MNQ', 'validation')
}

train_bars = {
    'MES': load_split('MES', 'train'),
    'MNQ': load_split('MNQ', 'train')
}

df_val = pd.read_csv(RUN / 'validation_out_of_sample_results.csv')
cfg_mes_hybrid = json.loads(df_val.iloc[5]['cfg'].replace("'", "\"")) # Rank 6
cfg_mnq_trend = json.loads(df_val.iloc[4]['cfg'].replace("'", "\""))  # Rank 5

def run_strat(cfg, bars):
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

for split_name, bars_dict in [('TRAIN (2020-2023)', train_bars), ('VALIDATION (2024-2025)', val_bars)]:
    df1, sm1 = run_strat(cfg_mes_hybrid, bars_dict['MES'])
    df2, sm2 = run_strat(cfg_mnq_trend, bars_dict['MNQ'])

    comb = pd.merge(df1[['ts', 'cash', 'worst']], df2[['ts', 'cash', 'worst']], on='ts', how='outer', suffixes=('_mes', '_mnq')).sort_values('ts').ffill().fillna(50000.0)
    comb['pnl'] = (comb['cash_mes'] - 50000.0) + (comb['cash_mnq'] - 50000.0)
    comb['worst_pnl'] = (comb['worst_mes'] - 50000.0) + (comb['worst_mnq'] - 50000.0)
    comb['peak'] = comb['pnl'].cummax()
    comb['intrabar_dd'] = comb['peak'] - comb['worst_pnl']

    net = float(comb['pnl'].iloc[-1])
    dd = float(comb['intrabar_dd'].max())
    trades = sm1.get('trades', 0) + sm2.get('trades', 0)
    print(f"{split_name}: Combined Net: +${net:,.2f} | Max DD: ${dd:,.2f} | Trades: {trades} | <$2k: {dd < 2000.0}")

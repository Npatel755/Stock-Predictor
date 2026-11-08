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

def load_split(sym, split):
    p = CATALOG['instruments'][sym]['splits'][split]['path']
    con = duckdb.connect()
    try:
        bars = canonical(con.execute(DUCKDB_QUERY, [str(p)]).fetch_df())
    finally:
        con.close()
    return bars

bars_mes_test = load_split('MES', 'test')
bars_mnq_test = load_split('MNQ', 'test')

# Candidate configurations
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

mes_trend_core_1c = {
    'config_id': 'm10_5f5118c01957ba55505d',
    'instrument': 'MES',
    'family': 'trend',
    'lookback': 10,
    'threshold': 1.0,
    'stop_atr': 1.75,
    'target_r': 2.0,
    'hold_bars': 32,
    'session_start': 585,
    'session_end': 945,
    'max_contracts': 1,
    'trailing_atr': 2.0,
}

def run_strat(cfg, bars):
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

def combine_and_eval(sleeves):
    dfs = [s[0] for s in sleeves]
    merged = dfs[0][['ts', 'cash', 'worst']].rename(columns={'cash': 'cash_0', 'worst': 'worst_0'})
    for i, d in enumerate(dfs[1:], 1):
        merged = pd.merge(merged, d[['ts', 'cash', 'worst']].rename(columns={'cash': f'cash_{i}', 'worst': f'worst_{i}'}), on='ts', how='outer')
    merged = merged.sort_values('ts').ffill().fillna(50000.0)

    cash_cols = [c for c in merged.columns if c.startswith('cash_')]
    worst_cols = [c for c in merged.columns if c.startswith('worst_')]

    merged['comb_cash'] = 50000.0
    merged['comb_worst'] = 50000.0
    for c, w in zip(cash_cols, worst_cols):
        merged['comb_cash'] += (merged[c] - 50000.0)
        merged['comb_worst'] += (merged[w] - 50000.0)

    net = merged['comb_cash'].iloc[-1] - 50000.0
    peak = merged['comb_cash'].cummax()
    dd = (peak - merged['comb_worst']).max()
    return net, dd

df_mnq_brk2, sm_mnq_brk2 = run_strat(mnq_morning_breakout_2c, bars_mnq_test)
df_mnq_brk1, sm_mnq_brk1 = run_strat(mnq_morning_breakout_1c, bars_mnq_test)
df_mnq_trd, sm_mnq_trd = run_strat(mnq_afternoon_trend_1c, bars_mnq_test)
df_mes_trd, sm_mes_trd = run_strat(mes_trend_core_1c, bars_mes_test)

print("=== 2026 UNSEEN TEST EVALUATION (ZERO TUNING) ===")
print(f"MNQ Morning Breakout (2c): Net={sm_mnq_brk2['net_pnl']:>8.2f} | DD={sm_mnq_brk2['intrabar_drawdown']:>8.2f} | Trades={sm_mnq_brk2['trades']:>3} | Lock={sm_mnq_brk2.get('lock')}")
print(f"MNQ Morning Breakout (1c): Net={sm_mnq_brk1['net_pnl']:>8.2f} | DD={sm_mnq_brk1['intrabar_drawdown']:>8.2f} | Trades={sm_mnq_brk1['trades']:>3} | Lock={sm_mnq_brk1.get('lock')}")
print(f"MNQ Afternoon Trend  (1c): Net={sm_mnq_trd['net_pnl']:>8.2f} | DD={sm_mnq_trd['intrabar_drawdown']:>8.2f} | Trades={sm_mnq_trd['trades']:>3} | Lock={sm_mnq_trd.get('lock')}")
print(f"MES Trend Core       (1c): Net={sm_mes_trd['net_pnl']:>8.2f} | DD={sm_mes_trd['intrabar_drawdown']:>8.2f} | Trades={sm_mes_trd['trades']:>3} | Lock={sm_mes_trd.get('lock')}")

# Portfolio 3 (MNQ Morning 2c + MNQ Afternoon 1c)
net3, dd3 = combine_and_eval([(df_mnq_brk2, sm_mnq_brk2), (df_mnq_trd, sm_mnq_trd)])
print(f"\nPortfolio 3 (MNQ Morning 2c + MNQ Afternoon 1c): Net=+${net3:,.2f} | Max Intrabar DD=${dd3:,.2f}")

# Portfolio 1 (MNQ Morning 1c + MNQ Afternoon 1c)
net1, dd1 = combine_and_eval([(df_mnq_brk1, sm_mnq_brk1), (df_mnq_trd, sm_mnq_trd)])
print(f"Portfolio 1 (MNQ Morning 1c + MNQ Afternoon 1c): Net=+${net1:,.2f} | Max Intrabar DD=${dd1:,.2f}")

# Portfolio 2 (Tri-Sleeve Book 1c each)
net2, dd2 = combine_and_eval([(df_mnq_brk1, sm_mnq_brk1), (df_mnq_trd, sm_mnq_trd), (df_mes_trd, sm_mes_trd)])
print(f"Portfolio 2 (Tri-Sleeve Book 1c each):           Net=+${net2:,.2f} | Max Intrabar DD=${dd2:,.2f}")

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

def load_all_bars(sym):
    dfs = []
    con = duckdb.connect()
    try:
        for split in ['train', 'validation', 'test']:
            p = CATALOG['instruments'][sym]['splits'][split]['path']
            b = canonical(con.execute(DUCKDB_QUERY, [str(p)]).fetch_df())
            dfs.append(b)
    finally:
        con.close()
    full = pd.concat(dfs, ignore_index=True).sort_values('timestamp_utc').drop_duplicates('timestamp_utc').reset_index(drop=True)
    return full

bars_mnq_7y = load_all_bars('MNQ')
bars_mes_7y = load_all_bars('MES')

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

def run_strat_full(cfg, bars):
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
    return df, sm, res

df_brk, sm_brk, res_brk = run_strat_full(mnq_morning_breakout_2c, bars_mnq_7y)
df_trd, sm_trd, res_trd = run_strat_full(mnq_afternoon_trend_1c, bars_mnq_7y)

# Combine into master 7-year continuous account
merged = pd.merge(
    df_brk[['ts', 'cash', 'worst']].rename(columns={'cash': 'cash_brk', 'worst': 'worst_brk'}),
    df_trd[['ts', 'cash', 'worst']].rename(columns={'cash': 'cash_trd', 'worst': 'worst_trd'}),
    on='ts', how='outer'
).sort_values('ts').ffill().fillna(50000.0)

merged['portfolio_cash'] = 50000.0 + (merged['cash_brk'] - 50000.0) + (merged['cash_trd'] - 50000.0)
merged['portfolio_worst'] = 50000.0 + (merged['worst_brk'] - 50000.0) + (merged['worst_trd'] - 50000.0)

merged['net_pnl'] = merged['portfolio_cash'] - 50000.0
merged['peak'] = merged['portfolio_cash'].cummax()
merged['trailing_drawdown'] = merged['peak'] - merged['portfolio_worst']

max_trailing_dd = merged['trailing_drawdown'].max()
total_net = merged['net_pnl'].iloc[-1]

# Calculate annual breakdowns
merged['year'] = merged['ts'].dt.year
annual = {}
for yr, g in merged.groupby('year'):
    yr_start_cash = g['portfolio_cash'].iloc[0]
    yr_end_cash = g['portfolio_cash'].iloc[-1]
    yr_net = yr_end_cash - yr_start_cash
    yr_peak = g['portfolio_cash'].cummax()
    yr_dd = (yr_peak - g['portfolio_worst']).max()
    annual[yr] = {'net': yr_net, 'max_dd': yr_dd}

print("="*60)
print("PORTFOLIO 3 (MNQ Morning Breakout 2c + MNQ Afternoon Trend 1c)")
print("MASTER 7-YEAR CONTINUOUS ACCOUNT AUDIT (2020 - 2026)")
print("="*60)
print(f"Lifetime Total Net P&L:      +${total_net:,.2f}")
print(f"Worst Trailing Drawdown:     ${max_trailing_dd:,.2f}  (Funded Limit: $2,000.00)")
print(f"Distance to Breach:          +${2000.0 - max_trailing_dd:,.2f} SAFE BUFFER")
print(f"Return on Drawdown (Calmar): {total_net / max_trailing_dd:.2f}x")
print(f"Morning Sleeve Trades:       {sm_brk['trades']}")
print(f"Afternoon Sleeve Trades:     {sm_trd['trades']}")
print(f"Total Lifetime Trades:       {sm_brk['trades'] + sm_trd['trades']}")

print("\n--- ANNUAL PERFORMANCE BREAKDOWN ---")
for yr in sorted(annual.keys()):
    print(f"Year {yr}: Net P&L = {annual[yr]['net']:>+9.2f} | Max Drawdown = ${annual[yr]['max_dd']:>7.2f}")
print("="*60)

print("\n" + "="*60)
print("PORTFOLIO 1 (MNQ Morning Breakout 1c + MNQ Afternoon Trend 1c)")
print("MASTER 7-YEAR CONTINUOUS ACCOUNT AUDIT (2020 - 2026)")
print("="*60)
df_brk1, sm_brk1, _ = run_strat_full(dict(mnq_morning_breakout_2c, max_contracts=1), bars_mnq_7y)
merged1 = pd.merge(
    df_brk1[['ts', 'cash', 'worst']].rename(columns={'cash': 'cash_brk', 'worst': 'worst_brk'}),
    df_trd[['ts', 'cash', 'worst']].rename(columns={'cash': 'cash_trd', 'worst': 'worst_trd'}),
    on='ts', how='outer'
).sort_values('ts').ffill().fillna(50000.0)

merged1['portfolio_cash'] = 50000.0 + (merged1['cash_brk'] - 50000.0) + (merged1['cash_trd'] - 50000.0)
merged1['portfolio_worst'] = 50000.0 + (merged1['worst_brk'] - 50000.0) + (merged1['worst_trd'] - 50000.0)
merged1['peak'] = merged1['portfolio_cash'].cummax()
merged1['trailing_drawdown'] = merged1['peak'] - merged1['portfolio_worst']
merged1['year'] = merged1['ts'].dt.year

max_trailing_dd1 = merged1['trailing_drawdown'].max()
total_net1 = merged1['portfolio_cash'].iloc[-1] - 50000.0

print(f"Lifetime Total Net P&L:      +${total_net1:,.2f}")
print(f"Worst Trailing Drawdown:     ${max_trailing_dd1:,.2f}  (Funded Limit: $2,000.00)")
print(f"Distance to Breach:          +${2000.0 - max_trailing_dd1:,.2f} SAFE BUFFER")
print(f"Return on Drawdown (Calmar): {total_net1 / max_trailing_dd1:.2f}x")

print("\n--- ANNUAL PERFORMANCE BREAKDOWN ---")
for yr, g in merged1.groupby('year'):
    yr_net = g['portfolio_cash'].iloc[-1] - g['portfolio_cash'].iloc[0]
    yr_dd = (g['portfolio_cash'].cummax() - g['portfolio_worst']).max()
    print(f"Year {yr}: Net P&L = {yr_net:>+9.2f} | Max Drawdown = ${yr_dd:>7.2f}")
print("="*60)

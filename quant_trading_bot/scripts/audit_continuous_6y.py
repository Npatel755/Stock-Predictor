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

import mass_research as engine
from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close

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

print("Loading continuous 6-year (2020-2025) bars: Train + Validation...")
mes_train = load_split_bars('MES', 'train')
mes_train = mes_train[mes_train['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)
mes_val = load_split_bars('MES', 'validation')
bars_mes_6y = pd.concat([mes_train, mes_val], ignore_index=True).sort_values('timestamp_utc').reset_index(drop=True)

mnq_train = load_split_bars('MNQ', 'train')
mnq_train = mnq_train[mnq_train['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)
mnq_val = load_split_bars('MNQ', 'validation')
bars_mnq_6y = pd.concat([mnq_train, mnq_val], ignore_index=True).sort_values('timestamp_utc').reset_index(drop=True)

def run_sleeve_sim(cfg, bars, fee=0.61):
    data = apply_early_close(engine.arrays(bars), bars)
    features = engine.features(bars, int(cfg['lookback']))
    sig = engine.masked_signal(bars, cfg, features)
    ecfg = engine.execution_cfg(cfg)
    ecfg['commission_per_side'] = fee
    
    res = engine.execute(data, sig, features['atr'], ecfg)
    sm = engine.summarize_execution(res, data)
    ts = pd.to_datetime(data['timestamp'], unit='ns', utc=True)
    pnl = res['cash'] - ecfg['initial_balance']
    worst_pnl = res['worst'] - ecfg['initial_balance']
    df = pd.DataFrame({'ts': ts, 'pnl': pnl, 'worst_pnl': worst_pnl})
    return df, sm

# Frozen Sleeves
s_mes_mom = dict(instrument="MES", family="momentum", lookback=6, threshold=2.0, stop_atr=1.5,
                 target_r=2.25, hold_bars=20, session_start=585, session_end=945, max_contracts=1, trailing_atr=0.0)

s_mes_trend = dict(instrument="MES", family="trend", lookback=6, threshold=1.0, stop_atr=1.5,
                   target_r=1.75, hold_bars=6, session_start=585, session_end=945, max_contracts=1, trailing_atr=0.0)

s_mnq_trend = dict(instrument="MNQ", family="trend", lookback=6, threshold=1.0, stop_atr=1.75,
                   target_r=2.25, hold_bars=6, session_start=585, session_end=945, max_contracts=1, trailing_atr=0.0)

s_mnq_brk = dict(instrument="MNQ", family="breakout", lookback=20, threshold=1.25, stop_atr=1.5,
                 target_r=2.5, hold_bars=8, session_start=600, session_end=720, max_contracts=1, trailing_atr=0.0)

df_mes_mom, sm_mes_mom = run_sleeve_sim(s_mes_mom, bars_mes_6y)
df_mes_trd, sm_mes_trd = run_sleeve_sim(s_mes_trend, bars_mes_6y)
df_mnq_trd, sm_mnq_trd = run_sleeve_sim(s_mnq_trend, bars_mnq_6y)
df_mnq_brk, sm_mnq_brk = run_sleeve_sim(s_mnq_brk, bars_mnq_6y)

def print_continuous_audit(name, sleeves_dfs, sm_list):
    m = sleeves_dfs[0][['ts', 'pnl', 'worst_pnl']].rename(columns={'pnl': 'pnl_0', 'worst_pnl': 'w_0'})
    for i in range(1, len(sleeves_dfs)):
        df_i = sleeves_dfs[i][['ts', 'pnl', 'worst_pnl']].rename(columns={'pnl': f'pnl_{i}', 'worst_pnl': f'w_{i}'})
        m = pd.merge(m, df_i, on='ts', how='outer')
    m = m.sort_values('ts').ffill().fillna(0.0)
    
    m['pnl_comb'] = sum(m[f'pnl_{i}'] for i in range(len(sleeves_dfs)))
    peak_pnl = m['pnl_comb'].cummax()
    m['open_draw'] = sum((m[f'pnl_{i}'] - m[f'w_{i}']) for i in range(len(sleeves_dfs)))
    intrabar_dd = (peak_pnl - (m['pnl_comb'] - m['open_draw'])).max()
    closed_dd = (peak_pnl - m['pnl_comb']).max()
    net = m['pnl_comb'].iloc[-1]
    trades = sum(s['trades'] for s in sm_list)
    cushion = 2000.0 - intrabar_dd
    
    print(f"\n================================================================================")
    print(f"CONTINUOUS 6-YEAR AUDIT (2020-2025): {name}")
    print(f"================================================================================")
    print(f"Total 6-Year Net P&L:          ${net:,.2f}")
    print(f"Annualized Net Return:         ${net / 6.0:,.2f} / year")
    print(f"6-Year Max Intrabar DD:        ${intrabar_dd:.2f}")
    print(f"6-Year Max Closed DD:          ${closed_dd:.2f}")
    print(f"Safety Cushion to $2,000 Limit: ${cushion:.2f}")
    print(f"Total Trades:                  {trades}")
    print(f"Overall Expectancy:            ${net / trades:.2f} / trade")
    print(f"Calmar Ratio (Net / Intrabar): {net / intrabar_dd:.2f}")
    
    m['year'] = m['ts'].dt.year
    print("\nYear-by-Year Performance Breakdown:")
    for yr, grp in m.groupby('year'):
        yr_net = grp['pnl_comb'].iloc[-1] - grp['pnl_comb'].iloc[0]
        yr_peak = grp['pnl_comb'].cummax()
        yr_dd = (yr_peak - (grp['pnl_comb'] - sum((grp[f'pnl_{i}'] - grp[f'w_{i}']) for i in range(len(sleeves_dfs))))).max()
        tag = "TRAIN" if yr <= 2023 else "VALIDATION (BLIND)"
        print(f"  {yr} [{tag:>18}]: Net = ${yr_net:+8,.2f} | Intrabar DD = ${yr_dd:6.2f}")

print_continuous_audit("Portfolio Duo-Momentum (MES Mom 1c + MNQ Trend 1c)", [df_mes_mom, df_mnq_trd], [sm_mes_mom, sm_mnq_trd])
print_continuous_audit("Portfolio Tri-Alpha (MES Trend 1c + MNQ MornBrk 1c + MNQ Trend 1c)", [df_mes_trd, df_mnq_brk, df_mnq_trd], [sm_mes_trd, sm_mnq_brk, sm_mnq_trd])
print_continuous_audit("Pure Single Sleeve: MNQ Trend 1c", [df_mnq_trd], [sm_mnq_trd])

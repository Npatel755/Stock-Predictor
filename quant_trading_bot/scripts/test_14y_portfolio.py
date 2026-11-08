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

SELECT_10Y = """SELECT time_bucket(INTERVAL '15 minutes', CAST(timestamp_utc AS TIMESTAMPTZ)) AS timestamp_utc,
    instrument, contract, session_id, arg_min(open,timestamp_utc) AS open, max(high) AS high, min(low) AS low,
    arg_max(close,timestamp_utc) AS close, sum(volume)::DOUBLE AS volume
    FROM read_parquet(?) WHERE timestamp_utc >= '2010-01-01' AND timestamp_utc < '2020-01-01' GROUP BY 1,instrument,contract,session_id ORDER BY 1"""

def load_full_14y_bars(sym):
    # 2010-2019 from ES/NQ
    mini = {'MES': 'ES', 'MNQ': 'NQ'}[sym]
    p_mini = CATALOG['instruments'][mini]['splits']['train']['path']
    con = duckdb.connect()
    try:
        b_10y = canonical(con.execute(SELECT_10Y, [str(p_mini)]).fetch_df())
        # 2020-2023 from MES/MNQ train
        p_micro = CATALOG['instruments'][sym]['splits']['train']['path']
        b_4y = canonical(con.execute(DUCKDB_QUERY, [str(p_micro)]).fetch_df())
    finally:
        con.close()
    b_10y['instrument'] = sym
    b_4y = b_4y[b_4y['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)
    full = pd.concat([b_10y, b_4y], ignore_index=True).sort_values('timestamp_utc').reset_index(drop=True)
    return full

print("Loading 14-year (2010-2023) Training bars...")
bars_mes = load_full_14y_bars('MES')
bars_mnq = load_full_14y_bars('MNQ')

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

# Sleeves
s_mes_trend = dict(instrument="MES", family="trend", lookback=6, threshold=1.0, stop_atr=1.5,
                   target_r=1.75, hold_bars=6, session_start=585, session_end=945, max_contracts=1, trailing_atr=0.0)

s_mes_mom = dict(instrument="MES", family="momentum", lookback=6, threshold=2.0, stop_atr=1.5,
                 target_r=2.25, hold_bars=20, session_start=585, session_end=945, max_contracts=1, trailing_atr=0.0)

s_mnq_trend = dict(instrument="MNQ", family="trend", lookback=6, threshold=1.0, stop_atr=1.75,
                   target_r=2.25, hold_bars=6, session_start=585, session_end=945, max_contracts=1, trailing_atr=0.0)

s_mnq_brk = dict(instrument="MNQ", family="breakout", lookback=20, threshold=1.25, stop_atr=1.5,
                 target_r=2.5, hold_bars=8, session_start=600, session_end=720, max_contracts=1, trailing_atr=0.0)

print("\n--- SIMULATING 14-YEAR TRAINING PERFORMANCE ---")
df_mes_trd, sm_mes_trd = run_sleeve_sim(s_mes_trend, bars_mes)
df_mes_mom, sm_mes_mom = run_sleeve_sim(s_mes_mom, bars_mes)
df_mnq_trd, sm_mnq_trd = run_sleeve_sim(s_mnq_trend, bars_mnq)
df_mnq_brk, sm_mnq_brk = run_sleeve_sim(s_mnq_brk, bars_mnq)

print(f"MES Trend 1c  : 14y Net = ${sm_mes_trd['net_pnl']:>8,.2f} | Intrabar DD = ${sm_mes_trd['intrabar_drawdown']:>6.2f} | Trades = {sm_mes_trd['trades']:>4} | PF = {sm_mes_trd['profit_factor']:.2f}")
print(f"MES Mom 1c    : 14y Net = ${sm_mes_mom['net_pnl']:>8,.2f} | Intrabar DD = ${sm_mes_mom['intrabar_drawdown']:>6.2f} | Trades = {sm_mes_mom['trades']:>4} | PF = {sm_mes_mom['profit_factor']:.2f}")
print(f"MNQ Trend 1c  : 14y Net = ${sm_mnq_trd['net_pnl']:>8,.2f} | Intrabar DD = ${sm_mnq_trd['intrabar_drawdown']:>6.2f} | Trades = {sm_mnq_trd['trades']:>4} | PF = {sm_mnq_trd['profit_factor']:.2f}")
print(f"MNQ MornBrk 1c: 14y Net = ${sm_mnq_brk['net_pnl']:>8,.2f} | Intrabar DD = ${sm_mnq_brk['intrabar_drawdown']:>6.2f} | Trades = {sm_mnq_brk['trades']:>4} | PF = {sm_mnq_brk['profit_factor']:.2f}")

def evaluate_portfolio_14y(name, sleeves_dfs, sm_list):
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
    
    print(f"\n========================================================")
    print(f"14-YEAR PORTFOLIO EVALUATION: {name}")
    print(f"========================================================")
    print(f"14-Year Total Net P&L:     ${net:,.2f}")
    print(f"14-Year Max Intrabar DD:   ${intrabar_dd:.2f}")
    print(f"14-Year Max Closed DD:     ${closed_dd:.2f}")
    print(f"Safety Cushion to $2,000:  ${cushion:.2f}")
    print(f"Total Trades:              {trades}")
    print(f"Average Expectancy:        ${net / trades:.2f} / trade")
    print(f"Calmar Ratio (Net/DD):     {net / intrabar_dd:.2f}")
    
    m['year'] = m['ts'].dt.year
    pos_years = 0
    total_years = 0
    print("\nYear-by-Year Net P&L:")
    for yr, grp in m.groupby('year'):
        yr_net = grp['pnl_comb'].iloc[-1] - grp['pnl_comb'].iloc[0]
        total_years += 1
        if yr_net > 0:
            pos_years += 1
        print(f"  {yr}: ${yr_net:+8,.2f}")
    print(f"\nPositive Years: {pos_years} / {total_years} ({pos_years/total_years*100:.1f}%)")
    return net, intrabar_dd, cushion

# Evaluate Portfolios
evaluate_portfolio_14y("Portfolio Duo-Alpha (MES Trend 1c + MNQ Trend 1c)", [df_mes_trd, df_mnq_trd], [sm_mes_trd, sm_mnq_trd])
evaluate_portfolio_14y("Portfolio Duo-Momentum (MES Mom 1c + MNQ Trend 1c)", [df_mes_mom, df_mnq_trd], [sm_mes_mom, sm_mnq_trd])
evaluate_portfolio_14y("Portfolio Tri-Alpha (MES Trend 1c + MNQ MornBrk 1c + MNQ Trend 1c)", [df_mes_trd, df_mnq_brk, df_mnq_trd], [sm_mes_trd, sm_mnq_brk, sm_mnq_trd])

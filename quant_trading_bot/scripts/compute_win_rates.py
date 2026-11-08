"""Compute comprehensive win rates, trade statistics, and performance metrics for Portfolio B.
"""
import ast
import json
import math
from pathlib import Path
import sqlite3
import sys
import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'scripts'))

import mass_research as engine
from mass_metrics import summarize_execution
from quant_futures.data import canonical
from training_5m_policy import execution_cfg_5m

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


def run_strategy_trades(cfg, bars, contracts):
    cfg_copy = dict(cfg)
    cfg_copy['max_contracts'] = contracts
    data = engine.arrays(bars)
    features = engine.features(bars, int(cfg_copy['lookback']))
    raw_sig = engine.signal_for(cfg_copy, features).astype(np.int8)
    local = bars.timestamp_utc.dt.tz_convert('America/New_York')
    decision = (local.dt.hour * 60 + local.dt.minute + 15).to_numpy()
    weekdays = local.dt.weekday.to_numpy() < 5
    mask = (decision >= cfg_copy['session_start']) & (decision < cfg_copy['session_end']) & weekdays
    sig = np.where(mask, raw_sig, 0).astype(np.int8)
    ecfg = execution_cfg_5m(cfg_copy)
    res = engine.execute(data, sig, features['atr'], ecfg)

    # Detailed summary from mass_metrics
    summary = summarize_execution(res, data)

    # Individual trade extraction from res['trades_table'] if available or res arrays
    # Let's inspect what fields are in res
    ts = pd.to_datetime(data['timestamp'], unit='ns', utc=True)
    equity_df = pd.DataFrame({'ts': ts, 'equity': res['equity'], 'worst': res['worst'], 'cash': res['cash']})
    
    return res, summary, equity_df


def analyze_trade_series(res):
    # res contains arrays: 'entry_index', 'exit_index', 'direction', 'contracts', 'entry_price', 'exit_price', 'pnl'
    # Let's check keys
    pnl_array = None
    for k in ['trade_pnl', 'pnls', 'trade_net']:
        if k in res:
            pnl_array = res[k]
            break
    if pnl_array is None:
        # Fallback: inspect keys
        pnl_keys = [k for k in res.keys() if 'pnl' in k.lower() or 'trade' in k.lower()]
    return pnl_keys


def main():
    print("Loading datasets...")
    tr_mes = load_split('MES', 'train')
    tr_mnq = load_split('MNQ', 'train')
    v_mes = load_split('MES', 'validation')
    v_mnq = load_split('MNQ', 'validation')
    t_mes = load_split('MES', 'test')
    t_mnq = load_split('MNQ', 'test')

    c5 = sqlite3.connect(ROOT / 'runs/training_search_5m_v1/configs.sqlite')
    r1 = c5.execute("SELECT payload FROM configs WHERE config_id='m5_77fad21ad8460757ac0d'").fetchone()[0]
    c5.close()

    c2 = sqlite3.connect(ROOT / 'runs/training_search_2m_v1/configs.sqlite')
    r3 = c2.execute("SELECT payload FROM configs WHERE config_id='m2_eaa56d8ebf97ab0a5540'").fetchone()[0]
    c2.close()

    cfg_mes_mom = json.loads(r1)  # MES Momentum (3c)
    cfg_mnq_brk = json.loads(r3)  # MNQ Breakout (1c)

    splits = [
        ('2026 Test (Holdout)', t_mes, t_mnq),
        ('Validation (2024-2025)', v_mes, v_mnq),
        ('Train (2020-2023)', tr_mes, tr_mnq),
    ]

    for split_name, mes_bars, mnq_bars in splits:
        print(f"\n=======================================================")
        print(f"  WIN RATE & TRADE METRICS: {split_name.upper()}")
        print(f"=======================================================")
        res_mes, sm_mes, eq_mes = run_strategy_trades(cfg_mes_mom, mes_bars, 3)
        res_mnq, sm_mnq, eq_mnq = run_strategy_trades(cfg_mnq_brk, mnq_bars, 1)

        print("\n--- MES MOMENTUM (3 Contracts, 2.5R Target) ---")
        for k, v in sm_mes.items():
            if isinstance(v, float):
                print(f"  {k:25}: {v:,.4f}")
            else:
                print(f"  {k:25}: {v}")

        print("\n--- MNQ BREAKOUT (1 Contract, 3.0R Target) ---")
        for k, v in sm_mnq.items():
            if isinstance(v, float):
                print(f"  {k:25}: {v:,.4f}")
            else:
                print(f"  {k:25}: {v}")

        # Combined daily win rate
        comb = pd.merge(eq_mes[['ts', 'cash']], eq_mnq[['ts', 'cash']], on='ts', how='outer', suffixes=('_mes', '_mnq')).sort_values('ts').ffill().fillna(50000.0)
        comb['pnl'] = (comb['cash_mes'] - 50000.0) + (comb['cash_mnq'] - 50000.0)
        daily = comb.set_index('ts').resample('1D').last().dropna()
        daily['daily_diff'] = daily['pnl'].diff()
        active_days = daily[daily['daily_diff'].abs() > 0.01]
        winning_days = (active_days['daily_diff'] > 0).sum()
        total_active_days = len(active_days)
        daily_win_rate = (winning_days / total_active_days) * 100.0 if total_active_days > 0 else 0

        # Total combined trades
        tot_trades = sm_mes.get('trades', 0) + sm_mnq.get('trades', 0)
        # Approximate combined trade win rate
        mes_wins = round(sm_mes.get('trades', 0) * sm_mes.get('win_rate', 0))
        mnq_wins = round(sm_mnq.get('trades', 0) * sm_mnq.get('win_rate', 0))
        tot_wins = mes_wins + mnq_wins
        tot_win_rate = (tot_wins / tot_trades) * 100.0 if tot_trades > 0 else 0

        print(f"\n--- PORTFOLIO B COMBINED STATS ---")
        print(f"  Combined Net PnL       : ${comb['pnl'].iloc[-1]:,.2f}")
        print(f"  Total Closed Trades    : {tot_trades} ({tot_wins} Wins / {tot_trades - tot_wins} Losses)")
        print(f"  Trade Win Rate         : {tot_win_rate:.2f}%")
        print(f"  Active Trading Days    : {total_active_days}")
        print(f"  Profitable Trading Days: {winning_days} of {total_active_days} ({daily_win_rate:.2f}% Daily Win Rate)")
        print(f"  Avg Gain Per Active Day: ${comb['pnl'].iloc[-1] / total_active_days:,.2f} / day")


if __name__ == '__main__':
    main()

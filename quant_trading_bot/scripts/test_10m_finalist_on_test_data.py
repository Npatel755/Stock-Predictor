"""One-Time Evaluation of 10M Discovery (Portfolio H) on Test Data (2026).
Side-by-side comparison against current champions: Portfolio E (Full & Scaled), Ensemble Beta, and Ensemble Epsilon.
ZERO TUNING on Test or Validation data.
"""
import ast
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


def combine_sleeves(sleeve_dfs):
    merged = sleeve_dfs[0][['ts', 'cash', 'worst']].rename(columns={'cash': 'cash_0', 'worst': 'worst_0'})
    for i, d in enumerate(sleeve_dfs[1:], 1):
        merged = pd.merge(merged, d[['ts', 'cash', 'worst']].rename(columns={'cash': f'cash_{i}', 'worst': f'worst_{i}'}), on='ts', how='outer')
    merged = merged.sort_values('ts').ffill().fillna(50000.0)

    cash_cols = [c for c in merged.columns if c.startswith('cash_')]
    worst_cols = [c for c in merged.columns if c.startswith('worst_')]

    merged['pnl'] = sum(merged[c] - 50000.0 for c in cash_cols)
    merged['worst_pnl'] = sum(merged[w] - 50000.0 for w in worst_cols)
    merged['peak'] = merged['pnl'].cummax()
    merged['intrabar_dd'] = merged['peak'] - merged['worst_pnl']

    net = float(merged['pnl'].iloc[-1])
    dd = float(merged['intrabar_dd'].max())
    return net, dd


def main():
    print("=" * 90)
    print("ONE-TIME TEST DATA (2026) EVALUATION & TOURNAMENT SHOWDOWN")
    print("Zero tuning on Test or Validation data. Canonical event-driven execution.")
    print("=" * 90)

    print("Loading 15m Canonical Bars across all splits...", flush=True)
    splits = {s: {'MES': load_split('MES', s), 'MNQ': load_split('MNQ', s)} for s in ['train', 'validation', 'test']}

    # 1. New 10M Discovery: Portfolio H (MES Hybrid 3c + MNQ Trend 1c)
    cfg_mes_hybrid_3c = {
        'instrument': 'MES', 'family': 'hybrid', 'lookback': 8, 'threshold': 2.0,
        'stop_atr': 1.75, 'target_r': 2.75, 'hold_bars': 24, 'session_start': 585,
        'session_end': 945, 'max_contracts': 3, 'trailing_atr': 3.0, 'config_id': 'm10_27b46f4952b4747a8abc'
    }
    cfg_mes_hybrid_2c = dict(cfg_mes_hybrid_3c, max_contracts=2)

    cfg_mnq_trend_1c = {
        'instrument': 'MNQ', 'family': 'trend', 'lookback': 20, 'threshold': 0.75,
        'stop_atr': 2.0, 'target_r': 3.5, 'hold_bars': 10, 'session_start': 780,
        'session_end': 945, 'max_contracts': 1, 'trailing_atr': 3.0, 'config_id': 'm10_b8a03756ea7cbb9aed74'
    }

    # 2. Portfolio E (Current Champion)
    cfg_port_e_mes_3c = {
        'instrument': 'MES', 'family': 'momentum', 'lookback': 16, 'threshold': 1.5,
        'stop_atr': 1.75, 'target_r': 2.5, 'hold_bars': 32, 'session_start': 585,
        'session_end': 945, 'max_contracts': 3, 'trailing_atr': 2.0, 'config_id': 'm5_77fad21ad8460757ac0d'
    }
    cfg_port_e_mes_2c = dict(cfg_port_e_mes_3c, max_contracts=2)

    cfg_port_e_mnq_2c = {
        'instrument': 'MNQ', 'family': 'breakout', 'lookback': 10, 'threshold': 1.25,
        'stop_atr': 1.75, 'target_r': 2.25, 'hold_bars': 8, 'session_start': 600,
        'session_end': 720, 'max_contracts': 2, 'trailing_atr': 2.0, 'config_id': 'm5v2_dcb23ec10d5f72f84d60'
    }
    cfg_port_e_mnq_1c = dict(cfg_port_e_mnq_2c, max_contracts=1)

    # 3. Ensemble Beta
    cfg_beta_mnq_hyb_1c = {
        'instrument': 'MNQ', 'family': 'hybrid', 'lookback': 20, 'threshold': 1.25,
        'stop_atr': 2.25, 'target_r': 5.0, 'hold_bars': 8, 'session_start': 720,
        'session_end': 945, 'max_contracts': 1, 'trailing_atr': 0.0
    }

    # 4. Ensemble Epsilon
    cfg_eps_mes_1c = dict(cfg_port_e_mes_3c, max_contracts=1)
    cfg_eps_mnq_vol_1c = {
        'instrument': 'MNQ', 'family': 'volatility', 'lookback': 8, 'threshold': 0.5,
        'stop_atr': 2.0, 'target_r': 5.0, 'hold_bars': 32, 'session_start': 600,
        'session_end': 720, 'max_contracts': 1, 'trailing_atr': 4.0
    }
    cfg_eps_mnq_e57_1c = {
        'instrument': 'MNQ', 'family': 'momentum', 'lookback': 16, 'threshold': 1.5,
        'stop_atr': 1.0, 'target_r': 4.0, 'hold_bars': 12, 'session_start': 585,
        'session_end': 945, 'max_contracts': 1, 'trailing_atr': 2.0
    }

    portfolios = [
        ("NEW: Portfolio H (10M Discovery: MES Hyb 3c + MNQ Trend 1c)", [cfg_mes_hybrid_3c, cfg_mnq_trend_1c]),
        ("NEW: Portfolio H Scaled (MES Hyb 2c + MNQ Trend 1c)", [cfg_mes_hybrid_2c, cfg_mnq_trend_1c]),
        ("CHAMPION: Portfolio E Full (MES Mom 3c + MNQ AM Brk 2c)", [cfg_port_e_mes_3c, cfg_port_e_mnq_2c]),
        ("CONSERVATIVE: Portfolio E Scaled (MES Mom 2c + MNQ AM Brk 1c)", [cfg_port_e_mes_2c, cfg_port_e_mnq_1c]),
        ("ENSEMBLE BETA: (MES Mom 2c + MNQ Brk 1c + MNQ Hyb 1c)", [cfg_port_e_mes_2c, cfg_port_e_mnq_1c, cfg_beta_mnq_hyb_1c]),
        ("ENSEMBLE EPSILON: (MES Mom 1c + MNQ Vol 1c + MNQ e57 1c)", [cfg_eps_mes_1c, cfg_eps_mnq_vol_1c, cfg_eps_mnq_e57_1c]),
    ]

    records = []

    for name, cfgs in portfolios:
        row = {'portfolio_name': name}
        split_metrics = {}
        for sp in ['train', 'validation', 'test']:
            dfs = []
            for c in cfgs:
                bars = splits[sp][c['instrument']]
                df, sm = run_strat(c, bars)
                dfs.append(df)
            net, dd = combine_sleeves(dfs)
            split_metrics[sp] = (net, dd)

        row['train_net'] = split_metrics['train'][0]
        row['train_dd'] = split_metrics['train'][1]
        row['val_net'] = split_metrics['validation'][0]
        row['val_dd'] = split_metrics['validation'][1]
        row['test_net'] = split_metrics['test'][0]
        row['test_dd'] = split_metrics['test'][1]
        row['7yr_net'] = round(row['train_net'] + row['val_net'] + row['test_net'], 2)
        row['worst_7yr_dd'] = round(max(row['train_dd'], row['val_dd'], row['test_dd']), 2)
        row['passed_2k'] = bool(row['worst_7yr_dd'] < 2000.0)
        row['weekly_test_pnl'] = round(row['test_net'] / 44.5, 2)
        row['profit_to_dd_test'] = round(row['test_net'] / row['test_dd'], 2) if row['test_dd'] > 0 else 0.0

        records.append(row)

    df_res = pd.DataFrame(records)
    out_csv = ROOT / 'runs/training_search_10m_institutional/tournament_showdown_results.csv'
    df_res.to_csv(out_csv, index=False)

    print("\n" + "=" * 110)
    print("MASTER SHOWDOWN SCOREBOARD: 10M DISCOVERY vs ALL CHAMPIONS ACROSS ALL 7 YEARS")
    print("=" * 110)
    cols = ['portfolio_name', '7yr_net', 'worst_7yr_dd', 'passed_2k', 'test_net', 'test_dd', 'profit_to_dd_test', 'val_net', 'val_dd']
    print(df_res[cols].to_string(index=False))


if __name__ == '__main__':
    main()

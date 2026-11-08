"""Save and audit the Unified Multi-Strategy Ensemble Book (4 Uncorrelated Sleeves)."""
import json
import sys
import ast
import duckdb
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'scripts'))

import mass_research as engine
from mass_metrics import summarize_execution
from quant_futures.data import canonical
from training_5m_v2_policy import execution_cfg_5m_v2

save_dir = ROOT / 'runs/saved_portfolio_F_multi_strategy_ensemble'
save_dir.mkdir(parents=True, exist_ok=True)

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
    ecfg = execution_cfg_5m_v2(cfg)
    res = engine.execute(data, sig, features['atr'], ecfg)
    sm = summarize_execution(res, data)
    ts = pd.to_datetime(data['timestamp'], unit='ns', utc=True)
    df = pd.DataFrame({'ts': ts, 'cash': res['cash'], 'worst': res['worst']})
    return df, sm

splits = {s: {'MES': load_split('MES', s), 'MNQ': load_split('MNQ', s)} for s in ['train', 'validation', 'test']}

# 4 Distinct Uncorrelated Institutional Sleeves
ensemble_config = {
    'sleeves': {
        'sleeve_1_mes_momentum': {
            'instrument': 'MES', 'family': 'momentum', 'lookback': 16, 'threshold': 1.5,
            'stop_atr': 1.75, 'target_r': 2.5, 'hold_bars': 32, 'session_start': 585,
            'session_end': 945, 'max_contracts': 2, 'trailing_atr': 2.0,
            'role': 'S&P 500 Intraday Momentum Anchor'
        },
        'sleeve_2_mnq_volatility': {
            'instrument': 'MNQ', 'family': 'volatility', 'lookback': 8, 'threshold': 0.5,
            'stop_atr': 2.0, 'target_r': 5.0, 'hold_bars': 32, 'session_start': 600,
            'session_end': 720, 'max_contracts': 1, 'trailing_atr': 4.0,
            'role': 'Nasdaq Morning Volatility Expansion (Claude Top Earner)'
        },
        'sleeve_3_mnq_morning_breakout': {
            'instrument': 'MNQ', 'family': 'breakout', 'lookback': 10, 'threshold': 1.25,
            'stop_atr': 1.75, 'target_r': 2.25, 'hold_bars': 8, 'session_start': 600,
            'session_end': 720, 'max_contracts': 1, 'trailing_atr': 2.0,
            'role': 'Nasdaq Morning Impulse Breakout'
        },
        'sleeve_4_mnq_afternoon_runner': {
            'instrument': 'MNQ', 'family': 'hybrid', 'lookback': 20, 'threshold': 1.25,
            'stop_atr': 2.25, 'target_r': 5.0, 'hold_bars': 8, 'session_start': 720,
            'session_end': 945, 'max_contracts': 1, 'trailing_atr': 0.0,
            'role': 'Nasdaq Afternoon Trend Continuation'
        }
    }
}

json.dump(ensemble_config, open(save_dir / 'ensemble_config.json', 'w'), indent=2)

def evaluate_ensemble_split(split_name):
    sleeve_dfs = []
    sleeve_summaries = {}
    for sname, scfg in ensemble_config['sleeves'].items():
        bars = splits[split_name][scfg['instrument']]
        df, sm = run_strat(scfg, bars)
        sleeve_dfs.append(df)
        sleeve_summaries[sname] = {
            'net_pnl': sm.get('net_pnl', 0.0),
            'trades': sm.get('trades', 0),
            'win_rate': sm.get('win_rate', 0.0),
            'profit_factor': sm.get('profit_factor', 0.0),
            'intrabar_dd': sm.get('intrabar_drawdown', 0.0)
        }
    
    merged = sleeve_dfs[0][['ts', 'cash', 'worst']].rename(columns={'cash': 'cash_0', 'worst': 'worst_0'})
    for i, d in enumerate(sleeve_dfs[1:], 1):
        merged = pd.merge(merged, d[['ts', 'cash', 'worst']].rename(columns={'cash': f'cash_{i}', 'worst': f'worst_{i}'}), on='ts', how='outer')
    merged = merged.sort_values('ts').ffill().fillna(50000.0)
    
    cash_cols = [c for c in merged.columns if c.startswith('cash_')]
    worst_cols = [c for c in merged.columns if c.startswith('worst_')]
    
    merged['pnl'] = sum(merged[c] - 50000.0 for c in cash_cols)
    merged['worst_pnl'] = sum(merged[w] - 50000.0 for w in worst_cols)
    merged['peak'] = merged['pnl'].cummax()
    merged['closed_dd'] = merged['peak'] - merged['pnl']
    merged['intrabar_dd'] = merged['peak'] - merged['worst_pnl']
    
    merged.to_csv(save_dir / f'equity_{split_name}.csv', index=False)
    
    return {
        'net_pnl': float(merged['pnl'].iloc[-1]),
        'closed_max_dd': float(merged['closed_dd'].max()),
        'intrabar_max_dd': float(merged['intrabar_dd'].max()),
        'cushion_to_2k': float(2000.0 - merged['intrabar_dd'].max()),
        'sleeves': sleeve_summaries
    }

train_res = evaluate_ensemble_split('train')
val_res = evaluate_ensemble_split('validation')
test_res = evaluate_ensemble_split('test')

test_res['avg_weekly_gain'] = test_res['net_pnl'] / 44.5
test_res['avg_monthly_gain'] = test_res['avg_weekly_gain'] * 4.333
test_res['weeks_to_pass_3k'] = 3000.0 / test_res['avg_weekly_gain']

summary = {
    'portfolio_name': 'Portfolio F: Unified Multi-Strategy Ensemble Book (4 Sleeves)',
    'structure': 'MES Momentum (2c) + MNQ Volatility (1c) + MNQ Morning Breakout (1c) + MNQ Afternoon Hybrid (1c)',
    'test_2026': test_res,
    'validation_2024_2025': val_res,
    'train_2020_2023': train_res,
    '7_year_lifetime_net': train_res['net_pnl'] + val_res['net_pnl'] + test_res['net_pnl'],
    'worst_historical_intrabar_dd': max(train_res['intrabar_max_dd'], val_res['intrabar_max_dd'], test_res['intrabar_max_dd'])
}

json.dump(summary, open(save_dir / 'summary.json', 'w'), indent=2)
print("Saved Portfolio F Multi-Strategy Ensemble Book successfully!")
print(f"2026 Test Net PnL:     +${test_res['net_pnl']:,.2f}  |  Drawdown: ${test_res['intrabar_max_dd']:,.2f}")
print(f"Validation Net PnL:    +${val_res['net_pnl']:,.2f}  |  Drawdown: ${val_res['intrabar_max_dd']:,.2f}")
print(f"Training Net PnL:      +${train_res['net_pnl']:,.2f} |  Drawdown: ${train_res['intrabar_max_dd']:,.2f}")
print(f"7-Year Lifetime Net:   +${summary['7_year_lifetime_net']:,.2f}")

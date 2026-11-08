"""Calculate precise distribution of time to clear the $3,000 target for top strategies."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import ast
import json
from pathlib import Path
import sys
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
import mass_research as engine
from quant_futures.data import canonical
import duckdb

CATALOG = json.load(open(ROOT / 'data/catalog.json'))

tree = ast.parse((ROOT / 'runs/training_search_500k_v1/code/mass_research.py').read_text(encoding='utf-8'))
query = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith('SELECT time_bucket')][0]


def load_bars(symbol, phase):
    p = CATALOG['instruments'][symbol]['splits'][phase]['path']
    con = duckdb.connect()
    try:
        bars = canonical(con.execute(query, [str(p)]).fetch_df())
    finally:
        con.close()
    return bars


STRATEGIES = [
    {
        'id': 'highr_67706898fdef6762c15a',
        'name': '1. MNQ Regime (4.0R, 3c) — Fastest Overall Velocity',
        'instrument': 'MNQ',
        'params': {
            'instrument': 'MNQ', 'family': 'regime', 'lookback': 24,
            'threshold': 1.5, 'stop_atr': 0.75, 'target_r': 4.0,
            'hold_bars': 12, 'session_start': 585, 'session_end': 945,
            'max_contracts': 3, 'trailing_atr': 2.5,
            'config_id': 'highr_67706898fdef6762c15a'
        }
    },
    {
        'id': 'mass_4a0b95329be1d0438243',
        'name': '2. MNQ Breakout (3c) — Benchmark High-Activity',
        'instrument': 'MNQ',
        'params': {
            'instrument': 'MNQ', 'family': 'breakout', 'lookback': 32,
            'threshold': 0.75, 'stop_atr': 1.0, 'target_r': 4.0,
            'hold_bars': 16, 'session_start': 585, 'session_end': 945,
            'max_contracts': 3, 'trailing_atr': 1.0,
            'config_id': 'mass_4a0b95329be1d0438243'
        }
    },
    {
        'id': 'mass_e57_scaled_2c',
        'name': '3. MNQ Momentum Scaled (2c) — Safest High Pass Rate',
        'instrument': 'MNQ',
        'params': {
            'instrument': 'MNQ', 'family': 'momentum', 'lookback': 16,
            'threshold': 1.5, 'stop_atr': 1.0, 'target_r': 4.0,
            'hold_bars': 12, 'session_start': 585, 'session_end': 945,
            'max_contracts': 2, 'trailing_atr': 2.0,
            'config_id': 'mass_e57_scaled_2c'
        }
    },
    {
        'id': 'highr_9cd4acba4cbb1a864e7f',
        'name': '4. MES Trend (8.0R, 3c) — S&P 500 High-R Runner',
        'instrument': 'MES',
        'params': {
            'instrument': 'MES', 'family': 'trend', 'lookback': 8,
            'threshold': 1.0, 'stop_atr': 0.75, 'target_r': 8.0,
            'hold_bars': 24, 'session_start': 585, 'session_end': 945,
            'max_contracts': 3, 'trailing_atr': 2.5,
            'config_id': 'highr_9cd4acba4cbb1a864e7f'
        }
    }
]

TEMP_DIR = ROOT / 'runs/temp_velocity_audit'
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Preload bars for both Validation and Test
bars_cache = {
    ('MNQ', 'validation'): load_bars('MNQ', 'validation'),
    ('MNQ', 'test'): load_bars('MNQ', 'test'),
    ('MES', 'validation'): load_bars('MES', 'validation'),
    ('MES', 'test'): load_bars('MES', 'test')
}

data_cache = {k: engine.arrays(v) for k, v in bars_cache.items()}
features_cache = {}

results = []

for s in STRATEGIES:
    sym = s['instrument']
    params = s['params']
    cid = s['id']
    
    oos_trades = []
    
    for phase in ['validation', 'test']:
        bars = bars_cache[(sym, phase)]
        data = data_cache[(sym, phase)]
        
        fk = (sym, phase, params['lookback'])
        if fk not in features_cache:
            features_cache[fk] = engine.features(bars, params['lookback'])
        features = features_cache[fk]
        
        sig = engine.masked_signal(bars, params, features)
        fold = [dict(label=phase, start=0, stop=len(bars), embargo_bars=96, purge_bars=16)]
        
        engine.evaluate_configuration(params, bars, data, fold, features, sig, save=True, folder=TEMP_DIR)
        t_file = TEMP_DIR / f"{params['config_id']}_{phase}_trades.parquet"
        
        if t_file.exists():
            tdf = pd.read_parquet(t_file)
            tdf['phase'] = phase
            oos_trades.append(tdf)
            t_file.unlink()
            
    df = pd.concat(oos_trades, ignore_index=True)
    df['entry_time'] = pd.to_datetime(df['entry_time'])
    df['exit_time'] = pd.to_datetime(df['exit_time'])
    df = df.sort_values('exit_time').reset_index(drop=True)
    
    total_trades = len(df)
    
    # Rolling Start Evaluation across Out-of-Sample Trades
    attempts = 0
    passes = 0
    pass_days = []
    pass_weeks = []
    pass_trades = []
    
    for start_idx in range(0, max(1, total_trades - 15)):
        attempts += 1
        sub = df.iloc[start_idx:].reset_index(drop=True)
        running_net = 0.0
        peak = 0.0
        start_t = sub['entry_time'].iloc[0]
        passed = False
        
        for t_i, row in sub.iterrows():
            running_net += row['net_pnl']
            peak = max(peak, running_net)
            dd = peak - running_net
            if dd >= 2000.0:  # Failed liquidation
                passed = False
                break
            if running_net >= 3000.0:  # Cleared $3,000!
                passed = True
                days = (row['exit_time'] - start_t).days
                pass_days.append(days)
                pass_weeks.append(round(days / 7.0, 1))
                pass_trades.append(t_i + 1)
                passes += 1
                break
                
    pass_rate = (passes / attempts * 100.0) if attempts > 0 else 0.0
    
    fastest_d = int(np.min(pass_days)) if pass_days else 0
    fastest_w = round(fastest_d / 7.0, 1)
    fastest_tr = int(np.min(pass_trades)) if pass_trades else 0
    
    p25_d = float(np.percentile(pass_days, 25)) if pass_days else 0.0
    p25_w = round(p25_d / 7.0, 1)
    
    median_d = float(np.median(pass_days)) if pass_days else 0.0
    median_w = round(median_d / 7.0, 1)
    median_tr = int(np.median(pass_trades)) if pass_trades else 0
    
    p75_d = float(np.percentile(pass_days, 75)) if pass_days else 0.0
    p75_w = round(p75_d / 7.0, 1)
    
    res = {
        'id': cid,
        'name': s['name'],
        'instrument': sym,
        'pass_rate_pct': round(pass_rate, 1),
        'fastest_weeks': fastest_w,
        'fastest_days': fastest_d,
        'fastest_trades': fastest_tr,
        'p25_weeks': p25_w,
        'p25_days': p25_d,
        'median_weeks': median_w,
        'median_days': median_d,
        'median_trades': median_tr,
        'p75_weeks': p75_w,
        'p75_days': p75_d,
        'total_oos_trades': total_trades
    }
    results.append(res)
    print(f"\n{s['name']}:")
    print(f"  Pass Rate (Never hits $2k DD): {pass_rate:.1f}%")
    print(f"  FASTEST to Pass $3k:           {fastest_w} weeks ({fastest_d} days, {fastest_tr} trades)")
    print(f"  25th Percentile (Good Pace):   {p25_w} weeks ({p25_d:.0f} days)")
    print(f"  TYPICAL / MEDIAN Time to Pass: {median_w} weeks ({median_d:.0f} days, {median_tr} trades)")
    print(f"  75th Percentile (Slow Pace):   {p75_w} weeks ({p75_d:.0f} days)")

json.dump(results, open(ROOT / 'reports/pass_velocity_distribution.json', 'w'), indent=2)

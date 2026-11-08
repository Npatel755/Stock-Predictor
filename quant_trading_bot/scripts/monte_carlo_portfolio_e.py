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

bars_mes = {
    'train': load_split_bars('MES', 'train'),
    'validation': load_split_bars('MES', 'validation'),
    'test': load_split_bars('MES', 'test'),
}
bars_mes['train'] = bars_mes['train'][bars_mes['train']['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)

bars_mnq = {
    'train': load_split_bars('MNQ', 'train'),
    'validation': load_split_bars('MNQ', 'validation'),
    'test': load_split_bars('MNQ', 'test'),
}
bars_mnq['train'] = bars_mnq['train'][bars_mnq['train']['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)

_MES_MOM = dict(instrument="MES", family="momentum", lookback=16, threshold=1.5, stop_atr=1.75,
                target_r=2.5, hold_bars=32, session_start=585, session_end=945, trailing_atr=2.0)
_MNQ_BRK = dict(instrument="MNQ", family="breakout", lookback=10, threshold=1.25, stop_atr=1.75,
                target_r=2.25, hold_bars=8, session_start=600, session_end=720, trailing_atr=2.0)

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
    ts = pd.to_datetime(data['timestamp'], unit='ns', utc=True)
    df = pd.DataFrame({'ts': ts, 'cash': res['cash'], 'worst': res['worst']})
    return df

def get_daily_pnls(sleeves):
    daily_returns = []
    for split in ['train', 'validation', 'test']:
        dfs = []
        for sname, scfg, contracts in sleeves:
            cfg = dict(scfg, max_contracts=contracts)
            bars = bars_mes[split] if cfg['instrument'] == 'MES' else bars_mnq[split]
            df = run_sleeve(cfg, bars)
            dfs.append(df)
            
        m = dfs[0][['ts', 'cash', 'worst']].rename(columns={'cash': 'c_0', 'worst': 'w_0'})
        for i in range(1, len(dfs)):
            m = pd.merge(m, dfs[i][['ts', 'cash', 'worst']].rename(columns={'cash': f'c_{i}', 'worst': f'w_{i}'}), on='ts', how='outer')
        m = m.sort_values('ts').ffill().fillna(50000.0)
        
        c_tot = 50000.0
        for i in range(len(dfs)):
            c_tot += (m[f'c_{i}'].to_numpy() - 50000.0)
        m['tot_cash'] = c_tot
        m['date'] = m['ts'].dt.tz_convert('America/New_York').dt.date
        daily = m.groupby('date')['tot_cash'].last().diff().dropna().values
        daily_returns.extend(daily)
        
    return np.array(daily_returns)

np.random.seed(42)

def run_monte_carlo(name, daily_pnls, n_sims=10000, horizon_days=250, block_size=5):
    n_days = len(daily_pnls)
    n_blocks = horizon_days // block_size
    
    breaches_count = 0
    ending_profits = []
    max_dds = []
    
    for _ in range(n_sims):
        # sample blocks
        start_indices = np.random.randint(0, n_days - block_size + 1, size=n_blocks)
        sampled_pnls = np.concatenate([daily_pnls[idx:idx+block_size] for idx in start_indices])
        
        equity = np.cumsum(sampled_pnls)
        peaks = np.maximum.accumulate(equity)
        dds = peaks - equity
        max_dd = np.max(dds)
        max_dds.append(max_dd)
        ending_profits.append(equity[-1])
        
        if max_dd >= 2000.0:
            breaches_count += 1
            
    breach_prob = (breaches_count / n_sims) * 100.0
    mean_profit = np.mean(ending_profits)
    p5_profit = np.percentile(ending_profits, 5)
    p95_profit = np.percentile(ending_profits, 95)
    mean_dd = np.mean(max_dds)
    p95_dd = np.percentile(max_dds, 95)
    
    print(f"==================================================")
    print(f"MONTE CARLO (10,000 SIMULATIONS, 250 TRADING DAYS)")
    print(f"Candidate: {name}")
    print(f"==================================================")
    print(f"Ruin / Breach Risk (DD >= $2,000) : {breach_prob:.2f}%")
    print(f"Expected Annual Net Profit        : +${mean_profit:,.2f}")
    print(f"5th Percentile Profit (Worst 5%)   : +${p5_profit:,.2f}")
    print(f"95th Percentile Profit (Best 5%)  : +${p95_profit:,.2f}")
    print(f"Average Max Drawdown              : ${mean_dd:,.2f}")
    print(f"95th Percentile Max Drawdown      : ${p95_dd:,.2f}")
    print()

pnls_scaled = get_daily_pnls([("MES_2c", _MES_MOM, 2), ("MNQ_2c", _MNQ_BRK, 2)])
run_monte_carlo("Portfolio E Scaled (MES 2c + MNQ 2c)", pnls_scaled)

pnls_cons = get_daily_pnls([("MES_1c", _MES_MOM, 1), ("MNQ_2c", _MNQ_BRK, 2)])
run_monte_carlo("Portfolio E Conservative (MES 1c + MNQ 2c)", pnls_cons)

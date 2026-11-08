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
    return pd.concat(dfs, ignore_index=True).sort_values('timestamp_utc').drop_duplicates('timestamp_utc').reset_index(drop=True)

bars_mnq = load_all_bars('MNQ')

# Candidate sleeves
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

def extract_trades(cfg, bars):
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
    
    trades = []
    for i in range(len(res['trade_net'])):
        t_exit = pd.to_datetime(data['timestamp'][res['trade_exit'][i]], unit='ns', utc=True)
        trades.append({
            'exit_ts': t_exit,
            'net': float(res['trade_net'][i]),
            'sleeve': cfg['family'],
        })
    return pd.DataFrame(trades)

t_brk = extract_trades(mnq_morning_breakout_2c, bars_mnq)
t_trd = extract_trades(mnq_afternoon_trend_1c, bars_mnq)
all_trades = pd.concat([t_brk, t_trd]).sort_values('exit_ts').reset_index(drop=True)

print(f"Total chronological trades: {len(all_trades)}")
pnls = all_trades['net'].to_numpy()

# Monte Carlo: 10,000 Block-Bootstrapped Simulations of 250 trading days
N_SIMS = 10000
BLOCK_SIZE = 5  # preserve short-term auto-correlation
n_trades = len(pnls)

rng = np.random.default_rng(20261108)
breaches = 0
max_dds = []

for _ in range(N_SIMS):
    # generate random sequence of blocks
    n_blocks = int(np.ceil(250 / BLOCK_SIZE))
    block_starts = rng.integers(0, n_trades - BLOCK_SIZE, size=n_blocks)
    sim_pnls = np.concatenate([pnls[idx:idx+BLOCK_SIZE] for idx in block_starts])[:250]
    
    curve = np.cumsum(sim_pnls)
    peak = np.maximum.accumulate(curve)
    dd = np.max(peak - curve)
    max_dds.append(dd)
    if dd >= 2000.0:
        breaches += 1

max_dds = np.array(max_dds)
breach_prob = (breaches / N_SIMS) * 100.0

print(f"10,000 Monte Carlo Simulations (250-Trade Sequences):")
print(f"  Breach Risk ($2,000 DD): {breach_prob:.2f}%")
print(f"  Median Max Drawdown:    ${np.median(max_dds):,.2f}")
print(f"  95th Percentile DD:     ${np.percentile(max_dds, 95):,.2f}")
print(f"  99th Percentile DD:     ${np.percentile(max_dds, 99):,.2f}")
print(f"  Maximum Observed DD:    ${np.max(max_dds):,.2f}")

# Evaluate Portfolio 1 (1 contract on both)
t_brk1 = extract_trades(dict(mnq_morning_breakout_2c, max_contracts=1), bars_mnq)
all_trades1 = pd.concat([t_brk1, t_trd]).sort_values('exit_ts').reset_index(drop=True)
pnls1 = all_trades1['net'].to_numpy()

breaches1 = 0
max_dds1 = []
for _ in range(N_SIMS):
    n_blocks = int(np.ceil(250 / BLOCK_SIZE))
    block_starts = rng.integers(0, len(pnls1) - BLOCK_SIZE, size=n_blocks)
    sim_pnls = np.concatenate([pnls1[idx:idx+BLOCK_SIZE] for idx in block_starts])[:250]
    curve = np.cumsum(sim_pnls)
    peak = np.maximum.accumulate(curve)
    dd = np.max(peak - curve)
    max_dds1.append(dd)
    if dd >= 2000.0:
        breaches1 += 1

max_dds1 = np.array(max_dds1)
print(f"\nPortfolio 1 (Pure 1-Contract on Both Sleeves):")
print(f"  Breach Risk ($2,000 DD): {(breaches1 / N_SIMS) * 100:.2f}%")
print(f"  Median Max Drawdown:    ${np.median(max_dds1):,.2f}")
print(f"  95th Percentile DD:     ${np.percentile(max_dds1, 95):,.2f}")
print(f"  99th Percentile DD:     ${np.percentile(max_dds1, 99):,.2f}")

import json
from pathlib import Path
import sys
import duckdb
import numpy as np
import pandas as pd
import ast
from itertools import product

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

print("Loading 2020-2023 Training Bars...")
bars_mes_tr = load_split_bars('MES', 'train')
bars_mes_tr = bars_mes_tr[bars_mes_tr['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)

bars_mnq_tr = load_split_bars('MNQ', 'train')
bars_mnq_tr = bars_mnq_tr[bars_mnq_tr['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)

data_mes = apply_early_close(engine.arrays(bars_mes_tr), bars_mes_tr)
data_mnq = apply_early_close(engine.arrays(bars_mnq_tr), bars_mnq_tr)

# Generate Candidate Space on Training Data
# Families: trend, momentum, breakout, mean_reversion, vwap, volume, hybrid
FAMILIES = ['trend', 'momentum', 'breakout', 'mean_reversion', 'vwap', 'volume', 'hybrid']
LOOKBACKS = [8, 12, 16, 20]
THRESHOLDS = [1.0, 1.25, 1.5, 2.0]
STOPS = [1.25, 1.5, 1.75]
TARGETS = [1.5, 2.0, 2.5, 3.0]
HOLDS = [8, 12, 16, 24]
SESSIONS = [
    ('all_day', 585, 945),
    ('am_peak', 600, 720),
    ('pm_close', 780, 945)
]

# Pre-compute features for each lookback
print("Pre-computing feature frames for lookbacks...")
features_mes = {lb: engine.features(bars_mes_tr, lb) for lb in LOOKBACKS}
features_mnq = {lb: engine.features(bars_mnq_tr, lb) for lb in LOOKBACKS}

local_mes = bars_mes_tr.timestamp_utc.dt.tz_convert('America/New_York')
decision_mes = (local_mes.dt.hour * 60 + local_mes.dt.minute + 15).to_numpy()
weekdays_mes = local_mes.dt.weekday.to_numpy() < 5

local_mnq = bars_mnq_tr.timestamp_utc.dt.tz_convert('America/New_York')
decision_mnq = (local_mnq.dt.hour * 60 + local_mnq.dt.minute + 15).to_numpy()
weekdays_mnq = local_mnq.dt.weekday.to_numpy() < 5

def run_single(sym, fam, lb, th, st, tg, hd, s_start, s_end):
    cfg = {
        'instrument': sym, 'family': fam, 'lookback': lb, 'threshold': th,
        'stop_atr': st, 'target_r': tg, 'hold_bars': hd,
        'session_start': s_start, 'session_end': s_end,
        'max_contracts': 1, 'trailing_atr': 0.0
    }
    bars = bars_mes_tr if sym == 'MES' else bars_mnq_tr
    data = data_mes if sym == 'MES' else data_mnq
    feat = features_mes[lb] if sym == 'MES' else features_mnq[lb]
    decision = decision_mes if sym == 'MES' else decision_mnq
    weekdays = weekdays_mes if sym == 'MES' else weekdays_mnq
    
    raw_sig = engine.signal_for(cfg, feat).astype(np.int8)
    mask = (decision >= s_start) & (decision < s_end) & weekdays
    sig = np.where(mask, raw_sig, 0).astype(np.int8)
    
    ecfg = execution_cfg_10m(cfg)
    res = engine.execute(data, sig, feat['atr'], ecfg)
    sm = engine.summarize_execution(res, data)
    
    # Check basic quality on training
    if sm['trades'] < 40 or sm['net_pnl'] <= 500 or sm['intrabar_drawdown'] > 750 or sm['profit_factor'] < 1.3:
        return None
        
    ts = pd.to_datetime(data['timestamp'], unit='ns', utc=True)
    df = pd.DataFrame({'ts': ts, 'cash': res['cash'], 'worst': res['worst']})
    return cfg, sm, df

print("Screening independent 1-contract sleeves across families on Training Data (2020-2023)...")
candidates_mes = []
candidates_mnq = []

sample_configs = []
for fam in FAMILIES:
    for lb in LOOKBACKS:
        for th in THRESHOLDS:
            for st in STOPS:
                for tg in TARGETS:
                    for hd in HOLDS:
                        for s_label, s_start, s_end in SESSIONS:
                            sample_configs.append((fam, lb, th, st, tg, hd, s_start, s_end))

# Downsample grid systematically to ~2,000 configurations per instrument
np.random.seed(42)
sampled_idx = np.random.choice(len(sample_configs), size=min(1500, len(sample_configs)), replace=False)
selected_configs = [sample_configs[i] for i in sampled_idx]

print(f"Evaluating {len(selected_configs)} configurations per asset...")

for params in selected_configs:
    res_m = run_single('MES', *params)
    if res_m is not None:
        candidates_mes.append(res_m)
        
    res_q = run_single('MNQ', *params)
    if res_q is not None:
        candidates_mnq.append(res_q)

print(f"Qualified 1c MES Sleeves: {len(candidates_mes)}")
print(f"Qualified 1c MNQ Sleeves: {len(candidates_mnq)}")

# Save intermediate summary
summary = {
    'mes_count': len(candidates_mes),
    'mnq_count': len(candidates_mnq),
    'top_mes': [{'fam': c[0]['family'], 'net': c[1]['net_pnl'], 'dd': c[1]['intrabar_drawdown'], 'pf': c[1]['profit_factor'], 'trades': c[1]['trades'], 'exp': c[1]['net_pnl']/c[1]['trades']} for c in sorted(candidates_mes, key=lambda x: x[1]['net_pnl'], reverse=True)[:10]],
    'top_mnq': [{'fam': c[0]['family'], 'net': c[1]['net_pnl'], 'dd': c[1]['intrabar_drawdown'], 'pf': c[1]['profit_factor'], 'trades': c[1]['trades'], 'exp': c[1]['net_pnl']/c[1]['trades']} for c in sorted(candidates_mnq, key=lambda x: x[1]['net_pnl'], reverse=True)[:10]],
}

out_p = ROOT / 'runs/training_orthogonal_sleeves.json'
json.dump(summary, open(out_p, 'w'), indent=2)
print(f"Saved summary to {out_p}")

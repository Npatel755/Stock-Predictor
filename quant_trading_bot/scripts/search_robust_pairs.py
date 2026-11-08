import ast
import json
from pathlib import Path
import sys
import duckdb
import numpy as np
import pandas as pd

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

print("Loading bars...")
bars_mes_train = load_split_bars('MES', 'train')
bars_mes_train = bars_mes_train[bars_mes_train['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)
bars_mes_val = load_split_bars('MES', 'validation')

bars_mnq_train = load_split_bars('MNQ', 'train')
bars_mnq_train = bars_mnq_train[bars_mnq_train['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)
bars_mnq_val = load_split_bars('MNQ', 'validation')

# Read qualifiers
df_ranked = pd.read_csv(ROOT / 'runs/training_search_10m_institutional/ranked.csv')
mes_qual = df_ranked[df_ranked['instrument'] == 'MES'].sort_values('champ_score', ascending=False)
mnq_qual = df_ranked[df_ranked['instrument'] == 'MNQ'].sort_values('champ_score', ascending=False)

# Add Portfolio E legs to candidate pools
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
    sm = engine.summarize_execution(res, data)
    ts = pd.to_datetime(data['timestamp'], unit='ns', utc=True)
    df = pd.DataFrame({'ts': ts, 'cash': res['cash'], 'worst': res['worst']})
    return df, sm

# Select top MES candidates
mes_candidates = [cfg_port_e_mes_2c, cfg_port_e_mes_3c]
for _, row in mes_qual.head(25).iterrows():
    p = json.loads(row['payload'])
    if 'payload' in p:
        p = json.loads(p['payload'])
    mes_candidates.append(p)

# Select top MNQ candidates
mnq_candidates = [cfg_port_e_mnq_2c, cfg_port_e_mnq_1c]
for _, row in mnq_qual.head(25).iterrows():
    p = json.loads(row['payload'])
    if 'payload' in p:
        p = json.loads(p['payload'])
    mnq_candidates.append(p)

print(f"Pre-running {len(mes_candidates)} MES candidates and {len(mnq_candidates)} MNQ candidates on Training...")

mes_train_runs = {}
for c in mes_candidates:
    cid = c['config_id'] + f"_{c.get('max_contracts', 1)}c"
    if cid not in mes_train_runs:
        df, sm = run_sleeve(c, bars_mes_train)
        mes_train_runs[cid] = (c, df, sm)

mnq_train_runs = {}
for c in mnq_candidates:
    cid = c['config_id'] + f"_{c.get('max_contracts', 1)}c"
    if cid not in mnq_train_runs:
        df, sm = run_sleeve(c, bars_mnq_train)
        mnq_train_runs[cid] = (c, df, sm)

print("Evaluating pair combinations on Training data...")
pair_results = []

for mes_id, (c_mes, df_mes, sm_mes) in mes_train_runs.items():
    for mnq_id, (c_mnq, df_mnq, sm_mnq) in mnq_train_runs.items():
        merged = pd.merge(
            df_mes[['ts', 'cash', 'worst']].rename(columns={'cash': 'c_mes', 'worst': 'w_mes'}),
            df_mnq[['ts', 'cash', 'worst']].rename(columns={'cash': 'c_mnq', 'worst': 'w_mnq'}),
            on='ts', how='outer'
        ).sort_values('ts').ffill().fillna(50000.0)

        merged['comb_cash'] = 50000.0 + (merged['c_mes'] - 50000.0) + (merged['c_mnq'] - 50000.0)
        merged['comb_worst'] = 50000.0 + (merged['w_mes'] - 50000.0) + (merged['w_mnq'] - 50000.0)

        net = merged['comb_cash'].iloc[-1] - 50000.0
        peak = merged['comb_cash'].cummax()
        dd = (peak - merged['comb_worst']).max()

        # Check annual consistency across 2020-2023
        merged['year'] = merged['ts'].dt.year
        annual_nets = []
        annual_dds = []
        for y, g in merged.groupby('year'):
            yn = g['comb_cash'].iloc[-1] - g['comb_cash'].iloc[0]
            yp = g['comb_cash'].cummax()
            yd = (yp - g['comb_worst']).max()
            annual_nets.append(yn)
            annual_dds.append(yd)

        min_annual_net = min(annual_nets) if annual_nets else -9999
        max_annual_dd = max(annual_dds) if annual_dds else 9999
        all_positive = all(yn > 0 for yn in annual_nets) and len(annual_nets) == 4

        # Stability score: reward high net, low drawdown, AND consistency (high min annual net)
        stability_score = (net / dd) * (min_annual_net / 1000.0) if dd > 0 and min_annual_net > 0 else -1.0

        if dd < 1500.0 and all_positive and net > 12000.0:
            pair_results.append({
                'mes_id': mes_id,
                'mnq_id': mnq_id,
                'mes_cfg': c_mes,
                'mnq_cfg': c_mnq,
                'train_net': net,
                'train_dd': dd,
                'min_annual_net': min_annual_net,
                'max_annual_dd': max_annual_dd,
                'stability_score': stability_score,
                'annual_nets': annual_nets,
            })

df_pairs = pd.DataFrame(pair_results).sort_values('stability_score', ascending=False)
print(f"\nFound {len(df_pairs)} qualifying pairs with Training DD < $1,500 and 4/4 positive years!")
print(df_pairs[['mes_id', 'mnq_id', 'train_net', 'train_dd', 'min_annual_net', 'stability_score']].head(10).to_string())

# Save top 10 finalists
top_pairs = df_pairs.head(10).to_dict(orient='records')
Path(ROOT / 'runs/robust_pairs_finalists.json').write_text(json.dumps(top_pairs, indent=2, default=str))

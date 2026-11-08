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

print("Loading Train data (2020-2023)...")
bars_mes_train = load_split_bars('MES', 'train')
bars_mes_train = bars_mes_train[bars_mes_train['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)

bars_mnq_train = load_split_bars('MNQ', 'train')
bars_mnq_train = bars_mnq_train[bars_mnq_train['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)

def run_sleeve_sim(cfg, bars, fee=0.61):
    data = apply_early_close(engine.arrays(bars), bars)
    features = engine.features(bars, int(cfg['lookback']))
    sig = engine.masked_signal(bars, cfg, features)
    ecfg = engine.execution_cfg(cfg)
    ecfg['commission_per_side'] = fee
    
    res = engine.execute(data, sig, features['atr'], ecfg)
    sm = engine.summarize_execution(res, data)
    ts = pd.to_datetime(data['timestamp'], unit='ns', utc=True)
    
    # Track pnl relative to starting balance
    pnl = res['cash'] - ecfg['initial_balance']
    worst_pnl = res['worst'] - ecfg['initial_balance']
    df = pd.DataFrame({'ts': ts, 'pnl': pnl, 'worst_pnl': worst_pnl})
    return df, sm, res

# Load qualifiers from pure_1c_training_qualifiers.json
with open(ROOT / 'runs/pure_1c_training_qualifiers.json') as f:
    qualifiers = json.load(f)

top_mes = qualifiers['mes'][0]['cfg']
top_mnq_brk = [q['cfg'] for q in qualifiers['mnq'] if q['cfg']['family'] == 'breakout'][0]
top_mnq_trd = [q['cfg'] for q in qualifiers['mnq'] if q['cfg']['family'] == 'trend'][0]

sleeves = [
    ('MES_Trend_1c', top_mes),
    ('MNQ_MornBrk_1c', top_mnq_brk),
    ('MNQ_Trend_1c', top_mnq_trd),
]

print("\n--- INDIVIDUAL SLEEVES ON TRAINING (2020-2023) AT $0.61 FEE ---")
results = []
for sname, scfg in sleeves:
    bars = bars_mes_train if scfg['instrument'] == 'MES' else bars_mnq_train
    df, sm, res = run_sleeve_sim(scfg, bars, fee=0.61)
    results.append((sname, df, sm))
    print(f"{sname:16}: Net = ${sm['net_pnl']:>8,.2f} | Intrabar DD = ${sm['intrabar_drawdown']:>6.2f} | Closed DD = ${sm['max_drawdown']:>6.2f} | Trades = {sm['trades']:>3} | PF = {sm['profit_factor']:.2f}")

# Pairwise & 3-way combinations
def evaluate_combo(name, active_results):
    m = active_results[0][1][['ts', 'pnl', 'worst_pnl']].rename(columns={'pnl': 'pnl_0', 'worst_pnl': 'w_0'})
    for i in range(1, len(active_results)):
        df_i = active_results[i][1][['ts', 'pnl', 'worst_pnl']].rename(columns={'pnl': f'pnl_{i}', 'worst_pnl': f'w_{i}'})
        m = pd.merge(m, df_i, on='ts', how='outer')
    m = m.sort_values('ts').ffill().fillna(0.0)
    
    m['pnl_comb'] = sum(m[f'pnl_{i}'] for i in range(len(active_results)))
    # Intrabar drawdown
    peak_pnl = m['pnl_comb'].cummax()
    m['open_draw'] = sum((m[f'pnl_{i}'] - m[f'w_{i}']) for i in range(len(active_results)))
    intrabar_dd = (peak_pnl - (m['pnl_comb'] - m['open_draw'])).max()
    closed_dd = (peak_pnl - m['pnl_comb']).max()
    net = m['pnl_comb'].iloc[-1]
    trades = sum(r[2]['trades'] for r in active_results)
    cushion = 2000.0 - intrabar_dd
    
    print(f"\n==========================================")
    print(f"COMBO: {name}")
    print(f"==========================================")
    print(f"Net P&L (2020-2023):       ${net:,.2f}")
    print(f"Max Intrabar Drawdown:     ${intrabar_dd:.2f}")
    print(f"Max Closed Drawdown:       ${closed_dd:.2f}")
    print(f"Safety Cushion to $2,000:  ${cushion:.2f}")
    print(f"Total Trades:              {trades}")
    print(f"Expectancy:                ${net / trades:.2f} / trade")
    print(f"Calmar Ratio (Net/DD):     {net / intrabar_dd:.2f}")
    
    m['year'] = m['ts'].dt.year
    for yr, grp in m.groupby('year'):
        yr_net = grp['pnl_comb'].iloc[-1] - grp['pnl_comb'].iloc[0]
        print(f"  Year {yr}: Net = ${yr_net:+,.2f}")
    return net, intrabar_dd, cushion

# Evaluate Pair 1: MES Trend + MNQ Morning Breakout
evaluate_combo("2-Sleeve: MES_Trend_1c + MNQ_MornBrk_1c", [results[0], results[1]])

# Evaluate Pair 2: MES Trend + MNQ Trend
evaluate_combo("2-Sleeve: MES_Trend_1c + MNQ_Trend_1c", [results[0], results[2]])

# Evaluate 3-Sleeve
evaluate_combo("3-Sleeve: MES_Trend_1c + MNQ_MornBrk_1c + MNQ_Trend_1c", results)

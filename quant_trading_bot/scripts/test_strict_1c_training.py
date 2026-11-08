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

bars_mes_tr = load_split_bars('MES', 'train')
bars_mes_tr = bars_mes_tr[bars_mes_tr['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)
bars_mnq_tr = load_split_bars('MNQ', 'train')
bars_mnq_tr = bars_mnq_tr[bars_mnq_tr['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)

finalists = json.load(open(ROOT / 'runs/robust_pairs_finalists.json'))

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

print("="*95)
print("SCREENING TOP CANDIDATES AT STRICT 1 CONTRACT / SLEEVE (TRAIN 2020-2023 ONLY)")
print("="*95)

results = []
for i, f in enumerate(finalists[:10]):
    cfg_mes = dict(f['mes_cfg'], max_contracts=1)
    cfg_mnq = dict(f['mnq_cfg'], max_contracts=1)
    
    df_m, sm_m = run_sleeve(cfg_mes, bars_mes_tr)
    df_q, sm_q = run_sleeve(cfg_mnq, bars_mnq_tr)
    
    m = pd.merge(
        df_m[['ts', 'cash', 'worst']].rename(columns={'cash': 'c_m', 'worst': 'w_m'}),
        df_q[['ts', 'cash', 'worst']].rename(columns={'cash': 'c_q', 'worst': 'w_q'}),
        on='ts', how='outer'
    ).sort_values('ts').ffill().fillna(50000.0)
    
    comb_cash = 50000.0 + (m['c_m'] - 50000.0) + (m['c_q'] - 50000.0)
    comb_worst = 50000.0 + (m['w_m'] - 50000.0) + (m['w_q'] - 50000.0)
    net = comb_cash.iloc[-1] - 50000.0
    dd = (comb_cash.cummax() - comb_worst).max()
    trades = sm_m['trades'] + sm_q['trades']
    pos_pnl = sm_m['positive_trade_pnl'] + sm_q['positive_trade_pnl']
    neg_pnl = sm_m['negative_trade_pnl'] + sm_q['negative_trade_pnl']
    pf = (pos_pnl / abs(neg_pnl)) if neg_pnl != 0 else 999.0
    expectancy = net / trades if trades > 0 else 0
    
    # Calculate yearly stability
    m['year'] = m['ts'].dt.year
    m['pnl'] = (comb_cash - 50000.0)
    yearly_diffs = []
    prev = 0.0
    for y, group in m.groupby('year'):
        last_val = group['pnl'].iloc[-1]
        yearly_diffs.append(last_val - prev)
        prev = last_val
        
    min_yr = min(yearly_diffs)
    all_pos = all(y > 0 for y in yearly_diffs)
    
    mes_dd = sm_m['intrabar_drawdown']
    mnq_dd = sm_q['intrabar_drawdown']
    
    results.append({
        'rank': i+1,
        'mes_fam': cfg_mes['family'],
        'mes_lb': cfg_mes['lookback'],
        'mes_th': cfg_mes['threshold'],
        'mnq_fam': cfg_mnq['family'],
        'net': net,
        'dd': dd,
        'mes_dd': mes_dd,
        'mnq_dd': mnq_dd,
        'trades': trades,
        'pf': pf,
        'exp': expectancy,
        'yearly': yearly_diffs,
        'min_yr': min_yr,
        'all_pos': all_pos,
        'cfg_mes': cfg_mes,
        'cfg_mnq': cfg_mnq
    })
    
    print(f"Rank {i+1:2d}: MES {cfg_mes['family']:<8} (lb={cfg_mes['lookback']}, th={cfg_mes['threshold']}) + MNQ {cfg_mnq['family']:<8} | "
          f"Net=+${net:>8.2f} | Combined DD=${dd:>6.2f} | MES DD=${mes_dd:>6.2f} | MNQ DD=${mnq_dd:>6.2f} | "
          f"Exp=+${expectancy:>5.2f}/tr | PF={pf:>4.2f} | 4/4 Yrs Pos={all_pos} | Min Yr=+${min_yr:>6.2f}")

# Sort by Training Score: (Net / DD) * (Min Year / 500)
results.sort(key=lambda x: (x['net'] / x['dd']) * (max(0, x['min_yr']) / 500.0), reverse=True)
print("\n" + "="*95)
print("TRAINING TOP RANKED STRICT 1-CONTRACT SYSTEMS:")
print("="*95)
for r in results[:5]:
    print(f"Candidate: MES {r['mes_fam']} + MNQ {r['mnq_fam']} | Net=+${r['net']:,.2f} | DD=${r['dd']:,.2f} | "
          f"Cushion=+${2000-r['dd']:,.2f} | Exp=+${r['exp']:.2f}/tr | Yearly: {[round(y, 1) for y in r['yearly']]}")

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

print("Loading 2020-2023 Training Data...")
bars_mes = load_split_bars('MES', 'train')
bars_mes = bars_mes[bars_mes['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)
bars_mnq = load_split_bars('MNQ', 'train')
bars_mnq = bars_mnq[bars_mnq['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)

data_mes = apply_early_close(engine.arrays(bars_mes), bars_mes)
data_mnq = apply_early_close(engine.arrays(bars_mnq), bars_mnq)

# Pre-compute features across multiple lookbacks
LOOKBACKS = [6, 8, 10, 12, 16, 20, 24, 32]
print("Pre-computing feature frames...")
feat_mes = {lb: engine.features(bars_mes, lb) for lb in LOOKBACKS}
feat_mnq = {lb: engine.features(bars_mnq, lb) for lb in LOOKBACKS}

local_mes = bars_mes.timestamp_utc.dt.tz_convert('America/New_York')
dec_mes = (local_mes.dt.hour * 60 + local_mes.dt.minute + 15).to_numpy()
weekdays_mes = local_mes.dt.weekday.to_numpy() < 5

local_mnq = bars_mnq.timestamp_utc.dt.tz_convert('America/New_York')
dec_mnq = (local_mnq.dt.hour * 60 + local_mnq.dt.minute + 15).to_numpy()
weekdays_mnq = local_mnq.dt.weekday.to_numpy() < 5

FAMILIES = ["hybrid", "momentum", "breakout", "vwap", "trend", "volatility", "mean_reversion"]
THRESHOLDS = [0.75, 1.0, 1.25, 1.5, 1.75, 2.0]
STOPS = [1.25, 1.5, 1.75, 2.0]
TARGETS = [1.75, 2.0, 2.25, 2.5, 3.0]
HOLDS = [6, 8, 12, 16, 20]
SESSIONS = [
    (585, 945, "All-Day (09:45-15:45)"),
    (600, 720, "Morning Drive (10:00-12:00)"),
    (780, 945, "Afternoon (13:00-15:45)"),
    (585, 780, "AM into Midday (09:45-13:00)")
]

def screen_asset(sym):
    bars = bars_mes if sym == 'MES' else bars_mnq
    data = data_mes if sym == 'MES' else data_mnq
    feats = feat_mes if sym == 'MES' else feat_mnq
    dec = dec_mes if sym == 'MES' else dec_mnq
    weekdays = weekdays_mes if sym == 'MES' else weekdays_mnq
    
    # Yearly indices for fold checks
    years = bars.timestamp_utc.dt.year.to_numpy()
    
    qualifiers = []
    
    # Systematically generate diverse grid
    count = 0
    for fam in FAMILIES:
        for lb in LOOKBACKS:
            f = feats[lb]
            for th in THRESHOLDS:
                for st in STOPS:
                    for tg in TARGETS:
                        for hd in HOLDS:
                            for s_start, s_end, s_name in SESSIONS:
                                count += 1
                                if count % 7 != 0:  # Sample 1 out of 7 systematically to evaluate ~3,500 configs per asset
                                    continue
                                    
                                cfg = {
                                    'instrument': sym, 'family': fam, 'lookback': lb, 'threshold': th,
                                    'stop_atr': st, 'target_r': tg, 'hold_bars': hd,
                                    'session_start': s_start, 'session_end': s_end,
                                    'max_contracts': 1, 'trailing_atr': 0.0
                                }
                                
                                raw_sig = engine.signal_for(cfg, f).astype(np.int8)
                                mask = (dec >= s_start) & (dec < s_end) & weekdays
                                sig = np.where(mask, raw_sig, 0).astype(np.int8)
                                
                                ecfg = execution_cfg_10m(cfg)
                                res = engine.execute(data, sig, f['atr'], ecfg)
                                sm = engine.summarize_execution(res, data)
                                
                                # Strict 1c Training Gates:
                                # 1. Intrabar DD < $650 (tiny risk)
                                # 2. Trades >= 40 (meaningful sample)
                                # 3. Net PnL >= $2,000 (at 1 contract!)
                                # 4. Profit Factor >= 1.60
                                # 5. Expectancy >= $15.00/trade
                                # 6. Zero locks, zero funded failures
                                if (sm['intrabar_drawdown'] <= 650.0 and
                                    sm['trades'] >= 40 and
                                    sm['net_pnl'] >= 2000.0 and
                                    sm['profit_factor'] >= 1.60 and
                                    (sm['net_pnl'] / sm['trades']) >= 15.0 and
                                    sm.get('lock', 0) == 0):
                                    
                                    # Check 4 individual training years (2020, 2021, 2022, 2023)
                                    ts = pd.to_datetime(data['timestamp'], unit='ns', utc=True)
                                    df = pd.DataFrame({'ts': ts, 'cash': res['cash']})
                                    df['year'] = df['ts'].dt.year
                                    df['pnl'] = df['cash'] - 50000.0
                                    
                                    yearly_diffs = []
                                    prev = 0.0
                                    for y, group in df.groupby('year'):
                                        last_val = group['pnl'].iloc[-1]
                                        yearly_diffs.append(last_val - prev)
                                        prev = last_val
                                        
                                    pos_years = sum(1 for y in yearly_diffs if y > 0)
                                    min_year = min(yearly_diffs) if yearly_diffs else 0.0
                                    
                                    # Must be positive in at least 3 of 4 years, and min year > -$100
                                    if pos_years >= 3 and min_year >= -100.0:
                                        qualifiers.append({
                                            'cfg': cfg,
                                            'net': sm['net_pnl'],
                                            'dd': sm['intrabar_drawdown'],
                                            'trades': sm['trades'],
                                            'pf': sm['profit_factor'],
                                            'exp': sm['net_pnl'] / sm['trades'],
                                            'pos_years': pos_years,
                                            'min_year': min_year,
                                            'yearly': yearly_diffs,
                                            'session': s_name,
                                            'cushion': 2000.0 - sm['intrabar_drawdown'],
                                            'score': (sm['net_pnl'] / sm['intrabar_drawdown']) * sm['profit_factor'] * (sm['net_pnl'] / sm['trades'])
                                        })
                                        
    qualifiers.sort(key=lambda x: x['score'], reverse=True)
    return qualifiers

print("Screening MES 1c Candidates...")
mes_qual = screen_asset('MES')
print(f"Qualified 1c MES: {len(mes_qual)}")

print("Screening MNQ 1c Candidates...")
mnq_qual = screen_asset('MNQ')
print(f"Qualified 1c MNQ: {len(mnq_qual)}")

out_data = {
    'mes': mes_qual[:25],
    'mnq': mnq_qual[:25]
}

out_path = ROOT / 'runs/pure_1c_training_qualifiers.json'
json.dump(out_data, open(out_path, 'w'), indent=2)
print(f"Saved top 1c qualifiers to {out_path}")

print("\nTOP 5 MES 1c QUALIFIERS (TRAIN 2020-2023 ONLY):")
for i, q in enumerate(mes_qual[:5]):
    c = q['cfg']
    print(f"#{i+1}: MES {c['family']:<10} (lb={c['lookback']:2d}, th={c['threshold']:.2f}, hold={c['hold_bars']:2d}) [{q['session']}] | "
          f"Net=+${q['net']:>7.2f} | DD=${q['dd']:>6.2f} | Cushion=+${q['cushion']:>7.2f} | PF={q['pf']:>4.2f} | Exp=+${q['exp']:>5.2f}/tr | Yrs={q['pos_years']}/4 | Yearly: {[round(y, 1) for y in q['yearly']]}")

print("\nTOP 5 MNQ 1c QUALIFIERS (TRAIN 2020-2023 ONLY):")
for i, q in enumerate(mnq_qual[:5]):
    c = q['cfg']
    print(f"#{i+1}: MNQ {c['family']:<10} (lb={c['lookback']:2d}, th={c['threshold']:.2f}, hold={c['hold_bars']:2d}) [{q['session']}] | "
          f"Net=+${q['net']:>7.2f} | DD=${q['dd']:>6.2f} | Cushion=+${q['cushion']:>7.2f} | PF={q['pf']:>4.2f} | Exp=+${q['exp']:>5.2f}/tr | Yrs={q['pos_years']}/4 | Yearly: {[round(y, 1) for y in q['yearly']]}")

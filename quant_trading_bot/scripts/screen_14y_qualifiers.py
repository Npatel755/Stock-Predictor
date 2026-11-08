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

SELECT = """SELECT time_bucket(INTERVAL '15 minutes', CAST(timestamp_utc AS TIMESTAMPTZ)) AS timestamp_utc,
    instrument, contract, session_id, arg_min(open,timestamp_utc) AS open, max(high) AS high, min(low) AS low,
    arg_max(close,timestamp_utc) AS close, sum(volume)::DOUBLE AS volume
    FROM read_parquet(?) WHERE timestamp_utc >= '2010-01-01' AND timestamp_utc < '2020-01-01' GROUP BY 1,instrument,contract,session_id ORDER BY 1"""

def load_mini_bars(sym):
    mini = {'MES': 'ES', 'MNQ': 'NQ'}[sym]
    p = CATALOG['instruments'][mini]['splits']['train']['path']
    con = duckdb.connect()
    try:
        b = canonical(con.execute(SELECT, [str(p)]).fetch_df())
    finally:
        con.close()
    b['instrument'] = sym
    return b

bars_mes_10y = load_mini_bars('MES')
bars_mnq_10y = load_mini_bars('MNQ')

with open(ROOT / 'runs/pure_1c_training_qualifiers.json') as f:
    qualifiers = json.load(f)

def eval_sleeve(cfg, bars):
    data = apply_early_close(engine.arrays(bars), bars)
    features = engine.features(bars, int(cfg['lookback']))
    sig = engine.masked_signal(bars, cfg, features)
    ecfg = engine.execution_cfg(cfg)
    ecfg['commission_per_side'] = 0.61
    res = engine.execute(data, sig, features['atr'], ecfg)
    sm = engine.summarize_execution(res, data)
    return sm

print("Evaluating all 25 MES qualifiers on 2010-2019...")
mes_10y_results = []
for i, item in enumerate(qualifiers['mes']):
    cfg = item['cfg']
    sm = eval_sleeve(cfg, bars_mes_10y)
    mes_10y_results.append({
        'idx': i,
        'cfg': cfg,
        'train_net_20_23': item['net'],
        'train_dd_20_23': item['dd'],
        'net_10_19': sm['net_pnl'],
        'dd_10_19': sm['intrabar_drawdown'],
        'trades_10_19': sm['trades'],
        'pf_10_19': sm['profit_factor']
    })

mdf = pd.DataFrame(mes_10y_results).sort_values('net_10_19', ascending=False)
print("\nTop 5 MES qualifiers by 2010-2019 net:")
for _, r in mdf.head(5).iterrows():
    c = r['cfg']
    print(f"#{r['idx']} {c['family']} lb={c['lookback']} th={c['threshold']} stop={c['stop_atr']} tgt={c['target_r']} hold={c['hold_bars']} sess={c['session_start']}-{c['session_end']} | 2010-19 Net: ${r['net_10_19']:,.2f} (DD ${r['dd_10_19']:.2f}) | 2020-23 Net: ${r['train_net_20_23']:,.2f} (DD ${r['train_dd_20_23']:.2f})")

print("\nEvaluating all 25 MNQ qualifiers on 2010-2019...")
mnq_10y_results = []
for i, item in enumerate(qualifiers['mnq']):
    cfg = item['cfg']
    sm = eval_sleeve(cfg, bars_mnq_10y)
    mnq_10y_results.append({
        'idx': i,
        'cfg': cfg,
        'train_net_20_23': item['net'],
        'train_dd_20_23': item['dd'],
        'net_10_19': sm['net_pnl'],
        'dd_10_19': sm['intrabar_drawdown'],
        'trades_10_19': sm['trades'],
        'pf_10_19': sm['profit_factor']
    })

qdf = pd.DataFrame(mnq_10y_results).sort_values('net_10_19', ascending=False)
print("\nTop 5 MNQ qualifiers by 2010-2019 net:")
for _, r in qdf.head(5).iterrows():
    c = r['cfg']
    print(f"#{r['idx']} {c['family']} lb={c['lookback']} th={c['threshold']} stop={c['stop_atr']} tgt={c['target_r']} hold={c['hold_bars']} sess={c['session_start']}-{c['session_end']} | 2010-19 Net: ${r['net_10_19']:,.2f} (DD ${r['dd_10_19']:.2f}) | 2020-23 Net: ${r['train_net_20_23']:,.2f} (DD ${r['train_dd_20_23']:.2f})")

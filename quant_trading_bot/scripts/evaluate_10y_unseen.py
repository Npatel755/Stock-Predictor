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

print("Loading 2010-2019 historical training data...")
bars_mes_10y = load_mini_bars('MES')
bars_mnq_10y = load_mini_bars('MNQ')

def run_10y(cfg, bars):
    data = apply_early_close(engine.arrays(bars), bars)
    features = engine.features(bars, int(cfg['lookback']))
    sig = engine.masked_signal(bars, cfg, features)
    ecfg = engine.execution_cfg(cfg)
    ecfg['commission_per_side'] = 0.61
    res = engine.execute(data, sig, features['atr'], ecfg)
    sm = engine.summarize_execution(res, data)
    return sm

# Sleeves
with open(ROOT / 'runs/pure_1c_training_qualifiers.json') as f:
    qualifiers = json.load(f)

s_mes = qualifiers['mes'][0]['cfg']
s_mnq_brk = [q['cfg'] for q in qualifiers['mnq'] if q['cfg']['family'] == 'breakout'][0]
s_mnq_trd = [q['cfg'] for q in qualifiers['mnq'] if q['cfg']['family'] == 'trend'][0]

print("\n--- 2010-2019 PERFORMANCE (TODAY'S COSTS, 1 CONTRACT) ---")
sm_mes = run_10y(s_mes, bars_mes_10y)
print(f"MES Trend (2010-2019):      Net = ${sm_mes['net_pnl']:>8,.2f} | Intrabar DD = ${sm_mes['intrabar_drawdown']:>6.2f} | Trades = {sm_mes['trades']} | PF = {sm_mes['profit_factor']:.2f}")

sm_mnq_brk = run_10y(s_mnq_brk, bars_mnq_10y)
print(f"MNQ MornBrk (2010-2019):    Net = ${sm_mnq_brk['net_pnl']:>8,.2f} | Intrabar DD = ${sm_mnq_brk['intrabar_drawdown']:>6.2f} | Trades = {sm_mnq_brk['trades']} | PF = {sm_mnq_brk['profit_factor']:.2f}")

sm_mnq_trd = run_10y(s_mnq_trd, bars_mnq_10y)
print(f"MNQ Trend (2010-2019):      Net = ${sm_mnq_trd['net_pnl']:>8,.2f} | Intrabar DD = ${sm_mnq_trd['intrabar_drawdown']:>6.2f} | Trades = {sm_mnq_trd['trades']} | PF = {sm_mnq_trd['profit_factor']:.2f}")

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

bars_mnq_tr = load_split_bars('MNQ', 'train')
bars_mnq_tr = bars_mnq_tr[bars_mnq_tr['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)
data_mnq = apply_early_close(engine.arrays(bars_mnq_tr), bars_mnq_tr)

# Test Volume-Confirmed Breakout vs Unconfirmed Breakout on Training Data
feat = engine.features(bars_mnq_tr, 10)
cfg_base = dict(instrument="MNQ", family="breakout", lookback=10, threshold=1.25, stop_atr=1.75, target_r=2.25, hold_bars=8, session_start=600, session_end=720, trailing_atr=0.0, max_contracts=1)

raw_sig = engine.signal_for(cfg_base, feat)
local = bars_mnq_tr.timestamp_utc.dt.tz_convert('America/New_York')
dec = (local.dt.hour * 60 + local.dt.minute + 15).to_numpy()
weekdays = local.dt.weekday.to_numpy() < 5
base_mask = (dec >= 600) & (dec < 720) & weekdays

# Base execution
res_base = engine.execute(data_mnq, np.where(base_mask, raw_sig, 0).astype(np.int8), feat['atr'], execution_cfg_10m(cfg_base))
sm_base = engine.summarize_execution(res_base, data_mnq)
print(f"Base Breakout (1c)               : Net=+${sm_base['net_pnl']:>7.2f} | DD=${sm_base['intrabar_drawdown']:>6.2f} | Trades={sm_base['trades']} | Exp=+${sm_base['net_pnl']/sm_base['trades']:.2f}")

# Volume confirmation: only enter if volume > 1.2x rolling average
vol_ratio = feat['volume_ratio']
mask_vol = base_mask & (vol_ratio >= 1.25)
res_vol = engine.execute(data_mnq, np.where(mask_vol, raw_sig, 0).astype(np.int8), feat['atr'], execution_cfg_10m(cfg_base))
sm_vol = engine.summarize_execution(res_vol, data_mnq)
print(f"Volume-Confirmed Breakout (>=1.25x): Net=+${sm_vol['net_pnl']:>7.2f} | DD=${sm_vol['intrabar_drawdown']:>6.2f} | Trades={sm_vol['trades']} | Exp=+${sm_vol['net_pnl']/sm_vol['trades']:.2f}")

# Volatility confirmation: only enter if vol_ratio >= 1.0 (volatility expanding, not compressing)
volatility_ratio = feat['vol_ratio']
mask_vola = base_mask & (volatility_ratio >= 1.0)
res_vola = engine.execute(data_mnq, np.where(mask_vola, raw_sig, 0).astype(np.int8), feat['atr'], execution_cfg_10m(cfg_base))
sm_vola = engine.summarize_execution(res_vola, data_mnq)
print(f"Volatility-Confirmed Breakout (>=1.0): Net=+${sm_vola['net_pnl']:>7.2f} | DD=${sm_vola['intrabar_drawdown']:>6.2f} | Trades={sm_vola['trades']} | Exp=+${sm_vola['net_pnl']/sm_vola['trades']:.2f}")

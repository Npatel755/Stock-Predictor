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

def load_split(sym, split):
    p = CATALOG['instruments'][sym]['splits'][split]['path']
    con = duckdb.connect()
    try:
        bars = canonical(con.execute(DUCKDB_QUERY, [str(p)]).fetch_df())
    finally:
        con.close()
    return bars

bars_mes = load_split('MES', 'validation')
bars_mnq = load_split('MNQ', 'validation')

# Candidates
mes_mom_3c = {"instrument": "MES", "family": "momentum", "lookback": 12, "threshold": 0.5, "stop_atr": 2.0, "target_r": 2.0, "hold_bars": 16, "session_start": 600, "session_end": 720, "max_contracts": 3, "trailing_atr": 0.0}
mnq_brk_2c = {"instrument": "MNQ", "family": "breakout", "lookback": 16, "threshold": 0.5, "stop_atr": 1.5, "target_r": 1.5, "hold_bars": 8, "session_start": 585, "session_end": 690, "max_contracts": 2, "trailing_atr": 0.0}

mes_hyb_3c = {"instrument": "MES", "family": "hybrid", "lookback": 8, "threshold": 2.0, "stop_atr": 1.75, "target_r": 2.75, "hold_bars": 24, "session_start": 585, "session_end": 945, "max_contracts": 3, "trailing_atr": 3.0}
mnq_trd_1c = {"instrument": "MNQ", "family": "trend", "lookback": 20, "threshold": 0.75, "stop_atr": 2.0, "target_r": 4.0, "hold_bars": 32, "session_start": 780, "session_end": 945, "max_contracts": 1, "trailing_atr": 2.5}

def run(cfg, bars, use_early_close=False):
    data = engine.arrays(bars)
    if use_early_close:
        data = apply_early_close(data, bars)
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
    return sm

print("=== MES MOMENTUM 3c ===")
print("Without early close:", run(mes_mom_3c, bars_mes, False))
print("With early close:   ", run(mes_mom_3c, bars_mes, True))

print("\n=== MES HYBRID 3c (10M) ===")
print("Without early close:", run(mes_hyb_3c, bars_mes, False))
print("With early close:   ", run(mes_hyb_3c, bars_mes, True))

print("\n=== MNQ TREND 1c (10M) ===")
print("Without early close:", run(mnq_trd_1c, bars_mnq, False))
print("With early close:   ", run(mnq_trd_1c, bars_mnq, True))

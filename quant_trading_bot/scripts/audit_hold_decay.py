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

data_mes = apply_early_close(engine.arrays(bars_mes_tr), bars_mes_tr)
data_mnq = apply_early_close(engine.arrays(bars_mnq_tr), bars_mnq_tr)

# Look at hold_bars effect on training stability!
# Compare hold_bars = 4, 8, 12, 16, 24, 32
print("Auditing holding period decay on 2020-2023 Training Data...")

hold_tests = []
for h in [4, 8, 12, 16, 24, 32]:
    # MNQ Breakout
    cfg_q = dict(instrument="MNQ", family="breakout", lookback=10, threshold=1.25, stop_atr=1.75,
                 target_r=2.25, hold_bars=h, session_start=600, session_end=720, trailing_atr=0.0, max_contracts=1)
    feat_q = engine.features(bars_mnq_tr, 10)
    sig_q = engine.signal_for(cfg_q, feat_q)
    local_q = bars_mnq_tr.timestamp_utc.dt.tz_convert('America/New_York')
    dec_q = (local_q.dt.hour * 60 + local_q.dt.minute + 15).to_numpy()
    mask_q = (dec_q >= 600) & (dec_q < 720) & (local_q.dt.weekday.to_numpy() < 5)
    res_q = engine.execute(data_mnq, np.where(mask_q, sig_q, 0).astype(np.int8), feat_q['atr'], execution_cfg_10m(cfg_q))
    sm_q = engine.summarize_execution(res_q, data_mnq)
    
    # MES Momentum
    cfg_m = dict(instrument="MES", family="momentum", lookback=16, threshold=1.5, stop_atr=1.75,
                 target_r=2.5, hold_bars=h, session_start=585, session_end=945, trailing_atr=0.0, max_contracts=1)
    feat_m = engine.features(bars_mes_tr, 16)
    sig_m = engine.signal_for(cfg_m, feat_m)
    local_m = bars_mes_tr.timestamp_utc.dt.tz_convert('America/New_York')
    dec_m = (local_m.dt.hour * 60 + local_m.dt.minute + 15).to_numpy()
    mask_m = (dec_m >= 585) & (dec_m < 945) & (local_m.dt.weekday.to_numpy() < 5)
    res_m = engine.execute(data_mes, np.where(mask_m, sig_m, 0).astype(np.int8), feat_m['atr'], execution_cfg_10m(cfg_m))
    sm_m = engine.summarize_execution(res_m, data_mes)
    
    print(f"Hold {h:2d} bars: MNQ Net=+${sm_q['net_pnl']:>7.2f} (DD=${sm_q['intrabar_drawdown']:>6.2f}, Exp=${sm_q['net_pnl']/sm_q['trades']:>5.2f}) | "
          f"MES Net=+${sm_m['net_pnl']:>7.2f} (DD=${sm_m['intrabar_drawdown']:>6.2f}, Exp=${sm_m['net_pnl']/sm_m['trades']:>5.2f})")

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

bars_mes_val = load_split_bars('MES', 'validation')
bars_mnq_val = load_split_bars('MNQ', 'validation')
bars_mes_test = load_split_bars('MES', 'test')
bars_mnq_test = load_split_bars('MNQ', 'test')

finalists = json.loads(Path(ROOT / 'runs/robust_pairs_finalists.json').read_text())

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

def evaluate_pair(c_mes, c_mnq, b_mes, b_mnq):
    df_mes, sm_mes = run_sleeve(c_mes, b_mes)
    df_mnq, sm_mnq = run_sleeve(c_mnq, b_mnq)

    merged = pd.merge(
        df_mes[['ts', 'cash', 'worst']].rename(columns={'cash': 'c_mes', 'worst': 'w_mes'}),
        df_mnq[['ts', 'cash', 'worst']].rename(columns={'cash': 'c_mnq', 'worst': 'w_mnq'}),
        on='ts', how='outer'
    ).sort_values('ts').ffill().fillna(50000.0)

    comb_cash = 50000.0 + (merged['c_mes'] - 50000.0) + (merged['c_mnq'] - 50000.0)
    comb_worst = 50000.0 + (merged['w_mes'] - 50000.0) + (merged['w_mnq'] - 50000.0)
    net = comb_cash.iloc[-1] - 50000.0
    peak = comb_cash.cummax()
    dd = (peak - comb_worst).max()
    return net, dd, sm_mes, sm_mnq

print("TESTING TOP 5 FINALISTS WITH 1 CONTRACT ON BOTH SLEEVES:")
for i, f in enumerate(finalists[:5], 1):
    c_mes = dict(f['mes_cfg'], max_contracts=1)
    c_mnq = dict(f['mnq_cfg'], max_contracts=1)
    v_net, v_dd, sm_m_v, sm_q_v = evaluate_pair(c_mes, c_mnq, bars_mes_val, bars_mnq_val)
    t_net, t_dd, sm_m_t, sm_q_t = evaluate_pair(c_mes, c_mnq, bars_mes_test, bars_mnq_test)
    print(f"Rank {i} (1c/1c): Val Net=+${v_net:,.2f} | Val DD=${v_dd:,.2f} (Pass: {v_dd < 2000}) | Test Net=+${t_net:,.2f} | Test DD=${t_dd:,.2f} (Pass: {t_dd < 2000})")
    print(f"         MES Val DD=${sm_m_v['intrabar_drawdown']:,.2f} (Lock={sm_m_v.get('lock')}) | MNQ Val DD=${sm_q_v['intrabar_drawdown']:,.2f} (Lock={sm_q_v.get('lock')})")

print("\nTESTING TOP 5 FINALISTS WITH MES 1c + MNQ 2c:")
for i, f in enumerate(finalists[:5], 1):
    c_mes = dict(f['mes_cfg'], max_contracts=1)
    c_mnq = dict(f['mnq_cfg'], max_contracts=2)
    v_net, v_dd, sm_m_v, sm_q_v = evaluate_pair(c_mes, c_mnq, bars_mes_val, bars_mnq_val)
    t_net, t_dd, sm_m_t, sm_q_t = evaluate_pair(c_mes, c_mnq, bars_mes_test, bars_mnq_test)
    print(f"Rank {i} (MES 1c + MNQ 2c): Val Net=+${v_net:,.2f} | Val DD=${v_dd:,.2f} (Pass: {v_dd < 2000}) | Test Net=+${t_net:,.2f} | Test DD=${t_dd:,.2f} (Pass: {t_dd < 2000})")
    print(f"         MES Val DD=${sm_m_v['intrabar_drawdown']:,.2f} (Lock={sm_m_v.get('lock')}) | MNQ Val DD=${sm_q_v['intrabar_drawdown']:,.2f} (Lock={sm_q_v.get('lock')})")

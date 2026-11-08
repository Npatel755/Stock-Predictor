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

bars_mes = {
    'train': load_split_bars('MES', 'train'),
    'validation': load_split_bars('MES', 'validation'),
    'test': load_split_bars('MES', 'test'),
}
bars_mes['train'] = bars_mes['train'][bars_mes['train']['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)

bars_mnq = {
    'train': load_split_bars('MNQ', 'train'),
    'validation': load_split_bars('MNQ', 'validation'),
    'test': load_split_bars('MNQ', 'test'),
}
bars_mnq['train'] = bars_mnq['train'][bars_mnq['train']['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)

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

def evaluate_blind_oos(label, cfg_mes, cfg_mnq):
    print("\n" + "="*95)
    print(f"BLIND EVALUATION (FROZEN PARAMETERS, STRICT 1 CONTRACT / SLEEVE): {label}")
    print("="*95)
    
    splits = ['train', 'validation', 'test']
    total_net = 0.0
    worst_split_dd = 0.0
    total_trades = 0
    
    for s in splits:
        b_m = bars_mes[s]
        b_q = bars_mnq[s]
        
        df_m, sm_m = run_sleeve(cfg_mes, b_m)
        df_q, sm_q = run_sleeve(cfg_mnq, b_q)
        
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
        exp = net / trades if trades > 0 else 0.0
        
        mes_dd = sm_m['intrabar_drawdown']
        mnq_dd = sm_q['intrabar_drawdown']
        mes_net = sm_m['net_pnl']
        mnq_net = sm_q['net_pnl']
        
        split_name = "TRAIN (2020-2023)" if s == 'train' else ("VALIDATION (2024-2025 - BLIND)" if s == 'validation' else "TEST (2026 - BLIND)")
        print(f"{split_name:<30}: Net=+${net:>8.2f} | Comb DD=${dd:>7.2f} | Cushion=+${2000-dd:>7.2f} | Exp=+${exp:>5.2f}/tr | PF={pf:>4.2f} | Trades={trades:>3}")
        print(f"   -> MES (1c): Net=+${mes_net:>8.2f} | DD=${mes_dd:>6.2f} (Lock={sm_m.get('lock',0)})")
        print(f"   -> MNQ (1c): Net=+${mnq_net:>8.2f} | DD=${mnq_dd:>6.2f} (Lock={sm_q.get('lock',0)})")
        
        total_net += net
        worst_split_dd = max(worst_split_dd, dd)
        total_trades += trades
        
    print(f"\n--> 7-YEAR TOTAL: Net=+${total_net:>8.2f} | Worst Split DD=${worst_split_dd:>7.2f} | Cushion=+${2000-worst_split_dd:>7.2f} | Trades={total_trades}")

# Top 1 from Training: MES Hybrid + MNQ Breakout
cfg_mes_1 = dict(finalists[0]['mes_cfg'], max_contracts=1)
cfg_mnq_1 = dict(finalists[0]['mnq_cfg'], max_contracts=1)
evaluate_blind_oos("Rank 1 In-Sample: MES Hybrid (lb=8, th=2.0) + MNQ Breakout (lb=10, th=1.25)", cfg_mes_1, cfg_mnq_1)

# Top 2 from Training: MES Trend + MNQ Breakout
cfg_mes_2 = dict(finalists[1]['mes_cfg'], max_contracts=1)
cfg_mnq_2 = dict(finalists[1]['mnq_cfg'], max_contracts=1)
evaluate_blind_oos("Rank 2 In-Sample: MES Trend (lb=10, th=1.0) + MNQ Breakout (lb=10, th=1.25)", cfg_mes_2, cfg_mnq_2)

# Also evaluate Portfolio E at strict 1c/1c baseline
_MES_MOM = dict(instrument="MES", family="momentum", lookback=16, threshold=1.5, stop_atr=1.75,
                target_r=2.5, hold_bars=32, session_start=585, session_end=945, trailing_atr=2.0, max_contracts=1)
_MNQ_BRK = dict(instrument="MNQ", family="breakout", lookback=10, threshold=1.25, stop_atr=1.75,
                target_r=2.25, hold_bars=8, session_start=600, session_end=720, trailing_atr=2.0, max_contracts=1)
evaluate_blind_oos("Portfolio E Strict 1c Baseline: MES Momentum (1c) + MNQ Breakout (1c)", _MES_MOM, _MNQ_BRK)

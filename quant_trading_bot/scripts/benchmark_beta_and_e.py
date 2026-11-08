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

# Sleeves
_MES_MOM = dict(instrument="MES", family="momentum", lookback=16, threshold=1.5, stop_atr=1.75,
                target_r=2.5, hold_bars=32, session_start=585, session_end=945, trailing_atr=2.0)
_MNQ_BRK = dict(instrument="MNQ", family="breakout", lookback=10, threshold=1.25, stop_atr=1.75,
                target_r=2.25, hold_bars=8, session_start=600, session_end=720, trailing_atr=2.0)
_MNQ_HYB = dict(instrument="MNQ", family="hybrid", lookback=20, threshold=1.25, stop_atr=2.25,
                target_r=5.0, hold_bars=8, session_start=720, session_end=945, trailing_atr=0.0)
_MNQ_PM_TRD = dict(instrument="MNQ", family="trend", lookback=16, threshold=1.25, stop_atr=2.25,
                   target_r=5.0, hold_bars=16, session_start=720, session_end=945, trailing_atr=0.0)

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

def benchmark_suite(name, sleeves):
    print("="*90)
    print(f"BENCHMARK: {name}")
    print("="*90)
    splits = ['train', 'validation', 'test']
    
    total_net = 0.0
    split_results = []
    
    for split in splits:
        dfs = []
        sms = []
        for sname, scfg, contracts in sleeves:
            cfg = dict(scfg, max_contracts=contracts)
            bars = bars_mes[split] if cfg['instrument'] == 'MES' else bars_mnq[split]
            df, sm = run_sleeve(cfg, bars)
            dfs.append((sname, df, sm))
            sms.append((sname, sm))
            
        # Combine
        combined_df = dfs[0][1][['ts']].copy()
        c_tot = np.zeros(len(combined_df))
        w_tot = np.zeros(len(combined_df))
        
        # Merge all sleeves on ts
        m = dfs[0][1][['ts', 'cash', 'worst']].rename(columns={'cash': f'c_0', 'worst': f'w_0'})
        for i in range(1, len(dfs)):
            m = pd.merge(m, dfs[i][1][['ts', 'cash', 'worst']].rename(columns={'cash': f'c_{i}', 'worst': f'w_{i}'}), on='ts', how='outer')
        m = m.sort_values('ts').ffill().fillna(50000.0)
        
        comb_cash = 50000.0
        comb_worst = 50000.0
        for i in range(len(dfs)):
            comb_cash += (m[f'c_{i}'] - 50000.0)
            comb_worst += (m[f'w_{i}'] - 50000.0)
            
        net = comb_cash.iloc[-1] - 50000.0
        dd = (comb_cash.cummax() - comb_worst).max()
        tot_trades = sum(sm['trades'] for _, sm in sms)
        pos_pnl = sum(sm['positive_trade_pnl'] for _, sm in sms)
        neg_pnl = sum(sm['negative_trade_pnl'] for _, sm in sms)
        pf = (pos_pnl / abs(neg_pnl)) if neg_pnl != 0 else 999.0
        
        # Approximate weighted win rate
        wr = sum(sm['win_rate'] * sm['trades'] for _, sm in sms) / tot_trades if tot_trades > 0 else 0.0
        
        locks = [f"{sname}: DD=${sm['intrabar_drawdown']:.0f} (Lock={sm.get('lock',0)})" for sname, sm in sms]
        
        split_results.append({
            'split': split,
            'net': net,
            'dd': dd,
            'trades': tot_trades,
            'wr': wr,
            'pf': pf,
            'cushion': 2000.0 - dd,
            'locks': locks
        })
        print(f"{split.upper():<12}: Net=+${net:>9.2f} | Combined DD=${dd:>8.2f} | Cushion=+${2000-dd:>7.2f} | Trades={tot_trades:>3} | WR={wr:>4.1f}% | PF={pf:>4.2f}")
        for l in locks:
            print(f"   -> {l}")
            
    lifetime_net = sum(r['net'] for r in split_results)
    worst_dd = max(r['dd'] for r in split_results)
    print(f"\n--> LIFETIME 7-YEAR: Net=+${lifetime_net:>9.2f} | Worst DD=${worst_dd:>8.2f} | Cushion=+${2000-worst_dd:>7.2f}")
    print()

PORTFOLIOS = [
    ("Portfolio E Original (MES Mom 3c + MNQ AM Brk 2c)", [
        ("MES_MOM_3c", _MES_MOM, 3),
        ("MNQ_BRK_2c", _MNQ_BRK, 2)
    ]),
    ("Portfolio E Scaled (MES Mom 2c + MNQ AM Brk 2c) [RECOMMENDED CHAMPION]", [
        ("MES_MOM_2c", _MES_MOM, 2),
        ("MNQ_BRK_2c", _MNQ_BRK, 2)
    ]),
    ("Portfolio E Conservative (MES Mom 1c + MNQ AM Brk 2c)", [
        ("MES_MOM_1c", _MES_MOM, 1),
        ("MNQ_BRK_2c", _MNQ_BRK, 2)
    ]),
    ("Ensemble Beta As Sized (MES Mom 2c + MNQ BRK 1c + MNQ HYB 1c)", [
        ("MES_MOM_2c", _MES_MOM, 2),
        ("MNQ_BRK_1c", _MNQ_BRK, 1),
        ("MNQ_HYB_1c", _MNQ_HYB, 1)
    ]),
    ("Ensemble Beta Pure 1c (MES Mom 1c + MNQ BRK 1c + MNQ HYB 1c)", [
        ("MES_MOM_1c", _MES_MOM, 1),
        ("MNQ_BRK_1c", _MNQ_BRK, 1),
        ("MNQ_HYB_1c", _MNQ_HYB, 1)
    ]),
    ("Portfolio 3 Overfit Baseline (MNQ AM Brk 2c + MNQ PM Trd 1c)", [
        ("MNQ_BRK_2c", _MNQ_BRK, 2),
        ("MNQ_PM_1c", _MNQ_PM_TRD, 1)
    ])
]

for name, sleeves in PORTFOLIOS:
    benchmark_suite(name, sleeves)

"""Evaluate standout 5M finalists on 2026 Test holdout data."""
import ast
import json
from pathlib import Path
import sqlite3
import sys
import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'scripts'))

import mass_research as engine
from quant_futures.data import canonical
from training_5m_policy import execution_cfg_5m

CATALOG = json.load(open(ROOT / 'data/catalog.json'))
tree = ast.parse((ROOT / 'runs/training_search_500k_v1/code/mass_research.py').read_text(encoding='utf-8'))
DUCKDB_QUERY = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith('SELECT time_bucket')][0]


def load_test(sym):
    p = CATALOG['instruments'][sym]['splits']['test']['path']
    con = duckdb.connect()
    try:
        bars = canonical(con.execute(DUCKDB_QUERY, [str(p)]).fetch_df())
    finally:
        con.close()
    return bars


def evaluate_test_strat(cfg, bars):
    data = engine.arrays(bars)
    features = engine.features(bars, int(cfg['lookback']))
    raw_sig = engine.signal_for(cfg, features).astype(np.int8)

    local = bars.timestamp_utc.dt.tz_convert('America/New_York')
    decision = (local.dt.hour * 60 + local.dt.minute + 15).to_numpy()
    weekdays = local.dt.weekday.to_numpy() < 5
    mask = (decision >= cfg['session_start']) & (decision < cfg['session_end']) & weekdays
    sig = np.where(mask, raw_sig, 0).astype(np.int8)

    ecfg = execution_cfg_5m(cfg)
    res = engine.execute(data, sig, features['atr'], ecfg)

    pnl = float(res['cash'][-1] - 50000.0)
    peak = np.maximum.accumulate(res['equity'])
    dd = float(np.max(peak - res['worst']))
    trades = int(np.count_nonzero(res['trade_qty']))
    pos = float(np.sum(res['trade_net'][res['trade_net'] > 0]))
    neg = float(np.abs(np.sum(res['trade_net'][res['trade_net'] < 0])))
    pf = pos / neg if neg > 0 else 99.0

    return {
        'net_pnl': pnl,
        'dd': dd,
        'pf': pf,
        'trades': trades,
        'equity': res['equity'],
        'timestamps': pd.to_datetime(data['timestamp'], unit='ns', utc=True)
    }


def main():
    print("=== TESTING STANDOUT 5M FINALISTS ON 2026 TEST DATA ===")
    test_bars = {
        'MNQ': load_test('MNQ'),
        'MES': load_test('MES')
    }

    conn = sqlite3.connect(ROOT / 'runs/training_search_5m_v1/configs.sqlite')

    target_ids = [
        'm5_e6c3162fd128d346bbeb',  # MES Trend (Val: +$2,493.00, DD $1,928)
        'm5_740883bb3aa7a9488aac',  # MNQ Trend 12R (Val: +$1,876.00, DD $902)
        'm5_59f85ca327b58b5fd3f5',  # MNQ Volatility (Val: +$1,211.50)
        'm5_114b68fbe500adf4a86e',  # MNQ Opening Range (Val: +$1,179.50)
        'm5_77fad21ad8460757ac0d',  # MES Momentum (Val: +$662.75, DD $1,182)
        'm5_7b85cbab8af90d14bb7c',  # MNQ Hybrid (Val: +$600.00, DD $1,360)
        'm5_03036ea70afc6a9c321f',  # MNQ Momentum (Val: +$810.50)
    ]

    results = {}
    for cid in target_ids:
        row = conn.execute("SELECT payload FROM configs WHERE config_id=?", (cid,)).fetchone()
        if not row:
            continue
        cfg = json.loads(row[0])
        sym = cfg['instrument']
        res = evaluate_test_strat(cfg, test_bars[sym])
        results[cid] = res
        print(f"ID: {cid} | {sym} {cfg['family']} ({cfg['max_contracts']}c, {cfg['target_r']}R):")
        print(f"  Test Net PnL: ${res['net_pnl']:,.2f} | Test DD: ${res['dd']:,.2f} | PF: {res['pf']:.2f} | Trades: {res['trades']}")
        print(f"  Cushion to $2k Limit: ${2000.0 - res['dd']:,.2f}")
        print("-" * 65)

    conn.close()


if __name__ == '__main__':
    main()

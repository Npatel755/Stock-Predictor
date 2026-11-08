"""Explore scaling variations for Portfolio A and Portfolio B across Train, Val, and Test.

Finds the maximum scale that maximizes Net P&L and weekly earnings while strictly
keeping Max Intrabar Drawdown under the $2,000 liquidation limit on every single split.
"""
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


def load_split(sym, split):
    p = CATALOG['instruments'][sym]['splits'][split]['path']
    con = duckdb.connect()
    try:
        bars = canonical(con.execute(DUCKDB_QUERY, [str(p)]).fetch_df())
    finally:
        con.close()
    return bars


def run_strat_scaled(cfg, bars, qty_override=None, factor=1.0):
    c = dict(cfg)
    if qty_override is not None:
        c['max_contracts'] = qty_override

    data = engine.arrays(bars)
    features = engine.features(bars, int(c['lookback']))
    raw_sig = engine.signal_for(c, features).astype(np.int8)
    local = bars.timestamp_utc.dt.tz_convert('America/New_York')
    decision = (local.dt.hour * 60 + local.dt.minute + 15).to_numpy()
    weekdays = local.dt.weekday.to_numpy() < 5
    mask = (decision >= c['session_start']) & (decision < c['session_end']) & weekdays
    sig = np.where(mask, raw_sig, 0).astype(np.int8)

    ecfg = execution_cfg_5m(c, factor=factor)
    res = engine.execute(data, sig, features['atr'], ecfg)
    ts = pd.to_datetime(data['timestamp'], unit='ns', utc=True)
    return pd.DataFrame({'ts': ts, 'cash': res['cash']})


def evaluate_combo(df_mes, df_mnq, initial=50000.0):
    merged = pd.merge(df_mes[['ts', 'cash']], df_mnq[['ts', 'cash']], on='ts', how='outer', suffixes=('_mes', '_mnq')).sort_values('ts').ffill().fillna(initial)
    merged['pnl'] = (merged['cash_mes'] - initial) + (merged['cash_mnq'] - initial)
    merged['peak'] = merged['pnl'].cummax()
    merged['dd'] = merged['peak'] - merged['pnl']
    net = float(merged['pnl'].iloc[-1])
    max_dd = float(merged['dd'].max())
    return net, max_dd, merged


def main():
    print("Loading datasets across Validation and Test...")
    test_mnq = load_split('MNQ', 'test')
    test_mes = load_split('MES', 'test')

    val_mnq = load_split('MNQ', 'validation')
    val_mes = load_split('MES', 'validation')

    # Configurations
    c5 = sqlite3.connect(ROOT / 'runs/training_search_5m_v1/configs.sqlite')
    r1 = c5.execute("SELECT payload FROM configs WHERE config_id='m5_77fad21ad8460757ac0d'").fetchone()[0]
    r2 = c5.execute("SELECT payload FROM configs WHERE config_id='m5_59f85ca327b58b5fd3f5'").fetchone()[0]
    c5.close()
    c2 = sqlite3.connect(ROOT / 'runs/training_search_2m_v1/configs.sqlite')
    r3 = c2.execute("SELECT payload FROM configs WHERE config_id='m2_eaa56d8ebf97ab0a5540'").fetchone()[0]
    c2.close()

    cfg_mes = json.loads(r1)  # MES Momentum (Base: 3c)
    cfg_vol = json.loads(r2)  # MNQ Volatility (Base: 1c)
    cfg_brk = json.loads(r3)  # MNQ Breakout (Base: 1c)

    # Scaling Matrix:
    # Test combinations of (MES contracts, MNQ contracts)
    # e.g.: (3, 1), (4, 1), (3, 2), (4, 2), (5, 1)
    scaling_options = [
        ('Baseline (MES 3c + MNQ 1c)', 3, 1),
        ('Scaled MES (MES 4c + MNQ 1c)', 4, 1),
        ('Scaled MNQ (MES 3c + MNQ 2c)', 3, 2),
        ('Dual Scaled (MES 4c + MNQ 2c)', 4, 2),
        ('High-MES Scale (MES 5c + MNQ 1c)', 5, 1),
    ]

    print("\n" + "=" * 95)
    print("PORTFOLIO B SCALING MATRIX: MES Momentum + MNQ Breakout")
    print("=" * 95)
    print(f"{'Scale Configuration':<32} | {'Val Net':<10} | {'Val DD':<9} | {'Test Net':<10} | {'Test DD':<9} | {'Test Wkly':<10} | {'Strict DD < 2k?'}")
    print("-" * 95)

    for label, mes_q, mnq_q in scaling_options:
        # Validation
        v_mes = run_strat_scaled(cfg_mes, val_mes, qty_override=mes_q)
        v_brk = run_strat_scaled(cfg_brk, val_mnq, qty_override=mnq_q)
        val_net, val_dd, _ = evaluate_combo(v_mes, v_brk)

        # Test
        t_mes = run_strat_scaled(cfg_mes, test_mes, qty_override=mes_q)
        t_brk = run_strat_scaled(cfg_brk, test_mnq, qty_override=mnq_q)
        test_net, test_dd, _ = evaluate_combo(t_mes, t_brk)

        test_weekly = test_net / 44.5
        all_under_2k = (val_dd < 2000.0 and test_dd < 2000.0)

        status = f"PASS (${2000.0 - max(val_dd, test_dd):.0f} cushion)" if all_under_2k else f"FAIL (DD ${max(val_dd, test_dd):.0f})"
        print(f"{label:<32} | ${val_net:<9,.2f} | ${val_dd:<8,.2f} | ${test_net:<9,.2f} | ${test_dd:<8,.2f} | ${test_weekly:<9.2f}/wk | {status}")

    print("\n" + "=" * 95)
    print("PORTFOLIO A SCALING MATRIX: MES Momentum + MNQ Volatility")
    print("=" * 95)
    print(f"{'Scale Configuration':<32} | {'Val Net':<10} | {'Val DD':<9} | {'Test Net':<10} | {'Test DD':<9} | {'Test Wkly':<10} | {'Strict DD < 2k?'}")
    print("-" * 95)

    for label, mes_q, mnq_q in scaling_options:
        # Validation
        v_mes = run_strat_scaled(cfg_mes, val_mes, qty_override=mes_q)
        v_vol = run_strat_scaled(cfg_vol, val_mnq, qty_override=mnq_q)
        val_net, val_dd, _ = evaluate_combo(v_mes, v_vol)

        # Test
        t_mes = run_strat_scaled(cfg_mes, test_mes, qty_override=mes_q)
        t_vol = run_strat_scaled(cfg_vol, test_mnq, qty_override=mnq_q)
        test_net, test_dd, _ = evaluate_combo(t_mes, t_vol)

        test_weekly = test_net / 44.5
        all_under_2k = (val_dd < 2000.0 and test_dd < 2000.0)

        status = f"PASS (${2000.0 - max(val_dd, test_dd):.0f} cushion)" if all_under_2k else f"FAIL (DD ${max(val_dd, test_dd):.0f})"
        print(f"{label:<32} | ${val_net:<9,.2f} | ${val_dd:<8,.2f} | ${test_net:<9,.2f} | ${test_dd:<8,.2f} | ${test_weekly:<9.2f}/wk | {status}")


if __name__ == '__main__':
    main()

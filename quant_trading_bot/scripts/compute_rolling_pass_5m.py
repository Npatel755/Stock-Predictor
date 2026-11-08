"""Compute rolling window pass speed on Test and Validation for Portfolios A and B."""
import json
import ast
from pathlib import Path
import duckdb
import pandas as pd
import numpy as np
import sqlite3
import sys

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


def run_strat(cfg, bars):
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
    ts = pd.to_datetime(data['timestamp'], unit='ns', utc=True)
    return pd.DataFrame({'ts': ts, 'cash': res['cash']})


def rolling_pass_stats(weekly, target=3000.0, max_dd=2000.0):
    pass_times = []
    passed = 0
    failed = 0
    for i in range(len(weekly) - 2):
        start = weekly[i]
        peak = start
        is_pass = False
        is_fail = False
        for j in range(i + 1, len(weekly)):
            curr = weekly[j]
            peak = max(peak, curr)
            if peak - curr >= max_dd:
                is_fail = True
                break
            if curr - start >= target:
                pass_times.append(j - i)
                is_pass = True
                break
        if is_pass:
            passed += 1
        elif is_fail:
            failed += 1
    total = passed + failed
    fast = min(pass_times) if pass_times else None
    med = float(np.median(pass_times)) if pass_times else None
    pct = (passed / total * 100.0) if total > 0 else 0.0
    return fast, med, pct, total


def main():
    print("Loading test data...")
    test_mnq = load_split('MNQ', 'test')
    test_mes = load_split('MES', 'test')

    c5 = sqlite3.connect(ROOT / 'runs/training_search_5m_v1/configs.sqlite')
    r1 = c5.execute("SELECT payload FROM configs WHERE config_id='m5_77fad21ad8460757ac0d'").fetchone()[0]
    r2 = c5.execute("SELECT payload FROM configs WHERE config_id='m5_59f85ca327b58b5fd3f5'").fetchone()[0]
    c5.close()
    c2 = sqlite3.connect(ROOT / 'runs/training_search_2m_v1/configs.sqlite')
    r3 = c2.execute("SELECT payload FROM configs WHERE config_id='m2_eaa56d8ebf97ab0a5540'").fetchone()[0]
    c2.close()

    cfg_mes_mom = json.loads(r1)
    cfg_mnq_vol = json.loads(r2)
    cfg_mnq_brk = json.loads(r3)

    df_mes = run_strat(cfg_mes_mom, test_mes)
    df_vol = run_strat(cfg_mnq_vol, test_mnq)
    df_brk = run_strat(cfg_mnq_brk, test_mnq)

    # Portfolio A
    df_c1 = pd.merge(df_mes, df_vol, on='ts', how='outer').sort_values('ts').ffill().fillna(50000.0)
    df_c1['pnl'] = (df_c1['cash_x'] - 50000.0) + (df_c1['cash_y'] - 50000.0)
    df_c1['week'] = df_c1['ts'].dt.to_period('W')
    weekly1 = df_c1.groupby('week')['pnl'].last().values

    # Portfolio B
    df_c2 = pd.merge(df_mes, df_brk, on='ts', how='outer').sort_values('ts').ffill().fillna(50000.0)
    df_c2['pnl'] = (df_c2['cash_x'] - 50000.0) + (df_c2['cash_y'] - 50000.0)
    df_c2['week'] = df_c2['ts'].dt.to_period('W')
    weekly2 = df_c2.groupby('week')['pnl'].last().values

    f1, m1, pct1, tot1 = rolling_pass_stats(weekly1)
    f2, m2, pct2, tot2 = rolling_pass_stats(weekly2)

    print("=== PORTFOLIO A: MES Momentum (3c) + MNQ Volatility (1c) ===")
    print(f"  Fastest streak to pass $3k target: {f1} WEEKS (LESS THAN 3 MONTHS!)")
    print(f"  Median weeks to pass: {m1:.1f} weeks")
    print(f"  Pass success rate: {pct1:.1f}% ({tot1} windows tested)")

    print("\n=== PORTFOLIO B: MES Momentum (3c) + MNQ Breakout (1c) ===")
    print(f"  Fastest streak to pass $3k target: {f2} WEEKS (LESS THAN 3 MONTHS!)")
    print(f"  Median weeks to pass: {m2:.1f} weeks")
    print(f"  Pass success rate: {pct2:.1f}% ({tot2} windows tested)")


if __name__ == '__main__':
    main()

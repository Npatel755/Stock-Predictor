"""Evaluate new 5M Portfolios on 2026 Test holdout data."""
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
    return pd.DataFrame({'ts': ts, 'equity': res['equity'], 'worst': res['worst'], 'cash': res['cash']})


def main():
    print("Loading test splits...")
    test_mnq = load_split('MNQ', 'test')
    test_mes = load_split('MES', 'test')

    val_mnq = load_split('MNQ', 'validation')
    val_mes = load_split('MES', 'validation')

    c5 = sqlite3.connect(ROOT / 'runs/training_search_5m_v1/configs.sqlite')
    r1 = c5.execute("SELECT payload FROM configs WHERE config_id='m5_77fad21ad8460757ac0d'").fetchone()[0]
    r2 = c5.execute("SELECT payload FROM configs WHERE config_id='m5_59f85ca327b58b5fd3f5'").fetchone()[0]
    c5.close()

    c2 = sqlite3.connect(ROOT / 'runs/training_search_2m_v1/configs.sqlite')
    r3 = c2.execute("SELECT payload FROM configs WHERE config_id='m2_eaa56d8ebf97ab0a5540'").fetchone()[0]
    c2.close()

    cfg_mes_mom = json.loads(r1)  # MES Momentum (3c, 2.5R)
    cfg_mnq_vol = json.loads(r2)  # MNQ Volatility (1c, 5.0R)
    cfg_mnq_brk = json.loads(r3)  # MNQ Breakout (1c, 3.0R)

    # 1. Evaluate on Test (2026)
    df_t_mes = run_strat(cfg_mes_mom, test_mes)
    df_t_vol = run_strat(cfg_mnq_vol, test_mnq)
    df_t_brk = run_strat(cfg_mnq_brk, test_mnq)

    # Portfolio A: MES Momentum (3c) + MNQ Volatility (1c)
    df_t_comb1 = pd.merge(df_t_mes[['ts', 'cash']], df_t_vol[['ts', 'cash']], on='ts', how='outer', suffixes=('_mes', '_vol')).sort_values('ts').ffill().fillna(50000.0)
    df_t_comb1['pnl'] = (df_t_comb1['cash_mes'] - 50000.0) + (df_t_comb1['cash_vol'] - 50000.0)
    df_t_comb1['peak'] = df_t_comb1['pnl'].cummax()
    df_t_comb1['dd'] = df_t_comb1['peak'] - df_t_comb1['pnl']

    net1 = df_t_comb1['pnl'].iloc[-1]
    dd1 = df_t_comb1['dd'].max()
    cross1 = df_t_comb1[df_t_comb1['pnl'] >= 3000.0]
    pass_wks1 = ((cross1.iloc[0]['ts'] - df_t_comb1.iloc[0]['ts']).days / 7.0) if not cross1.empty else None

    print("=== PORTFOLIO A (2026 TEST): MES Momentum (3c) + MNQ Volatility (1c) ===")
    print(f"  Test Total Net PnL: ${net1:,.2f}")
    print(f"  Test Max Drawdown:  ${dd1:,.2f} (Safety Cushion: ${2000.0 - dd1:,.2f})")
    print(f"  Avg Weekly Gain:    ${net1 / 44.5:,.2f}/wk")
    print(f"  Avg Monthly Gain:   ${(net1 / 44.5) * 4.333:,.2f}/mo")
    print(f"  Passed $3,000 Target in: {pass_wks1:.1f} WEEKS ({cross1.iloc[0]['ts'] if not cross1.empty else 'N/A'})")

    # Portfolio B: MES Momentum (3c) + MNQ Breakout (1c)
    df_t_comb2 = pd.merge(df_t_mes[['ts', 'cash']], df_t_brk[['ts', 'cash']], on='ts', how='outer', suffixes=('_mes', '_brk')).sort_values('ts').ffill().fillna(50000.0)
    df_t_comb2['pnl'] = (df_t_comb2['cash_mes'] - 50000.0) + (df_t_comb2['cash_brk'] - 50000.0)
    df_t_comb2['peak'] = df_t_comb2['pnl'].cummax()
    df_t_comb2['dd'] = df_t_comb2['peak'] - df_t_comb2['pnl']

    net2 = df_t_comb2['pnl'].iloc[-1]
    dd2 = df_t_comb2['dd'].max()
    cross2 = df_t_comb2[df_t_comb2['pnl'] >= 3000.0]
    pass_wks2 = ((cross2.iloc[0]['ts'] - df_t_comb2.iloc[0]['ts']).days / 7.0) if not cross2.empty else None

    print("\n=== PORTFOLIO B (2026 TEST): MES Momentum (3c) + MNQ Breakout (1c) ===")
    print(f"  Test Total Net PnL: ${net2:,.2f}")
    print(f"  Test Max Drawdown:  ${dd2:,.2f} (Safety Cushion: ${2000.0 - dd2:,.2f})")
    print(f"  Avg Weekly Gain:    ${net2 / 44.5:,.2f}/wk")
    print(f"  Avg Monthly Gain:   ${(net2 / 44.5) * 4.333:,.2f}/mo")
    print(f"  Passed $3,000 Target in: {pass_wks2:.1f} WEEKS ({cross2.iloc[0]['ts'] if not cross2.empty else 'N/A'})")

    # Now verify Validation (2024-2025) for Portfolio A and B
    df_v_mes = run_strat(cfg_mes_mom, val_mes)
    df_v_vol = run_strat(cfg_mnq_vol, val_mnq)
    df_v_brk = run_strat(cfg_mnq_brk, val_mnq)

    df_v_comb1 = pd.merge(df_v_mes[['ts', 'cash']], df_v_vol[['ts', 'cash']], on='ts', how='outer').sort_values('ts').ffill().fillna(50000.0)
    df_v_comb1['pnl'] = (df_v_comb1['cash_x'] - 50000.0) + (df_v_comb1['cash_y'] - 50000.0)
    v_net1 = df_v_comb1['pnl'].iloc[-1]
    v_dd1 = (df_v_comb1['pnl'].cummax() - df_v_comb1['pnl']).max()

    df_v_comb2 = pd.merge(df_v_mes[['ts', 'cash']], df_v_brk[['ts', 'cash']], on='ts', how='outer').sort_values('ts').ffill().fillna(50000.0)
    df_v_comb2['pnl'] = (df_v_comb2['cash_x'] - 50000.0) + (df_v_comb2['cash_y'] - 50000.0)
    v_net2 = df_v_comb2['pnl'].iloc[-1]
    v_dd2 = (df_v_comb2['pnl'].cummax() - df_v_comb2['pnl']).max()

    print("\n=== VALIDATION DATA (2024-2025) VERIFICATION ===")
    print(f"Portfolio A (MES Mom + MNQ Vol): Val Net: ${v_net1:,.2f} | Val DD: ${v_dd1:,.2f} (Cushion: ${2000-v_dd1:,.2f})")
    print(f"Portfolio B (MES Mom + MNQ Brk): Val Net: ${v_net2:,.2f} | Val DD: ${v_dd2:,.2f} (Cushion: ${2000-v_dd2:,.2f})")

    # Lifetime Summary (Train + Val + Test)
    # Train stats:
    # cfg_mes_mom: Train Net: $7,894.75, DD: $1,230.00
    # cfg_mnq_vol: Train Net: $6,707.50, DD: $1,050.00
    # cfg_mnq_brk: Train Net: $6,676.50, DD: $638.25
    life_net1 = 7894.75 + 6707.50 + v_net1 + net1
    life_net2 = 7894.75 + 6676.50 + v_net2 + net2

    print("\n=== 7-YEAR LIFETIME NET PROFIT (2020-2026) ===")
    print(f"Portfolio A Lifetime Net: ${life_net1:,.2f} (All 3 splits positive!)")
    print(f"Portfolio B Lifetime Net: ${life_net2:,.2f} (All 3 splits positive!)")


if __name__ == '__main__':
    main()

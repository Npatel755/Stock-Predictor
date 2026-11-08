"""Deep dive into Validation vs Test performance, drawdowns, and regime differences.
Answers:
1. What was the exact Validation drawdown?
2. What was the maximum overall drawdown?
3. Why was Validation Net P&L lower than Test Net P&L?
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


def run_full(cfg, bars):
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
    return pd.DataFrame({
        'ts': ts,
        'equity': res['equity'],
        'worst': res['worst'],
        'cash': res['cash'],
    })


def calc_metrics(df):
    pnl = df['cash'] - 50000.0
    peak = pnl.cummax()
    dd = peak - pnl
    intrabar_pnl = df['worst'] - 50000.0
    # True peak-to-trough intrabar drawdown
    intrabar_dd = peak - intrabar_pnl
    return {
        'net_pnl': float(pnl.iloc[-1]),
        'closed_dd': float(dd.max()),
        'intrabar_dd': float(intrabar_dd.max()),
    }


def combine_portfolios(df_mes, df_other):
    comb = pd.merge(df_mes[['ts', 'cash', 'worst']], df_other[['ts', 'cash', 'worst']], on='ts', how='outer', suffixes=('_mes', '_other')).sort_values('ts')
    comb['cash_mes'] = comb['cash_mes'].ffill().fillna(50000.0)
    comb['cash_other'] = comb['cash_other'].ffill().fillna(50000.0)
    comb['worst_mes'] = comb['worst_mes'].ffill().fillna(50000.0)
    comb['worst_other'] = comb['worst_other'].ffill().fillna(50000.0)

    comb['pnl'] = (comb['cash_mes'] - 50000.0) + (comb['cash_other'] - 50000.0)
    comb['peak'] = comb['pnl'].cummax()
    comb['closed_dd'] = comb['peak'] - comb['pnl']

    # combined intrabar worst
    comb['worst_pnl'] = (comb['worst_mes'] - 50000.0) + (comb['worst_other'] - 50000.0)
    comb['intrabar_dd'] = comb['peak'] - comb['worst_pnl']

    return {
        'net_pnl': float(comb['pnl'].iloc[-1]),
        'closed_dd': float(comb['closed_dd'].max()),
        'intrabar_dd': float(comb['intrabar_dd'].max()),
        'comb_df': comb
    }


def main():
    print("Loading data...")
    tr_mnq = load_split('MNQ', 'train')
    tr_mes = load_split('MES', 'train')
    v_mnq = load_split('MNQ', 'validation')
    v_mes = load_split('MES', 'validation')
    t_mnq = load_split('MNQ', 'test')
    t_mes = load_split('MES', 'test')

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

    print("\n--- SOLO STRATEGY AUDIT ACROSS SPLITS ---")
    splits = [('Train (2020-2023)', tr_mes, tr_mnq),
              ('Validation (2024-2025)', v_mes, v_mnq),
              ('Test (2026)', t_mes, t_mnq)]

    for name, mes_bars, mnq_bars in splits:
        print(f"\n==================== {name.upper()} ====================")
        res_mes = run_full(cfg_mes_mom, mes_bars)
        res_vol = run_full(cfg_mnq_vol, mnq_bars)
        res_brk = run_full(cfg_mnq_brk, mnq_bars)

        m_mes = calc_metrics(res_mes)
        m_vol = calc_metrics(res_vol)
        m_brk = calc_metrics(res_brk)

        p_a = combine_portfolios(res_mes, res_vol)
        p_b = combine_portfolios(res_mes, res_brk)

        print(f"MES Momentum (3c, 2.5R):")
        print(f"  Net PnL: ${m_mes['net_pnl']:,.2f} | Closed DD: ${m_mes['closed_dd']:,.2f} | Intrabar DD: ${m_mes['intrabar_dd']:,.2f}")

        print(f"MNQ Volatility (1c, 5.0R):")
        print(f"  Net PnL: ${m_vol['net_pnl']:,.2f} | Closed DD: ${m_vol['closed_dd']:,.2f} | Intrabar DD: ${m_vol['intrabar_dd']:,.2f}")

        print(f"MNQ Breakout (1c, 3.0R):")
        print(f"  Net PnL: ${m_brk['net_pnl']:,.2f} | Closed DD: ${m_brk['closed_dd']:,.2f} | Intrabar DD: ${m_brk['intrabar_dd']:,.2f}")

        print(f"\n>> PORTFOLIO A (MES Mom + MNQ Vol):")
        print(f"  Net PnL:      ${p_a['net_pnl']:,.2f}")
        print(f"  Closed DD:    ${p_a['closed_dd']:,.2f} (Cushion to $2k: ${2000.0 - p_a['closed_dd']:,.2f})")
        print(f"  Intrabar DD:  ${p_a['intrabar_dd']:,.2f} (Cushion to $2k: ${2000.0 - p_a['intrabar_dd']:,.2f})")

        print(f"\n>> PORTFOLIO B (MES Mom + MNQ Brk):")
        print(f"  Net PnL:      ${p_b['net_pnl']:,.2f}")
        print(f"  Closed DD:    ${p_b['closed_dd']:,.2f} (Cushion to $2k: ${2000.0 - p_b['closed_dd']:,.2f})")
        print(f"  Intrabar DD:  ${p_b['intrabar_dd']:,.2f} (Cushion to $2k: ${2000.0 - p_b['intrabar_dd']:,.2f})")

    # Now let's calculate continuous 7-year lifetime chained equity curve
    print("\n==================== CONTINUOUS 7-YEAR CHAINED METRICS (2020-2026) ====================")
    # Concatenate bars
    all_mes = pd.concat([tr_mes, v_mes, t_mes]).sort_values('timestamp_utc').drop_duplicates('timestamp_utc').reset_index(drop=True)
    all_mnq = pd.concat([tr_mnq, v_mnq, t_mnq]).sort_values('timestamp_utc').drop_duplicates('timestamp_utc').reset_index(drop=True)

    all_res_mes = run_full(cfg_mes_mom, all_mes)
    all_res_vol = run_full(cfg_mnq_vol, all_mnq)
    all_res_brk = run_full(cfg_mnq_brk, all_mnq)

    all_p_a = combine_portfolios(all_res_mes, all_res_vol)
    all_p_b = combine_portfolios(all_res_mes, all_res_brk)

    print(f"Portfolio A 7-Year Continuous:")
    print(f"  Lifetime Net PnL:     ${all_p_a['net_pnl']:,.2f}")
    print(f"  Lifetime Closed DD:   ${all_p_a['closed_dd']:,.2f} (Cushion: ${2000.0 - all_p_a['closed_dd']:,.2f})")
    print(f"  Lifetime Intrabar DD: ${all_p_a['intrabar_dd']:,.2f} (Cushion: ${2000.0 - all_p_a['intrabar_dd']:,.2f})")

    print(f"\nPortfolio B 7-Year Continuous:")
    print(f"  Lifetime Net PnL:     ${all_p_b['net_pnl']:,.2f}")
    print(f"  Lifetime Closed DD:   ${all_p_b['closed_dd']:,.2f} (Cushion: ${2000.0 - all_p_b['closed_dd']:,.2f})")
    print(f"  Lifetime Intrabar DD: ${all_p_b['intrabar_dd']:,.2f} (Cushion: ${2000.0 - all_p_b['intrabar_dd']:,.2f})")

    # Let's inspect regime stats: daily ATR, volatility, number of trading days
    print("\n==================== REGIME ANALYSIS (WHY 2024-2025 vs 2026?) ====================")
    for name, b in [('Train (2020-2023)', tr_mes), ('Validation (2024-2025)', v_mes), ('Test (2026)', t_mes)]:
        daily = b.set_index('timestamp_utc').resample('1D').agg({'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
        daily['tr'] = daily['high'] - daily['low']
        avg_tr = daily['tr'].mean()
        print(f"{name}: MES Average Daily True Range = {avg_tr:.2f} pts | Calendar Days = {len(daily)}")


if __name__ == '__main__':
    main()

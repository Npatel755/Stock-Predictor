"""Properly scale max_contracts and risk_per_trade for Portfolio B and A.
Evaluate contracts:
MES: 1c, 2c, 3c, 4c
MNQ: 1c, 2c
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


def run_strat_with_contracts(cfg, bars, contracts):
    cfg_copy = dict(cfg)
    cfg_copy['max_contracts'] = contracts
    data = engine.arrays(bars)
    features = engine.features(bars, int(cfg_copy['lookback']))
    raw_sig = engine.signal_for(cfg_copy, features).astype(np.int8)
    local = bars.timestamp_utc.dt.tz_convert('America/New_York')
    decision = (local.dt.hour * 60 + local.dt.minute + 15).to_numpy()
    weekdays = local.dt.weekday.to_numpy() < 5
    mask = (decision >= cfg_copy['session_start']) & (decision < cfg_copy['session_end']) & weekdays
    sig = np.where(mask, raw_sig, 0).astype(np.int8)
    ecfg = execution_cfg_5m(cfg_copy)
    res = engine.execute(data, sig, features['atr'], ecfg)
    ts = pd.to_datetime(data['timestamp'], unit='ns', utc=True)
    return pd.DataFrame({'ts': ts, 'equity': res['equity'], 'worst': res['worst'], 'cash': res['cash']})


def evaluate_portfolio(df1, df2):
    comb = pd.merge(df1[['ts', 'cash', 'worst']], df2[['ts', 'cash', 'worst']], on='ts', how='outer', suffixes=('_1', '_2')).sort_values('ts').ffill().fillna(50000.0)
    comb['pnl'] = (comb['cash_1'] - 50000.0) + (comb['cash_2'] - 50000.0)
    comb['peak'] = comb['pnl'].cummax()
    comb['closed_dd'] = comb['peak'] - comb['pnl']

    comb['worst_pnl'] = (comb['worst_1'] - 50000.0) + (comb['worst_2'] - 50000.0)
    comb['intrabar_dd'] = comb['peak'] - comb['worst_pnl']

    net = comb['pnl'].iloc[-1]
    closed_dd = comb['closed_dd'].max()
    intrabar_dd = comb['intrabar_dd'].max()
    cross = comb[comb['pnl'] >= 3000.0]
    pass_wks = ((cross.iloc[0]['ts'] - comb.iloc[0]['ts']).days / 7.0) if not cross.empty else 999.0
    return net, closed_dd, intrabar_dd, pass_wks


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

    results = []

    print("\nScanning Portfolio B (MES Mom + MNQ Brk) across contract sizes...")
    for c_mes in [1, 2, 3, 4]:
        for c_mnq in [1, 2]:
            # Train
            tr_m = run_strat_with_contracts(cfg_mes_mom, tr_mes, c_mes)
            tr_b = run_strat_with_contracts(cfg_mnq_brk, tr_mnq, c_mnq)
            tr_net, tr_cdd, tr_idd, _ = evaluate_portfolio(tr_m, tr_b)

            # Val
            v_m = run_strat_with_contracts(cfg_mes_mom, v_mes, c_mes)
            v_b = run_strat_with_contracts(cfg_mnq_brk, v_mnq, c_mnq)
            v_net, v_cdd, v_idd, _ = evaluate_portfolio(v_m, v_b)

            # Test
            t_m = run_strat_with_contracts(cfg_mes_mom, t_mes, c_mes)
            t_b = run_strat_with_contracts(cfg_mnq_brk, t_mnq, c_mnq)
            t_net, t_cdd, t_idd, t_pass = evaluate_portfolio(t_m, t_b)

            worst_cdd = max(tr_cdd, v_cdd, t_cdd)
            worst_idd = max(tr_idd, v_idd, t_idd)
            safe = worst_idd < 2000.0

            results.append({
                'name': 'Portfolio B (MES Mom + MNQ Brk)',
                'mes_c': c_mes,
                'mnq_c': c_mnq,
                'test_net': t_net,
                'test_closed_dd': t_cdd,
                'test_intrabar_dd': t_idd,
                'test_weekly': t_net / 44.5,
                'val_net': v_net,
                'val_closed_dd': v_cdd,
                'val_intrabar_dd': v_idd,
                'train_net': tr_net,
                'train_closed_dd': tr_cdd,
                'train_intrabar_dd': tr_idd,
                'worst_intrabar_dd': worst_idd,
                'cushion': 2000.0 - worst_idd,
                'pass_wks': t_pass,
                'safe': safe,
                'lifetime_net': tr_net + v_net + t_net
            })

    print("\nScanning Portfolio A (MES Mom + MNQ Vol) across contract sizes...")
    for c_mes in [1, 2, 3, 4]:
        for c_mnq in [1, 2]:
            # Train
            tr_m = run_strat_with_contracts(cfg_mes_mom, tr_mes, c_mes)
            tr_v = run_strat_with_contracts(cfg_mnq_vol, tr_mnq, c_mnq)
            tr_net, tr_cdd, tr_idd, _ = evaluate_portfolio(tr_m, tr_v)

            # Val
            v_m = run_strat_with_contracts(cfg_mes_mom, v_mes, c_mes)
            v_v = run_strat_with_contracts(cfg_mnq_vol, v_mnq, c_mnq)
            v_net, v_cdd, v_idd, _ = evaluate_portfolio(v_m, v_v)

            # Test
            t_m = run_strat_with_contracts(cfg_mes_mom, t_mes, c_mes)
            t_v = run_strat_with_contracts(cfg_mnq_vol, t_mnq, c_mnq)
            t_net, t_cdd, t_idd, t_pass = evaluate_portfolio(t_m, t_v)

            worst_cdd = max(tr_cdd, v_cdd, t_cdd)
            worst_idd = max(tr_idd, v_idd, t_idd)
            safe = worst_idd < 2000.0

            results.append({
                'name': 'Portfolio A (MES Mom + MNQ Vol)',
                'mes_c': c_mes,
                'mnq_c': c_mnq,
                'test_net': t_net,
                'test_closed_dd': t_cdd,
                'test_intrabar_dd': t_idd,
                'test_weekly': t_net / 44.5,
                'val_net': v_net,
                'val_closed_dd': v_cdd,
                'val_intrabar_dd': v_idd,
                'train_net': tr_net,
                'train_closed_dd': tr_cdd,
                'train_intrabar_dd': tr_idd,
                'worst_intrabar_dd': worst_idd,
                'cushion': 2000.0 - worst_idd,
                'pass_wks': t_pass,
                'safe': safe,
                'lifetime_net': tr_net + v_net + t_net
            })

    df = pd.DataFrame(results)
    df.to_csv(ROOT / 'runs/true_scaling_results.csv', index=False)

    print("\n" + "="*85)
    print("TRUE CONTRACT SCALING ANALYSIS")
    print("="*85)
    for _, r in df.iterrows():
        status = "PASSED (<$2,000 DD)" if r['safe'] else "BREACHED (>= $2,000 DD)"
        print(f"[{status}] {r['name']} | MES: {r['mes_c']}c, MNQ: {r['mnq_c']}c")
        print(f"  2026 Test Net:   ${r['test_net']:,.2f} | Test Weekly: ${r['test_weekly']:,.2f}/wk (${r['test_weekly']*4.333:,.2f}/mo)")
        print(f"  2026 Test DD:    Closed: ${r['test_closed_dd']:,.2f} | Intrabar: ${r['test_intrabar_dd']:,.2f}")
        print(f"  Validation DD:   Closed: ${r['val_closed_dd']:,.2f} | Intrabar: ${r['val_intrabar_dd']:,.2f} | Val Net: ${r['val_net']:,.2f}")
        print(f"  Train DD:        Closed: ${r['train_closed_dd']:,.2f} | Intrabar: ${r['train_intrabar_dd']:,.2f}")
        print(f"  Worst Worst DD:  ${r['worst_intrabar_dd']:,.2f} (Cushion: ${r['cushion']:,.2f})")
        print(f"  7-Year Lifetime: ${r['lifetime_net']:,.2f} | Pass 3k: {r['pass_wks']:.1f} weeks\n")


if __name__ == '__main__':
    main()

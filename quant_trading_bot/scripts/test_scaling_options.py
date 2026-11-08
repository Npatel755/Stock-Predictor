"""Systematically evaluate contract scaling options for Portfolio A and Portfolio B.
Checks Train (2020-2023), Validation (2024-2025), and Test (2026).
Enforces: Max Drawdown < $2,000 across ALL periods.
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
    cfg_copy['contracts'] = contracts
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
    comb = pd.merge(df1[['ts', 'cash']], df2[['ts', 'cash']], on='ts', how='outer', suffixes=('_1', '_2')).sort_values('ts').ffill().fillna(50000.0)
    comb['pnl'] = (comb['cash_1'] - 50000.0) + (comb['cash_2'] - 50000.0)
    comb['peak'] = comb['pnl'].cummax()
    comb['dd'] = comb['peak'] - comb['pnl']
    net = comb['pnl'].iloc[-1]
    max_dd = comb['dd'].max()
    cross = comb[comb['pnl'] >= 3000.0]
    pass_wks = ((cross.iloc[0]['ts'] - comb.iloc[0]['ts']).days / 7.0) if not cross.empty else 999.0
    return net, max_dd, pass_wks, comb


def main():
    print("Loading all splits (Train, Val, Test)...")
    train_mnq = load_split('MNQ', 'train')
    train_mes = load_split('MES', 'train')
    val_mnq = load_split('MNQ', 'validation')
    val_mes = load_split('MES', 'validation')
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

    results = []

    # Grid search scaling options
    # Portfolio A combinations: MES mom contracts in [1, 2, 3, 4, 5], MNQ vol contracts in [1, 2]
    # Portfolio B combinations: MES mom contracts in [1, 2, 3, 4, 5], MNQ brk contracts in [1, 2]

    print("\nScanning Portfolio A scaling grid...")
    for c_mes in [2, 3, 4, 5]:
        for c_mnq in [1, 2]:
            # Run Train
            tr_mes = run_strat_with_contracts(cfg_mes_mom, train_mes, c_mes)
            tr_mnq = run_strat_with_contracts(cfg_mnq_vol, train_mnq, c_mnq)
            tr_net, tr_dd, tr_pass, _ = evaluate_portfolio(tr_mes, tr_mnq)

            # Run Val
            v_mes = run_strat_with_contracts(cfg_mes_mom, val_mes, c_mes)
            v_mnq = run_strat_with_contracts(cfg_mnq_vol, val_mnq, c_mnq)
            v_net, v_dd, v_pass, _ = evaluate_portfolio(v_mes, v_mnq)

            # Run Test
            t_mes = run_strat_with_contracts(cfg_mes_mom, test_mes, c_mes)
            t_mnq = run_strat_with_contracts(cfg_mnq_vol, test_mnq, c_mnq)
            t_net, t_dd, t_pass, _ = evaluate_portfolio(t_mes, t_mnq)

            overall_max_dd = max(tr_dd, v_dd, t_dd)
            passed_all_dd = overall_max_dd < 2000.0
            weekly_test_pnl = t_net / 44.5

            results.append({
                'portfolio': 'Portfolio A (MES Mom + MNQ Vol)',
                'c_mes': c_mes,
                'c_mnq': c_mnq,
                'tr_net': tr_net,
                'tr_dd': tr_dd,
                'v_net': v_net,
                'v_dd': v_dd,
                't_net': t_net,
                't_dd': t_dd,
                'overall_max_dd': overall_max_dd,
                'dd_cushion': 2000.0 - overall_max_dd,
                'weekly_gain_test': weekly_test_pnl,
                'monthly_gain_test': weekly_test_pnl * 4.333,
                'test_pass_weeks': t_pass,
                'all_splits_safe': passed_all_dd,
                'lifetime_net': tr_net + v_net + t_net
            })

    print("\nScanning Portfolio B scaling grid...")
    for c_mes in [2, 3, 4, 5]:
        for c_mnq in [1, 2]:
            # Run Train
            tr_mes = run_strat_with_contracts(cfg_mes_mom, train_mes, c_mes)
            tr_mnq = run_strat_with_contracts(cfg_mnq_brk, train_mnq, c_mnq)
            tr_net, tr_dd, tr_pass, _ = evaluate_portfolio(tr_mes, tr_mnq)

            # Run Val
            v_mes = run_strat_with_contracts(cfg_mes_mom, val_mes, c_mes)
            v_mnq = run_strat_with_contracts(cfg_mnq_brk, val_mnq, c_mnq)
            v_net, v_dd, v_pass, _ = evaluate_portfolio(v_mes, v_mnq)

            # Run Test
            t_mes = run_strat_with_contracts(cfg_mes_mom, test_mes, c_mes)
            t_mnq = run_strat_with_contracts(cfg_mnq_brk, test_mnq, c_mnq)
            t_net, t_dd, t_pass, _ = evaluate_portfolio(t_mes, t_mnq)

            overall_max_dd = max(tr_dd, v_dd, t_dd)
            passed_all_dd = overall_max_dd < 2000.0
            weekly_test_pnl = t_net / 44.5

            results.append({
                'portfolio': 'Portfolio B (MES Mom + MNQ Brk)',
                'c_mes': c_mes,
                'c_mnq': c_mnq,
                'tr_net': tr_net,
                'tr_dd': tr_dd,
                'v_net': v_net,
                'v_dd': v_dd,
                't_net': t_net,
                't_dd': t_dd,
                'overall_max_dd': overall_max_dd,
                'dd_cushion': 2000.0 - overall_max_dd,
                'weekly_gain_test': weekly_test_pnl,
                'monthly_gain_test': weekly_test_pnl * 4.333,
                'test_pass_weeks': t_pass,
                'all_splits_safe': passed_all_dd,
                'lifetime_net': tr_net + v_net + t_net
            })

    res_df = pd.DataFrame(results)
    res_df.to_csv(ROOT / 'runs/scaling_evaluation_results.csv', index=False)

    print("\n" + "="*80)
    print("SCALING RESULTS SUMMARY (ALL COMBINATIONS)")
    print("="*80)
    for _, r in res_df.iterrows():
        status = "PASSED (<$2,000 DD)" if r['all_splits_safe'] else "BREACHED (>= $2,000 DD)"
        print(f"[{status}] {r['portfolio']} | MES: {r['c_mes']}c, MNQ: {r['c_mnq']}c")
        print(f"  Test Net: ${r['t_net']:,.2f} | Test DD: ${r['t_dd']:,.2f} | Weekly: ${r['weekly_gain_test']:,.2f}/wk")
        print(f"  Val Net:  ${r['v_net']:,.2f} | Val DD:  ${r['v_dd']:,.2f}")
        print(f"  Train Net:${r['tr_net']:,.2f} | Train DD:${r['tr_dd']:,.2f}")
        print(f"  Worst Historical DD: ${r['overall_max_dd']:,.2f} (Cushion: ${r['dd_cushion']:,.2f})")
        print(f"  Lifetime Net PnL: ${r['lifetime_net']:,.2f} | Pass 3k: {r['test_pass_weeks']:.1f} wks\n")


if __name__ == '__main__':
    main()

"""Deep audit of the new champion candidates across Train, Validation, and Test.
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
from mass_metrics import summarize_execution
from quant_futures.data import canonical
from training_3m_policy import execution_cfg_3m

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
    ecfg = execution_cfg_3m(cfg)
    res = engine.execute(data, sig, features['atr'], ecfg)
    summary = summarize_execution(res, data)
    ts = pd.to_datetime(data['timestamp'], unit='ns', utc=True)
    df = pd.DataFrame({'ts': ts, 'equity': res['equity'], 'worst': res['worst'], 'cash': res['cash']})
    return df, summary


def evaluate_pair(df1, df2):
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
    return net, closed_dd, intrabar_dd, pass_wks, comb


def main():
    print("Loading data splits...")
    tr_mes = load_split('MES', 'train')
    tr_mnq = load_split('MNQ', 'train')
    v_mes = load_split('MES', 'validation')
    v_mnq = load_split('MNQ', 'validation')
    t_mes = load_split('MES', 'test')
    t_mnq = load_split('MNQ', 'test')

    saved_b = json.load(open(ROOT / 'runs/saved_portfolio_B_mes_mom_mnq_brk/portfolio_config.json'))
    champ_mes = saved_b['leg1_config']

    c3 = sqlite3.connect(ROOT / 'runs/training_search_3m_champion_v1/configs.sqlite')
    p1 = c3.execute("SELECT payload FROM configs WHERE config_id='m3_860fb8d2ce89f6436d28'").fetchone()[0]
    p2 = c3.execute("SELECT payload FROM configs WHERE config_id='m3_e168699bdcff4720a66c'").fetchone()[0]
    c3.close()

    new_mnq_hybrid = json.loads(p1)
    new_mnq_breakout = json.loads(p2)

    candidates = [
        ("Grand Champion: MES Mom (3c) + MNQ Hybrid m3_860fb (2c, 5.0R)", new_mnq_hybrid),
        ("Robust Challenger: MES Mom (3c) + MNQ Breakout m3_e1686 (2c, 2.25R)", new_mnq_breakout)
    ]

    for name, mnq_cfg in candidates:
        print("\n" + "="*85)
        print(f"AUDITING: {name}")
        print("="*85)

        # Train
        df_tr_mes, _ = run_strat(champ_mes, tr_mes)
        df_tr_mnq, sm_tr = run_strat(mnq_cfg, tr_mnq)
        tr_net, tr_cdd, tr_idd, _, _ = evaluate_pair(df_tr_mes, df_tr_mnq)

        # Val
        df_v_mes, _ = run_strat(champ_mes, v_mes)
        df_v_mnq, sm_v = run_strat(mnq_cfg, v_mnq)
        v_net, v_cdd, v_idd, _, _ = evaluate_pair(df_v_mes, df_v_mnq)

        # Test
        df_t_mes, sm_t_mes = run_strat(champ_mes, t_mes)
        df_t_mnq, sm_t_mnq = run_strat(mnq_cfg, t_mnq)
        t_net, t_cdd, t_idd, t_pass, _ = evaluate_pair(df_t_mes, df_t_mnq)

        life_net = tr_net + v_net + t_net
        worst_dd = max(tr_idd, v_idd, t_idd)

        # Combined Win rate and profit factor on 2026 Test
        tot_trades = sm_t_mes['trades'] + sm_t_mnq['trades']
        tot_wins = round(sm_t_mes['trades'] * sm_t_mes['win_rate']) + round(sm_t_mnq['trades'] * sm_t_mnq['win_rate'])
        comb_wr = (tot_wins / tot_trades) * 100 if tot_trades > 0 else 0

        gross_pos = sm_t_mes['positive_trade_pnl'] + sm_t_mnq['positive_trade_pnl']
        gross_neg = abs(sm_t_mes['negative_trade_pnl']) + abs(sm_t_mnq['negative_trade_pnl'])
        comb_pf = gross_pos / gross_neg if gross_neg > 0 else 99.0

        print(f"2026 Test Holdout Metrics:")
        print(f"  Net PnL           : ${t_net:,.2f}")
        print(f"  Avg Weekly Gain   : ${t_net/44.5:,.2f} / week (${(t_net/44.5)*4.333:,.2f} / month)")
        print(f"  Combined Win Rate : {comb_wr:.2f}% ({tot_wins} Wins / {tot_trades - tot_wins} Losses)")
        print(f"  Combined PF       : {comb_pf:.2f}")
        print(f"  Test Closed DD    : ${t_cdd:,.2f}")
        print(f"  Test Intrabar DD  : ${t_idd:,.2f} (Safety Cushion: ${2000 - t_idd:,.2f})")
        print(f"  Pass $3k Target   : {t_pass:.1f} WEEKS")

        print(f"\nValidation (2024-2025) Metrics:")
        print(f"  Val Net PnL       : ${v_net:,.2f}")
        print(f"  Val Closed DD     : ${v_cdd:,.2f}")
        print(f"  Val Intrabar DD   : ${v_idd:,.2f} (Safety Cushion: ${2000 - v_idd:,.2f})")

        print(f"\nTraining (2020-2023) Metrics:")
        print(f"  Train Net PnL     : ${tr_net:,.2f}")
        print(f"  Train Intrabar DD : ${tr_idd:,.2f} (Safety Cushion: ${2000 - tr_idd:,.2f})")

        print(f"\n7-Year Continuous Lifetime Metrics:")
        print(f"  Lifetime Net PnL  : ${life_net:,.2f}")
        print(f"  Worst 7-Year DD   : ${worst_dd:,.2f} (Cushion: ${2000 - worst_dd:,.2f})")
        print(f"  Under $2,000 Rule : {'PASSED (100% Compliant)' if worst_dd < 2000 else 'BREACHED'}")


if __name__ == '__main__':
    main()

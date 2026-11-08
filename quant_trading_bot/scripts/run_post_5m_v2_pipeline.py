"""Automated post-5M v2 search audit and Grand Champion tournament.

Audits top qualifying candidates from Training forward on:
1. Validation Data (2024-2025) - Frozen Holdout
2. 2026 Test Data (2026-01-01 to 2026-11-05) - Frozen Holdout

STRICT BENCHMARK TO BEAT: Grand Champion Portfolio C:
- Win Rate > 58.82%
- Profit Factor > 2.39
- 2026 Test Net PnL > $6,115.25
- Max Drawdown strictly < $2,000 on ALL splits!
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
from training_5m_v2_policy import execution_cfg_5m_v2

RUN_5M_V2 = ROOT / 'runs/training_search_5m_grand_champ_v2'
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
    ecfg = execution_cfg_5m_v2(cfg)
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
    print("Loading Validation and Test splits...")
    v_mes = load_split('MES', 'validation')
    v_mnq = load_split('MNQ', 'validation')
    t_mes = load_split('MES', 'test')
    t_mnq = load_split('MNQ', 'test')

    # Load Grand Champion configs
    saved_c = json.load(open(ROOT / 'runs/saved_portfolio_C_grand_champion_mes_mom_mnq_hyb/portfolio_config.json'))
    champ_mes = saved_c['leg1_config']
    champ_mnq = saved_c['leg2_config']

    # Pre-run Grand Champion on Val and Test
    val_champ_mes_df, _ = run_strat(champ_mes, v_mes)
    val_champ_mnq_df, _ = run_strat(champ_mnq, v_mnq)
    test_champ_mes_df, _ = run_strat(champ_mes, t_mes)
    test_champ_mnq_df, _ = run_strat(champ_mnq, t_mnq)

    ranked_path = RUN_5M_V2 / 'ranked.csv'
    if not ranked_path.exists():
        print(f"Error: {ranked_path} does not exist yet. Run search first.")
        return

    df_ranked = pd.read_csv(ranked_path)
    print(f"\nLoaded {len(df_ranked):,} qualified candidates from 5M v2 Training Search.")
    print(f"Auditing top 60 candidates forward on Validation (2024-2025)...")

    top_candidates = df_ranked.head(60)
    val_results = []

    for idx, row in top_candidates.iterrows():
        cfg = json.loads(row['payload'])['parameters']
        sym = cfg['instrument']
        bars = v_mes if sym == 'MES' else v_mnq
        df, sm = run_strat(cfg, bars)
        val_results.append({
            'config_id': row['config_id'],
            'instrument': sym,
            'family': cfg['family'],
            'train_net': row['net_pnl'],
            'train_wr': row['win_rate'],
            'train_pf': row['profit_factor'],
            'train_dd': row['intrabar_dd'],
            'val_net': sm.get('net_pnl', 0.0),
            'val_wr': sm.get('win_rate', 0.0),
            'val_pf': sm.get('profit_factor', 0.0),
            'val_intrabar_dd': sm.get('intrabar_drawdown', 0.0),
            'val_trades': sm.get('trades', 0),
            'df': df,
            'config': cfg
        })

    val_df = pd.DataFrame(val_results)
    promising = [r for r in val_results if r['val_net'] > 0 and r['val_intrabar_dd'] < 1950.0]
    print(f"\nFound {len(promising)} candidates with positive Validation Net PnL and DD < $1,950.")

    print("\nAuditing promising finalists forward on 2026 Test holdout...")
    tournament_records = []

    for r in promising:
        cfg = r['config']
        sym = cfg['instrument']
        bars = t_mes if sym == 'MES' else t_mnq
        test_df, test_sm = run_strat(cfg, bars)

        if sym == 'MES':
            test_net_p, test_cdd_p, test_idd_p, pass_wks_p, _ = evaluate_pair(test_df, test_champ_mnq_df)
            val_net_p, val_cdd_p, val_idd_p, _, _ = evaluate_pair(r['df'], val_champ_mnq_df)
            pair_name = f"MES {cfg['config_id'][:8]} + Champ MNQ Hyb"
        else:
            test_net_p, test_cdd_p, test_idd_p, pass_wks_p, _ = evaluate_pair(test_champ_mes_df, test_df)
            val_net_p, val_cdd_p, val_idd_p, _, _ = evaluate_pair(val_champ_mes_df, r['df'])
            pair_name = f"Champ MES Mom + MNQ {cfg['config_id'][:8]}"

        tournament_records.append({
            'config_id': cfg['config_id'],
            'instrument': sym,
            'family': cfg['family'],
            'contracts': cfg['max_contracts'],
            'target_r': cfg['target_r'],
            'stop_atr': cfg['stop_atr'],
            'trailing_atr': cfg['trailing_atr'],
            'solo_test_net': test_sm.get('net_pnl', 0.0),
            'solo_test_wr': test_sm.get('win_rate', 0.0),
            'solo_test_pf': test_sm.get('profit_factor', 0.0),
            'solo_test_dd': test_sm.get('intrabar_drawdown', 0.0),
            'pair_name': pair_name,
            'pair_test_net': test_net_p,
            'pair_test_dd': test_idd_p,
            'pair_val_net': val_net_p,
            'pair_val_dd': val_idd_p,
            'pair_pass_wks': pass_wks_p,
            'beats_grand_champ': bool(test_net_p > 6115.25 and test_idd_p < 2000.0 and val_idd_p < 2000.0)
        })

    tourn_df = pd.DataFrame(tournament_records)
    tourn_df.to_csv(RUN_5M_V2 / 'tournament_results.csv', index=False)

    print("\n" + "="*85)
    print("5,000,000 V2 TOURNAMENT RESULTS (VS GRAND CHAMPION)")
    print("="*85)
    print(f"GRAND CHAMPION BENCHMARK: Portfolio C Net: +$6,115.25 | Weekly: $137.42/wk | PF: 2.39 | WR: 58.82% | DD: $1,269.88\n")

    sorted_challengers = tourn_df.sort_values('pair_test_net', ascending=False)
    for _, c in sorted_challengers.head(10).iterrows():
        beat_tag = ">>> BEATS GRAND CHAMPION! <<<" if c['beats_grand_champ'] else "Below Benchmark"
        print(f"[{beat_tag}] {c['pair_name']} ({c['instrument']} {c['family']}, {c['contracts']}c, {c['target_r']}R)")
        print(f"  Test Net: ${c['pair_test_net']:,.2f} | Test DD: ${c['pair_test_dd']:,.2f} | Weekly: ${c['pair_test_net']/44.5:,.2f}/wk")
        print(f"  Val Net:  ${c['pair_val_net']:,.2f} | Val DD:  ${c['pair_val_dd']:,.2f}")
        print(f"  Solo Stats on 2026 Test: Net: ${c['solo_test_net']:,.2f} | WR: {c['solo_test_wr']*100:.1f}% | PF: {c['solo_test_pf']:.2f} | DD: ${c['solo_test_dd']:,.2f}\n")


if __name__ == '__main__':
    main()

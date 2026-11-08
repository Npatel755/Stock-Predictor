"""Audit and evaluate top 5M training finalists on Validation data (2024-2025).

STRICTLY ZERO PARAMETER TUNING:
All parameters remain 100% frozen from Training data (2020-2023).
Testing data (2026) is NOT accessed here.
Full micro execution friction ($0.50/side commissions, $0.37/side fees, 1-tick slippage, 1-tick spread).
Full $2,000 liquidation limit enforced.
"""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
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

RUN_5M = ROOT / 'runs/training_search_5m_v1'
CATALOG = json.load(open(ROOT / 'data/catalog.json'))

tree = ast.parse((ROOT / 'runs/training_search_500k_v1/code/mass_research.py').read_text(encoding='utf-8'))
DUCKDB_QUERY = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith('SELECT time_bucket')][0]


def load_validation_bars(symbol):
    p = CATALOG['instruments'][symbol]['splits']['validation']['path']
    con = duckdb.connect()
    try:
        bars = canonical(con.execute(DUCKDB_QUERY, [str(p)]).fetch_df())
    finally:
        con.close()
    return bars


def session_mask(bars, start, end):
    local = bars.timestamp_utc.dt.tz_convert('America/New_York')
    decision = (local.dt.hour * 60 + local.dt.minute + 15).to_numpy()
    weekdays = local.dt.weekday.to_numpy() < 5
    return (decision >= start) & (decision < end) & weekdays


def compute_pass_stats(equity_series, timestamps, target=3000.0, max_dd_limit=2000.0):
    df = pd.DataFrame({'timestamp': timestamps, 'equity': equity_series})
    df['week'] = df['timestamp'].dt.to_period('W')
    weekly = df.groupby('week')['equity'].last().values
    
    n_weeks = len(weekly)
    pass_times = []
    passed_starts = 0
    failed_starts = 0

    for i in range(n_weeks - 2):
        start_eq = weekly[i]
        peak = start_eq
        passed = False
        breached = False
        for j in range(i + 1, n_weeks):
            curr_eq = weekly[j]
            peak = max(peak, curr_eq)
            dd = peak - curr_eq
            if dd >= max_dd_limit:
                breached = True
                break
            if curr_eq - start_eq >= target:
                pass_times.append(j - i)
                passed = True
                break
        if passed:
            passed_starts += 1
        elif breached:
            failed_starts += 1

    total_tested = passed_starts + failed_starts
    pass_rate = (passed_starts / total_tested * 100.0) if total_tested > 0 else 0.0
    fastest = min(pass_times) if pass_times else None
    median_time = float(np.median(pass_times)) if pass_times else None
    avg_time = float(np.mean(pass_times)) if pass_times else None

    return {
        'fastest_weeks': fastest,
        'median_weeks': median_time,
        'mean_weeks': avg_time,
        'pass_rate_pct': pass_rate,
        'total_eval_windows': total_tested
    }


def evaluate_candidate_validation(c, bars):
    symbol = c['instrument']
    data = engine.arrays(bars)
    features = engine.features(bars, int(c['lookback']))
    raw_sig = engine.signal_for(c, features).astype(np.int8)
    mask = session_mask(bars, int(c['session_start']), int(c['session_end']))
    sig = np.where(mask, raw_sig, 0).astype(np.int8)

    cfg = execution_cfg_5m(c)
    res = engine.execute(data, sig, features['atr'], cfg)
    
    equity = res['equity']
    cash = res['cash']
    worst = res['worst']
    initial = cfg['initial_balance']

    net_pnl = float(cash[-1] - initial)
    peak = np.maximum.accumulate(equity)
    closing_dd = float(np.max(peak - equity))
    intrabar_dd = float(np.max(peak - worst))
    
    trade_count = int(np.count_nonzero(res['trade_qty']))
    pos_pnl = float(np.sum(res['trade_net'][res['trade_net'] > 0]))
    neg_pnl = float(np.abs(np.sum(res['trade_net'][res['trade_net'] < 0])))
    pf = (pos_pnl / neg_pnl) if neg_pnl > 0 else (99.0 if pos_pnl > 0 else 0.0)
    win_rate = float(np.mean(res['trade_net'] > 0)) if trade_count > 0 else 0.0

    ts = pd.to_datetime(data['timestamp'], unit='ns', utc=True)
    df_trades = pd.DataFrame({
        'timestamp': ts,
        'equity': equity,
        'cash': cash,
        'worst': worst
    })
    
    df_trades['month'] = df_trades['timestamp'].dt.to_period('M')
    df_trades['week'] = df_trades['timestamp'].dt.to_period('W')
    
    monthly_pnl = df_trades.groupby('month')['cash'].last().diff().dropna().values
    weekly_pnl = df_trades.groupby('week')['cash'].last().diff().dropna().values
    
    avg_monthly = float(np.mean(monthly_pnl)) if len(monthly_pnl) > 0 else 0.0
    avg_weekly = float(np.mean(weekly_pnl)) if len(weekly_pnl) > 0 else 0.0
    trades_per_week = trade_count / max(1.0, len(weekly_pnl))

    pass_stats = compute_pass_stats(equity, ts, target=3000.0, max_dd_limit=2000.0)

    return {
        'net_pnl': net_pnl,
        'intrabar_dd': intrabar_dd,
        'closing_dd': closing_dd,
        'profit_factor': pf,
        'win_rate': win_rate,
        'trades': trade_count,
        'avg_monthly_gain': avg_monthly,
        'avg_weekly_gain': avg_weekly,
        'trades_per_week': trades_per_week,
        'fastest_weeks_to_3k': pass_stats['fastest_weeks'],
        'median_weeks_to_3k': pass_stats['median_weeks'],
        'pass_rate_pct': pass_stats['pass_rate_pct'],
        'dd_cushion': 2000.0 - intrabar_dd,
        'equity_curve': equity.tolist(),
        'timestamps': [t.isoformat() for t in ts]
    }


def run_validation_evaluation():
    csv_path = RUN_5M / 'ranked.csv'
    if not csv_path.exists():
        print(f"Error: {csv_path} does not exist yet. Please wait for training search to complete.")
        return

    df_ranked = pd.read_csv(csv_path)
    print(f"Loaded {len(df_ranked):,} qualified training candidates from {csv_path.name}")

    selected = []
    selected_cids = set()

    # Best per family for MNQ
    mnq_families = ('breakout', 'trend', 'momentum', 'hybrid', 'opening_range', 'regime', 'volatility')
    for fam in mnq_families:
        match = df_ranked[(df_ranked['instrument'] == 'MNQ') & (df_ranked['family'] == fam)].head(2)
        for _, r in match.iterrows():
            row = r.to_dict()
            if row['config_id'] not in selected_cids:
                selected.append(row)
                selected_cids.add(row['config_id'])

    # Best per family for MES
    mes_families = ('breakout', 'trend', 'momentum', 'hybrid', 'regime', 'opening_range')
    for fam in mes_families:
        match = df_ranked[(df_ranked['instrument'] == 'MES') & (df_ranked['family'] == fam)].head(2)
        for _, r in match.iterrows():
            row = r.to_dict()
            if row['config_id'] not in selected_cids:
                selected.append(row)
                selected_cids.add(row['config_id'])

    # Top overall velocity to 3k
    fastest_top = df_ranked.sort_values('weeks_to_3k').head(5)
    for _, r in fastest_top.iterrows():
        row = r.to_dict()
        if row['config_id'] not in selected_cids:
            selected.append(row)
            selected_cids.add(row['config_id'])

    print(f"Selected {len(selected)} diverse training finalists for frozen Validation evaluation:")
    for s in selected:
        print(f"  Rank {s['rank']}: {s['config_id']} | {s['instrument']} {s['family']} | Train Net: ${float(s['net_pnl']):,.2f} | Train DD: ${float(s['intrabar_dd']):,.2f} | Train Weekly: ${float(s['weekly_pnl']):.2f}/wk | Est Wks: {float(s['weeks_to_3k']):.1f} wks | Contracts: {s['max_contracts']} | Target: {s['target_r']}R")

    bars_cache = {}
    for inst in ('MNQ', 'MES'):
        print(f"Loading {inst} validation bars (2024-2025)...")
        bars_cache[inst] = load_validation_bars(inst)

    results = []
    configs_db = RUN_5M / 'configs.sqlite'
    c_conn = sqlite3.connect(configs_db)

    for s in selected:
        cid = s['config_id']
        cur = c_conn.execute("SELECT payload FROM configs WHERE config_id=?", (cid,))
        row = cur.fetchone()
        if not row:
            continue
        cfg = json.loads(row[0])
        inst = cfg['instrument']
        
        print(f"\nEvaluating {cid} ({inst} {cfg['family']} | {cfg['max_contracts']}c, {cfg['target_r']}R) on Validation (2024-2025)...")
        res = evaluate_candidate_validation(cfg, bars_cache[inst])
        
        print(f"  Val Net PnL: ${res['net_pnl']:,.2f} | Val DD: ${res['intrabar_dd']:,.2f} | PF: {res['profit_factor']:.2f} | Win Rate: {res['win_rate']*100:.1f}%")
        print(f"  Avg Monthly: ${res['avg_monthly_gain']:,.2f}/mo | Avg Weekly: ${res['avg_weekly_gain']:,.2f}/wk | Trades/wk: {res['trades_per_week']:.1f}")
        print(f"  Fastest Pass: {res['fastest_weeks_to_3k']} wks | Median: {res['median_weeks_to_3k']} wks | Cushion: ${res['dd_cushion']:,.2f}")

        results.append({
            'config_id': cid,
            'instrument': inst,
            'family': cfg['family'],
            'train_rank': s['rank'],
            'train_net_pnl': float(s['net_pnl']),
            'train_dd': float(s['intrabar_dd']),
            'train_weekly_pnl': float(s['weekly_pnl']),
            'train_weeks_to_3k': float(s['weeks_to_3k']),
            'val_net_pnl': res['net_pnl'],
            'val_intrabar_dd': res['intrabar_dd'],
            'val_closing_dd': res['closing_dd'],
            'val_profit_factor': res['profit_factor'],
            'val_win_rate': res['win_rate'],
            'val_trades': res['trades'],
            'val_avg_monthly_gain': res['avg_monthly_gain'],
            'val_avg_weekly_gain': res['avg_weekly_gain'],
            'val_trades_per_week': res['trades_per_week'],
            'val_fastest_weeks_to_3k': res['fastest_weeks_to_3k'],
            'val_median_weeks_to_3k': res['median_weeks_to_3k'],
            'val_pass_rate_pct': res['pass_rate_pct'],
            'val_dd_cushion': res['dd_cushion'],
            'parameters': cfg,
            'equity_curve': res['equity_curve'],
            'timestamps': res['timestamps']
        })

    c_conn.close()

    out_dir = ROOT / 'reports'
    out_dir.mkdir(parents=True, exist_ok=True)
    
    summary_list = []
    for r in results:
        r_copy = dict(r)
        del r_copy['equity_curve']
        del r_copy['timestamps']
        summary_list.append(r_copy)
        
    json_path = out_dir / 'validation_5m_standouts.json'
    with json_path.open('w', encoding='utf-8') as f:
        json.dump(summary_list, f, indent=2)

    curves_path = RUN_5M / 'validation_curves.json'
    with curves_path.open('w', encoding='utf-8') as f:
        json.dump(results, f)

    print(f"\nAll evaluations saved to {json_path} and {curves_path}")


if __name__ == '__main__':
    run_validation_evaluation()

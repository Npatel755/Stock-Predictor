"""Evaluate 2M Champions and Fast-Pass Portfolios on 2026 Test holdout data.

STRICTLY ZERO PARAMETER TUNING:
All parameters remain 100% frozen.
Authentic micro contract economics ($0.50/side commission, $0.37/side fees, 1-tick slippage, 1-tick spread).
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
from training_2m_policy import execution_cfg_2m

RUN_2M = ROOT / 'runs/training_search_2m_v1'
CATALOG = json.load(open(ROOT / 'data/catalog.json'))

tree = ast.parse((ROOT / 'runs/training_search_500k_v1/code/mass_research.py').read_text(encoding='utf-8'))
DUCKDB_QUERY = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith('SELECT time_bucket')][0]


def load_test_bars(symbol):
    p = CATALOG['instruments'][symbol]['splits']['test']['path']
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


def evaluate_candidate_test(c, bars):
    symbol = c['instrument']
    data = engine.arrays(bars)
    features = engine.features(bars, int(c['lookback']))
    raw_sig = engine.signal_for(c, features).astype(np.int8)
    mask = session_mask(bars, int(c['session_start']), int(c['session_end']))
    sig = np.where(mask, raw_sig, 0).astype(np.int8)

    cfg = execution_cfg_2m(c)
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
        'equity_curve': equity,
        'timestamps': ts
    }


def main():
    print("=== EVALUATING 2M CHAMPIONS & PORTFOLIOS ON 2026 TEST DATA (WITHOUT TUNING) ===")
    
    # Pre-load test bars
    test_bars = {}
    for sym in ('MNQ', 'MES'):
        print(f"Loading {sym} Test bars (2026-01-01 to 2026-11-05)...")
        test_bars[sym] = load_test_bars(sym)

    # Load parameters of finalists from configs.sqlite
    configs_db = RUN_2M / 'configs.sqlite'
    conn = sqlite3.connect(configs_db)

    # Standout champion list from validation
    cids = [
        'm2_a1f1cc46771107c0a9f9',  # MES Trend (2c, 7.0R)
        'm2_2a6dc4bf5f9f7a7836f4',  # MNQ Momentum (1c, 10.0R)
        'm2_95c765ba5d3a7183fc3e',  # MNQ Hybrid (1c, 6.0R)
        'm2_eaa56d8ebf97ab0a5540',  # MNQ Breakout (1c, 3.0R)
        'm2_0e614d16e089968432f7',  # MNQ Trend (1c, 5.0R)
        'm2_ec77fbb2cf1ce88b0134',  # MNQ Opening Range (1c, 2.5R)
    ]

    # Load validation results to merge lifetime metrics
    val_summary = {d['config_id']: d for d in json.load(open(ROOT / 'reports/validation_2m_standouts.json'))}

    eval_results = []
    equity_curves_dict = {}

    for cid in cids:
        cur = conn.execute("SELECT payload FROM configs WHERE config_id=?", (cid,))
        row = cur.fetchone()
        cfg = json.loads(row[0])
        sym = cfg['instrument']

        print(f"\nEvaluating {cid} ({sym} {cfg['family']} | {cfg['max_contracts']}c, {cfg['target_r']}R) on 2026 Test...")
        res = evaluate_candidate_test(cfg, test_bars[sym])
        
        v_info = val_summary.get(cid, {})
        train_net = v_info.get('train_net_pnl', 0.0)
        val_net = v_info.get('val_net_pnl', 0.0)
        test_net = res['net_pnl']
        lifetime_net = train_net + val_net + test_net
        worst_lifetime_dd = max(v_info.get('train_dd', 0.0), v_info.get('val_intrabar_dd', 0.0), res['intrabar_dd'])

        print(f"  Test Net PnL: ${res['net_pnl']:,.2f} | Test DD: ${res['intrabar_dd']:,.2f} | PF: {res['profit_factor']:.2f} | Win Rate: {res['win_rate']*100:.1f}%")
        print(f"  Avg Monthly: ${res['avg_monthly_gain']:,.2f}/mo | Avg Weekly: ${res['avg_weekly_gain']:,.2f}/wk | Trades/wk: {res['trades_per_week']:.1f}")
        print(f"  Fastest Pass: {res['fastest_weeks_to_3k']} wks | Median: {res['median_weeks_to_3k']} wks | Cushion: ${res['dd_cushion']:,.2f}")
        print(f"  LIFETIME NET (Train+Val+Test): ${lifetime_net:,.2f} | Worst DD: ${worst_lifetime_dd:,.2f} | All 3 Splits Positive: {train_net > 0 and val_net > 0 and test_net > 0}")

        eval_results.append({
            'config_id': cid,
            'instrument': sym,
            'family': cfg['family'],
            'max_contracts': cfg['max_contracts'],
            'target_r': cfg['target_r'],
            'stop_atr': cfg['stop_atr'],
            'train_net_pnl': train_net,
            'val_net_pnl': val_net,
            'test_net_pnl': test_net,
            'lifetime_net_pnl': lifetime_net,
            'test_intrabar_dd': res['intrabar_dd'],
            'worst_lifetime_dd': worst_lifetime_dd,
            'test_profit_factor': res['profit_factor'],
            'test_win_rate': res['win_rate'],
            'test_trades': res['trades'],
            'test_avg_monthly_gain': res['avg_monthly_gain'],
            'test_avg_weekly_gain': res['avg_weekly_gain'],
            'test_trades_per_week': res['trades_per_week'],
            'test_fastest_weeks_to_3k': res['fastest_weeks_to_3k'],
            'test_median_weeks_to_3k': res['median_weeks_to_3k'],
            'test_pass_rate_pct': res['pass_rate_pct'],
            'test_dd_cushion': res['dd_cushion'],
            'all_splits_positive': bool(train_net > 0 and val_net > 0 and test_net > 0),
            'parameters': cfg
        })

        equity_curves_dict[cid] = {
            'equity': res['equity_curve'].tolist(),
            'timestamps': [t.isoformat() for t in res['timestamps']]
        }

    conn.close()

    # Now evaluate Dual-Market Portfolios on Test
    print("\n=== EVALUATING DUAL-MARKET PORTFOLIOS ON 2026 TEST DATA ===")
    c_mes = equity_curves_dict['m2_a1f1cc46771107c0a9f9']
    c_hyb = equity_curves_dict['m2_95c765ba5d3a7183fc3e']
    c_mom = equity_curves_dict['m2_2a6dc4bf5f9f7a7836f4']
    c_brk = equity_curves_dict['m2_eaa56d8ebf97ab0a5540']

    df_mes = pd.DataFrame({'ts': pd.to_datetime(c_mes['timestamps']), 'pnl1': np.array(c_mes['equity']) - 50000.0})
    df_hyb = pd.DataFrame({'ts': pd.to_datetime(c_hyb['timestamps']), 'pnl2': np.array(c_hyb['equity']) - 50000.0})
    df_mom = pd.DataFrame({'ts': pd.to_datetime(c_mom['timestamps']), 'pnl3': np.array(c_mom['equity']) - 50000.0})
    df_brk = pd.DataFrame({'ts': pd.to_datetime(c_brk['timestamps']), 'pnl4': np.array(c_brk['equity']) - 50000.0})

    df_comb = pd.merge(df_mes, df_hyb, on='ts', how='outer').sort_values('ts').ffill().fillna(0)
    df_comb = pd.merge(df_comb, df_mom, on='ts', how='outer').sort_values('ts').ffill().fillna(0)
    df_comb = pd.merge(df_comb, df_brk, on='ts', how='outer').sort_values('ts').ffill().fillna(0)

    portfolios = {
        "Conservative Fast-Pass: MES Trend (2c) + MNQ Hybrid (6R)": df_comb['pnl1'] + df_comb['pnl2'],
        "High-Velocity Surge: MES Trend (2c) + MNQ Momentum (10R)": df_comb['pnl1'] + df_comb['pnl3'],
        "Intra-Market Dual: MNQ Momentum (10R) + MNQ Hybrid (6R)":  df_comb['pnl2'] + df_comb['pnl3'],
    }

    portfolio_results = []
    for pname, pnl_col in portfolios.items():
        total_net = float(pnl_col.iloc[-1])
        peak = pnl_col.cummax()
        max_dd = float((peak - pnl_col).max())
        cushion = 2000.0 - max_dd
        
        df_p = pd.DataFrame({'ts': df_comb['ts'], 'pnl': pnl_col})
        df_p['week'] = df_p['ts'].dt.to_period('W')
        df_p['month'] = df_p['ts'].dt.to_period('M')
        
        wk_pnl = df_p.groupby('week')['pnl'].last().diff().dropna().values
        mo_pnl = df_p.groupby('month')['pnl'].last().diff().dropna().values
        
        avg_wk = float(np.mean(wk_pnl)) if len(wk_pnl) > 0 else 0.0
        avg_mo = float(np.mean(mo_pnl)) if len(mo_pnl) > 0 else 0.0
        
        pass_st = compute_pass_stats(pnl_col + 50000.0, df_comb['ts'], target=3000.0, max_dd_limit=2000.0)

        print(f"Portfolio: {pname}")
        print(f"  Test Total Net PnL: ${total_net:,.2f}")
        print(f"  Test Max Drawdown:  ${max_dd:,.2f} (Safety Cushion: ${cushion:,.2f})")
        print(f"  Avg Monthly Gain:   ${avg_mo:,.2f}/mo")
        print(f"  Avg Weekly Gain:    ${avg_wk:,.2f}/wk")
        print(f"  Fastest Pass ($3k): {pass_st['fastest_weeks']} wks | Median: {pass_st['median_weeks']} wks | Pass Rate: {pass_st['pass_rate_pct']:.1f}%")
        print("-" * 75)

        portfolio_results.append({
            'portfolio_name': pname,
            'test_net_pnl': total_net,
            'test_max_dd': max_dd,
            'test_dd_cushion': cushion,
            'test_avg_monthly_gain': avg_mo,
            'test_avg_weekly_gain': avg_wk,
            'test_fastest_weeks_to_3k': pass_st['fastest_weeks'],
            'test_median_weeks_to_3k': pass_st['median_weeks'],
            'test_pass_rate_pct': pass_st['pass_rate_pct']
        })

    # Save all test results
    out_dir = ROOT / 'reports'
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / 'test_2m_champions_summary.json', 'w') as f:
        json.dump({'single_strategies': eval_results, 'portfolios': portfolio_results}, f, indent=2)

    with open(RUN_2M / 'test_curves.json', 'w') as f:
        json.dump({
            'single_curves': equity_curves_dict,
            'df_comb_ts': [t.isoformat() for t in df_comb['ts']],
            'pnl_mes_hyb': (df_comb['pnl1'] + df_comb['pnl2']).tolist(),
            'pnl_mes_mom': (df_comb['pnl1'] + df_comb['pnl3']).tolist(),
        }, f)

    print("\nSaved all test evaluations to reports/test_2m_champions_summary.json and test_curves.json")


if __name__ == '__main__':
    main()

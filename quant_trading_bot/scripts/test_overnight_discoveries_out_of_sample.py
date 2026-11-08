"""Out-of-Sample Verification of Overnight Discoveries.
Evaluates the top configurations discovered on Training data (2020-2023) against
Validation (2024-2025) and Test (2026) with ZERO TUNING.
"""
import ast
import json
from pathlib import Path
import sys
import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'scripts'))

from quant_futures.data import canonical

RUN_DIR = ROOT / 'runs/overnight_institutional_research'
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


def compute_atr(high, low, close, window=14):
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(window).mean()


def simulate_trades(opens, highs, lows, closes, mins, atrs, sigs, stop_mult, target_r, trail_mult, max_hold, mult=2.0, tick=0.25, fee_per_side=0.50, slip_ticks=1.0, risk_target=200.0, max_qty=2, dynamic_sizing=False):
    adverse = tick * slip_ticks
    n = len(opens)
    trades = []
    cash = 50000.0
    equity = np.full(n, 50000.0, dtype=np.float64)
    worst = np.full(n, 50000.0, dtype=np.float64)

    side, qty = 0, 0
    entry_px, stop_px, target_px = 0.0, 0.0, 0.0
    entry_bar = 0
    flat_min = 15 * 60 + 55

    for i in range(1, n):
        if side != 0 and trail_mult > 0.0:
            trail_dist = trail_mult * atrs[i-1]
            if side > 0:
                proposed = round((closes[i-1] - trail_dist) / tick) * tick
                stop_px = max(stop_px, proposed)
            else:
                proposed = round((closes[i-1] + trail_dist) / tick) * tick
                stop_px = min(stop_px, proposed)

        if side != 0:
            exit_reason = None
            exit_px = 0.0

            if mins[i] >= flat_min:
                exit_reason = 'session_flat'
                exit_px = opens[i] - side * adverse
            elif (i - entry_bar) >= max_hold:
                exit_reason = 'time_exit'
                exit_px = opens[i] - side * adverse
            elif (lows[i] <= stop_px if side > 0 else highs[i] >= stop_px):
                exit_reason = 'stop'
                exit_px = stop_px - side * adverse
            elif (highs[i] >= target_px + tick if side > 0 else lows[i] <= target_px - tick):
                exit_reason = 'target'
                exit_px = target_px

            if exit_reason is not None:
                gross = side * qty * (exit_px - entry_px) * mult
                fees = qty * fee_per_side * 2.0
                net = gross - fees
                cash += net
                trades.append({'net_pnl': net, 'side': side, 'qty': qty, 'reason': exit_reason})
                side, qty = 0, 0

        if side == 0 and mins[i] < flat_min:
            prev_sig = sigs[i-1]
            if prev_sig != 0 and np.isfinite(atrs[i-1]) and atrs[i-1] > 0.0:
                side = prev_sig
                entry_px = opens[i] + side * adverse
                entry_bar = i

                point_risk = stop_mult * atrs[i-1]
                if dynamic_sizing:
                    dollar_risk_per_c = point_risk * mult + 2.0 * fee_per_side + 2.0 * adverse * mult
                    qty = max(1, min(max_qty, int(np.floor(risk_target / dollar_risk_per_c))))
                else:
                    qty = max_qty

                stop_dist = round(point_risk / tick) * tick
                stop_px = entry_px - side * stop_dist

                target_dist = round((stop_mult * target_r * atrs[i-1]) / tick) * tick
                target_px = entry_px + side * target_dist

        if side != 0:
            unrealized = side * qty * (closes[i] - entry_px) * mult - qty * fee_per_side * 2.0
            worst_bar = lows[i] if side > 0 else highs[i]
            unrealized_worst = side * qty * (worst_bar - entry_px) * mult - qty * fee_per_side * 2.0
            equity[i] = cash + unrealized
            worst[i] = cash + min(unrealized, unrealized_worst)
        else:
            equity[i] = cash
            worst[i] = cash

    peak = np.maximum.accumulate(equity)
    intrabar_dd = float(np.max(peak - worst))
    net_pnl = float(cash - 50000.0)

    wins = [t for t in trades if t['net_pnl'] > 0]
    losses = [t for t in trades if t['net_pnl'] < 0]
    win_rate = len(wins) / len(trades) if trades else 0.0
    gross_win = sum(t['net_pnl'] for t in wins)
    gross_loss = abs(sum(t['net_pnl'] for t in losses))
    pf = (gross_win / gross_loss) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0)

    return {
        'net_pnl': round(net_pnl, 2),
        'trades': len(trades),
        'win_rate': round(win_rate, 4),
        'profit_factor': round(pf, 3),
        'intrabar_dd': round(intrabar_dd, 2),
        'equity': equity,
        'worst': worst
    }


def prepare_data(split_name):
    b_mes = load_split('MES', split_name)
    b_mnq = load_split('MNQ', split_name)

    b_mes['atr'] = compute_atr(b_mes['high'], b_mes['low'], b_mes['close'])
    b_mnq['atr'] = compute_atr(b_mnq['high'], b_mnq['low'], b_mnq['close'])

    aligned = pd.merge(
        b_mes[['timestamp_utc', 'open', 'high', 'low', 'close', 'atr']],
        b_mnq[['timestamp_utc', 'open', 'high', 'low', 'close', 'atr']],
        on='timestamp_utc',
        suffixes=('_mes', '_mnq')
    ).sort_values('timestamp_utc').reset_index(drop=True)

    local = aligned['timestamp_utc'].dt.tz_convert('America/New_York')
    mins = (local.dt.hour * 60 + local.dt.minute).to_numpy()
    weekdays = (local.dt.weekday < 5).to_numpy()

    return {
        'aligned': aligned,
        'mins': mins,
        'weekdays': weekdays,
        'opens_mnq': aligned['open_mnq'].to_numpy(dtype=np.float64),
        'highs_mnq': aligned['high_mnq'].to_numpy(dtype=np.float64),
        'lows_mnq': aligned['low_mnq'].to_numpy(dtype=np.float64),
        'closes_mnq': aligned['close_mnq'].to_numpy(dtype=np.float64),
        'atrs_mnq': aligned['atr_mnq'].to_numpy(dtype=np.float64),
        'opens_mes': aligned['open_mes'].to_numpy(dtype=np.float64),
        'highs_mes': aligned['high_mes'].to_numpy(dtype=np.float64),
        'lows_mes': aligned['low_mes'].to_numpy(dtype=np.float64),
        'closes_mes': aligned['close_mes'].to_numpy(dtype=np.float64),
        'atrs_mes': aligned['atr_mes'].to_numpy(dtype=np.float64)
    }


def evaluate_all():
    print("Loading data for all splits: Train (2020-2023), Validation (2024-2025), Test (2026)...", flush=True)
    splits_data = {s: prepare_data(s) for s in ['train', 'validation', 'test']}

    candidates = [
        {
            'name': 'Candidate 1: MNQ Morning Breakout with MES Breadth Filter (0.50 thresh)',
            'type': 'single_sleeve',
            'run_func': lambda d: simulate_trades(
                d['opens_mnq'], d['highs_mnq'], d['lows_mnq'], d['closes_mnq'], d['mins'], d['atrs_mnq'],
                sigs=np.where(
                    (d['mins'] >= 600) & (d['mins'] < 720) & d['weekdays'] &
                    (((pd.Series(d['closes_mnq']) - pd.Series(d['closes_mnq']).shift(10)) / (d['atrs_mnq'] * np.sqrt(10))) > 1.25) &
                    (((pd.Series(d['closes_mes']) - pd.Series(d['closes_mes']).shift(16)) / (d['atrs_mes'] * np.sqrt(16))) > 0.50), 1,
                    np.where(
                        (d['mins'] >= 600) & (d['mins'] < 720) & d['weekdays'] &
                        (((pd.Series(d['closes_mnq']) - pd.Series(d['closes_mnq']).shift(10)) / (d['atrs_mnq'] * np.sqrt(10))) < -1.25) &
                        (((pd.Series(d['closes_mes']) - pd.Series(d['closes_mes']).shift(16)) / (d['atrs_mes'] * np.sqrt(16))) < -0.50), -1, 0
                    )
                ).astype(np.int8),
                stop_mult=1.75, target_r=2.25, trail_mult=2.0, max_hold=8, mult=2.0, max_qty=2, dynamic_sizing=False
            )
        },
        {
            'name': 'Candidate 2: MNQ Afternoon Institutional Runner (13:00-15:45 EST)',
            'type': 'single_sleeve',
            'run_func': lambda d: simulate_trades(
                d['opens_mnq'], d['highs_mnq'], d['lows_mnq'], d['closes_mnq'], d['mins'], d['atrs_mnq'],
                sigs=np.where(
                    (d['mins'] >= 780) & (d['mins'] < 945) & d['weekdays'] &
                    (((pd.Series(d['closes_mnq']) - pd.Series(d['closes_mnq']).shift(12)) / (d['atrs_mnq'] * np.sqrt(12))) > 1.25), 1,
                    np.where(
                        (d['mins'] >= 780) & (d['mins'] < 945) & d['weekdays'] &
                        (((pd.Series(d['closes_mnq']) - pd.Series(d['closes_mnq']).shift(12)) / (d['atrs_mnq'] * np.sqrt(12))) < -1.25), -1, 0
                    )
                ).astype(np.int8),
                stop_mult=1.75, target_r=2.0, trail_mult=2.0, max_hold=10, mult=2.0, max_qty=1, dynamic_sizing=False
            )
        },
        {
            'name': 'Candidate 3: MNQ Volatility-Targeted Momentum Alpha (Lookback 8, Stop 1.25, Target 2.0R, $200 Budget)',
            'type': 'single_sleeve',
            'run_func': lambda d: simulate_trades(
                d['opens_mnq'], d['highs_mnq'], d['lows_mnq'], d['closes_mnq'], d['mins'], d['atrs_mnq'],
                sigs=np.where(
                    (d['mins'] >= 600) & (d['mins'] < 720) & d['weekdays'] &
                    (((pd.Series(d['closes_mnq']) - pd.Series(d['closes_mnq']).shift(8)) / (d['atrs_mnq'] * np.sqrt(8))) > 1.5), 1,
                    np.where(
                        (d['mins'] >= 600) & (d['mins'] < 720) & d['weekdays'] &
                        (((pd.Series(d['closes_mnq']) - pd.Series(d['closes_mnq']).shift(8)) / (d['atrs_mnq'] * np.sqrt(8))) < -1.5), -1, 0
                    )
                ).astype(np.int8),
                stop_mult=1.25, target_r=2.0, trail_mult=2.0, max_hold=8, mult=2.0, risk_target=200.0, max_qty=2, dynamic_sizing=True
            )
        },
        {
            'name': 'Candidate 4: MNQ Ultra-Low DD Vol-Target Alpha (Lookback 12, Thresh 1.75, Stop 1.25, Target 2.0R, $200 Budget)',
            'type': 'single_sleeve',
            'run_func': lambda d: simulate_trades(
                d['opens_mnq'], d['highs_mnq'], d['lows_mnq'], d['closes_mnq'], d['mins'], d['atrs_mnq'],
                sigs=np.where(
                    (d['mins'] >= 600) & (d['mins'] < 720) & d['weekdays'] &
                    (((pd.Series(d['closes_mnq']) - pd.Series(d['closes_mnq']).shift(12)) / (d['atrs_mnq'] * np.sqrt(12))) > 1.75), 1,
                    np.where(
                        (d['mins'] >= 600) & (d['mins'] < 720) & d['weekdays'] &
                        (((pd.Series(d['closes_mnq']) - pd.Series(d['closes_mnq']).shift(12)) / (d['atrs_mnq'] * np.sqrt(12))) < -1.75), -1, 0
                    )
                ).astype(np.int8),
                stop_mult=1.25, target_r=2.0, trail_mult=2.0, max_hold=8, mult=2.0, risk_target=200.0, max_qty=2, dynamic_sizing=True
            )
        },
        {
            'name': 'Candidate 5: Portfolio G (Tri-Session Book: MES Mom 2c + MNQ AM Breakout 1c + MNQ PM Runner 1c)',
            'type': 'portfolio',
            'run_func': lambda d: run_portfolio_g(d)
        }
    ]

    def run_portfolio_g(d):
        # Sleeve 1: MES Mom 2c (09:45 - 15:45)
        sig_mes = np.where(
            (d['mins'] >= 585) & (d['mins'] < 945) & d['weekdays'] &
            (((pd.Series(d['closes_mes']) - pd.Series(d['closes_mes']).shift(16)) / (d['atrs_mes'] * np.sqrt(16))) > 1.5), 1,
            np.where(
                (d['mins'] >= 585) & (d['mins'] < 945) & d['weekdays'] &
                (((pd.Series(d['closes_mes']) - pd.Series(d['closes_mes']).shift(16)) / (d['atrs_mes'] * np.sqrt(16))) < -1.5), -1, 0
            )
        ).astype(np.int8)
        res_s1 = simulate_trades(d['opens_mes'], d['highs_mes'], d['lows_mes'], d['closes_mes'], d['mins'], d['atrs_mes'],
                                 sig_mes, stop_mult=1.75, target_r=2.5, trail_mult=2.0, max_hold=999, mult=5.0, max_qty=2, dynamic_sizing=False)

        # Sleeve 2: MNQ Morning Breakout 1c (10:00 - 12:00) with MES confirmation
        sig_mnq_am = np.where(
            (d['mins'] >= 600) & (d['mins'] < 720) & d['weekdays'] &
            (((pd.Series(d['closes_mnq']) - pd.Series(d['closes_mnq']).shift(10)) / (d['atrs_mnq'] * np.sqrt(10))) > 1.25) &
            (((pd.Series(d['closes_mes']) - pd.Series(d['closes_mes']).shift(16)) / (d['atrs_mes'] * np.sqrt(16))) > 0.0), 1,
            np.where(
                (d['mins'] >= 600) & (d['mins'] < 720) & d['weekdays'] &
                (((pd.Series(d['closes_mnq']) - pd.Series(d['closes_mnq']).shift(10)) / (d['atrs_mnq'] * np.sqrt(10))) < -1.25) &
                (((pd.Series(d['closes_mes']) - pd.Series(d['closes_mes']).shift(16)) / (d['atrs_mes'] * np.sqrt(16))) < 0.0), -1, 0
            )
        ).astype(np.int8)
        res_s2 = simulate_trades(d['opens_mnq'], d['highs_mnq'], d['lows_mnq'], d['closes_mnq'], d['mins'], d['atrs_mnq'],
                                 sig_mnq_am, stop_mult=1.75, target_r=2.25, trail_mult=2.0, max_hold=8, mult=2.0, max_qty=1, dynamic_sizing=False)

        # Sleeve 3: MNQ PM Runner 1c (13:00 - 15:45)
        sig_mnq_pm = np.where(
            (d['mins'] >= 780) & (d['mins'] < 945) & d['weekdays'] &
            (((pd.Series(d['closes_mnq']) - pd.Series(d['closes_mnq']).shift(12)) / (d['atrs_mnq'] * np.sqrt(12))) > 1.25), 1,
            np.where(
                (d['mins'] >= 780) & (d['mins'] < 945) & d['weekdays'] &
                (((pd.Series(d['closes_mnq']) - pd.Series(d['closes_mnq']).shift(12)) / (d['atrs_mnq'] * np.sqrt(12))) < -1.25), -1, 0
            )
        ).astype(np.int8)
        res_s3 = simulate_trades(d['opens_mnq'], d['highs_mnq'], d['lows_mnq'], d['closes_mnq'], d['mins'], d['atrs_mnq'],
                                 sig_mnq_pm, stop_mult=1.75, target_r=2.0, trail_mult=2.0, max_hold=10, mult=2.0, max_qty=1, dynamic_sizing=False)

        comb_equity = 50000.0 + (res_s1['equity'] - 50000.0) + (res_s2['equity'] - 50000.0) + (res_s3['equity'] - 50000.0)
        comb_worst = 50000.0 + (res_s1['worst'] - 50000.0) + (res_s2['worst'] - 50000.0) + (res_s3['worst'] - 50000.0)
        comb_peak = np.maximum.accumulate(comb_equity)
        comb_dd = float(np.max(comb_peak - comb_worst))
        comb_net = float(comb_equity[-1] - 50000.0)
        total_trades = res_s1['trades'] + res_s2['trades'] + res_s3['trades']

        return {
            'net_pnl': round(comb_net, 2),
            'intrabar_dd': round(comb_dd, 2),
            'trades': total_trades,
            'win_rate': round((res_s1['win_rate']*res_s1['trades'] + res_s2['win_rate']*res_s2['trades'] + res_s3['win_rate']*res_s3['trades']) / max(1, total_trades), 4),
            'profit_factor': 0.0,
            'equity': comb_equity,
            'worst': comb_worst
        }

    results_table = []

    print("\n" + "=" * 90)
    print("STRICT OUT-OF-SAMPLE EVALUATION (NO TUNING ON VALIDATION OR TEST)")
    print("=" * 90)

    for cand in candidates:
        name = cand['name']
        print(f"\nEvaluating: {name}...")
        row = {'name': name}

        train_res = cand['run_func'](splits_data['train'])
        val_res = cand['run_func'](splits_data['validation'])
        test_res = cand['run_func'](splits_data['test'])

        row['train_net'] = train_res['net_pnl']
        row['train_dd'] = train_res['intrabar_dd']
        row['train_pf'] = train_res['profit_factor']
        row['train_trades'] = train_res['trades']

        row['val_net'] = val_res['net_pnl']
        row['val_dd'] = val_res['intrabar_dd']
        row['val_pf'] = val_res['profit_factor']
        row['val_trades'] = val_res['trades']

        row['test_net'] = test_res['net_pnl']
        row['test_dd'] = test_res['intrabar_dd']
        row['test_pf'] = test_res['profit_factor']
        row['test_trades'] = test_res['trades']

        row['7yr_net'] = round(train_res['net_pnl'] + val_res['net_pnl'] + test_res['net_pnl'], 2)
        row['worst_7yr_dd'] = round(max(train_res['intrabar_dd'], val_res['intrabar_dd'], test_res['intrabar_dd']), 2)
        row['passed_2k_rule'] = bool(row['worst_7yr_dd'] < 2000.0)

        results_table.append(row)

        print(f"  TRAIN (2020-2023) : Net +${train_res['net_pnl']:>9,.2f} | DD: ${train_res['intrabar_dd']:>8,.2f} | PF: {train_res['profit_factor']:>4.2f} | Trades: {train_res['trades']}")
        print(f"  VAL   (2024-2025) : Net +${val_res['net_pnl']:>9,.2f} | DD: ${val_res['intrabar_dd']:>8,.2f} | PF: {val_res['profit_factor']:>4.2f} | Trades: {val_res['trades']}")
        print(f"  TEST  (2026)      : Net +${test_res['net_pnl']:>9,.2f} | DD: ${test_res['intrabar_dd']:>8,.2f} | PF: {test_res['profit_factor']:>4.2f} | Trades: {test_res['trades']}")
        print(f"  7-YR LIFETIME     : Net +${row['7yr_net']:>9,.2f} | Worst DD: ${row['worst_7yr_dd']:>8,.2f} | Strictly <$2k: {row['passed_2k_rule']}")

    df_out = pd.DataFrame(results_table)
    df_out.to_csv(RUN_DIR / 'overnight_discoveries_out_of_sample_audit.csv', index=False)
    print("\nSaved full audit table to:", RUN_DIR / 'overnight_discoveries_out_of_sample_audit.csv')


if __name__ == '__main__':
    evaluate_all()

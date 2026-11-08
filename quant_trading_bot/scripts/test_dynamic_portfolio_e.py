"""Test Citadel-style Dynamic Volatility Sizing on Portfolio E across all 3 splits."""
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

CATALOG = json.load(open(ROOT / 'data/catalog.json'))
tree = ast.parse((ROOT / 'runs/training_search_500k_v1/code/mass_research.py').read_text(encoding='utf-8'))
DUCKDB_QUERY = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith('SELECT time_bucket')][0]


def load_data(sym, split):
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


def simulate_dynamic(
    opens, highs, lows, closes, mins, atrs, sigs,
    stop_mult, target_r, trail_mult, max_hold, mult,
    risk_budget=200.0, max_contracts=3, min_contracts=1,
    tick=0.25, fee_per_side=0.50, slip_ticks=1.0, dynamic=True
):
    adverse = tick * slip_ticks
    n = len(opens)
    trades = []
    cash = 50000.0
    equity = np.full(n, 50000.0, dtype=np.float64)
    worst = np.full(n, 50000.0, dtype=np.float64)

    side = 0
    qty = 0
    entry_px = 0.0
    stop_px = 0.0
    target_px = 0.0
    entry_bar = 0

    flat_min = 15 * 60 + 55  # 3:55 PM EST

    for i in range(1, n):
        # 1. Trailing stop
        if side != 0 and trail_mult > 0.0:
            trail_dist = trail_mult * atrs[i-1]
            if side > 0:
                proposed = round((closes[i-1] - trail_dist) / tick) * tick
                stop_px = max(stop_px, proposed)
            else:
                proposed = round((closes[i-1] + trail_dist) / tick) * tick
                stop_px = min(stop_px, proposed)

        # 2. Check exits on current bar (STOP FIRST)
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
                trades.append({
                    'net_pnl': net,
                    'side': side,
                    'qty': qty,
                    'reason': exit_reason
                })
                side = 0
                qty = 0

        # 3. Check entry from previous bar
        if side == 0 and mins[i] < flat_min:
            prev_sig = sigs[i-1]
            if prev_sig != 0 and np.isfinite(atrs[i-1]) and atrs[i-1] > 0.0:
                side = prev_sig
                entry_px = opens[i] + side * adverse
                entry_bar = i

                point_risk = stop_mult * atrs[i-1]
                if dynamic:
                    dollar_risk_per_c = point_risk * mult + 2.0 * fee_per_side + 2.0 * adverse * mult
                    qty = max(min_contracts, min(max_contracts, int(np.floor(risk_budget / dollar_risk_per_c))))
                else:
                    qty = max_contracts

                stop_dist = round(point_risk / tick) * tick
                stop_px = entry_px - side * stop_dist

                target_dist = round((stop_mult * target_r * atrs[i-1]) / tick) * tick
                target_px = entry_px + side * target_dist

        # 4. Mark to market
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
    win_rate = len(wins) / len(trades) if trades else 0.0

    return {
        'net_pnl': round(net_pnl, 2),
        'trades': len(trades),
        'win_rate': round(win_rate, 4),
        'intrabar_dd': round(intrabar_dd, 2),
        'equity': equity,
        'worst': worst
    }


def evaluate_combo(split_name, dynamic=False, mes_budget=300.0, mnq_budget=200.0):
    b_mes = load_data('MES', split_name)
    b_mnq = load_data('MNQ', split_name)

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

    opens_mes = aligned['open_mes'].to_numpy(dtype=np.float64)
    highs_mes = aligned['high_mes'].to_numpy(dtype=np.float64)
    lows_mes = aligned['low_mes'].to_numpy(dtype=np.float64)
    closes_mes = aligned['close_mes'].to_numpy(dtype=np.float64)
    atrs_mes = aligned['atr_mes'].to_numpy(dtype=np.float64)

    opens_mnq = aligned['open_mnq'].to_numpy(dtype=np.float64)
    highs_mnq = aligned['high_mnq'].to_numpy(dtype=np.float64)
    lows_mnq = aligned['low_mnq'].to_numpy(dtype=np.float64)
    closes_mnq = aligned['close_mnq'].to_numpy(dtype=np.float64)
    atrs_mnq = aligned['atr_mnq'].to_numpy(dtype=np.float64)

    # Leg 1: MES Momentum (Lookback 16, Thresh 1.5, Stop 1.75, Target 2.5R, Trail 2.0, Session 09:45-15:45, Max 3c)
    mom_mes = (pd.Series(closes_mes) - pd.Series(closes_mes).shift(16)) / (atrs_mes * np.sqrt(16))
    in_mes = (mins >= 585) & (mins < 945) & weekdays
    sig_mes = np.where(in_mes & (mom_mes > 1.5), 1, np.where(in_mes & (mom_mes < -1.5), -1, 0)).astype(np.int8)

    res_mes = simulate_dynamic(
        opens_mes, highs_mes, lows_mes, closes_mes, mins, atrs_mes, sig_mes,
        stop_mult=1.75, target_r=2.5, trail_mult=2.0, max_hold=999, mult=5.0,
        risk_budget=mes_budget, max_contracts=3, min_contracts=1, dynamic=dynamic
    )

    # Leg 2: MNQ Morning Breakout (Lookback 10, Thresh 1.25, Stop 1.75, Target 2.25R, Trail 2.0, Hold 8, Session 10:00-12:00, Max 2c)
    mom_mnq = (pd.Series(closes_mnq) - pd.Series(closes_mnq).shift(10)) / (atrs_mnq * np.sqrt(10))
    in_mnq = (mins >= 600) & (mins < 720) & weekdays
    sig_mnq = np.where(in_mnq & (mom_mnq > 1.25), 1, np.where(in_mnq & (mom_mnq < -1.25), -1, 0)).astype(np.int8)

    res_mnq = simulate_dynamic(
        opens_mnq, highs_mnq, lows_mnq, closes_mnq, mins, atrs_mnq, sig_mnq,
        stop_mult=1.75, target_r=2.25, trail_mult=2.0, max_hold=8, mult=2.0,
        risk_budget=mnq_budget, max_contracts=2, min_contracts=1, dynamic=dynamic
    )

    # Combine Mark-to-Market
    comb_equity = 50000.0 + (res_mes['equity'] - 50000.0) + (res_mnq['equity'] - 50000.0)
    comb_worst = 50000.0 + (res_mes['worst'] - 50000.0) + (res_mnq['worst'] - 50000.0)
    comb_peak = np.maximum.accumulate(comb_equity)
    comb_dd = float(np.max(comb_peak - comb_worst))
    comb_net = float(comb_equity[-1] - 50000.0)

    return {
        'split': split_name,
        'net_pnl': round(comb_net, 2),
        'intrabar_dd': round(comb_dd, 2),
        'mes_net': res_mes['net_pnl'],
        'mes_dd': res_mes['intrabar_dd'],
        'mnq_net': res_mnq['net_pnl'],
        'mnq_dd': res_mnq['intrabar_dd'],
    }


def main():
    print("=" * 75)
    print("COMPARISON: STATIC PORTFOLIO E vs CITADEL DYNAMIC VOL-TARGETED PORTFOLIO E")
    print("=" * 75)

    print("\n--- 1. STATIC SIZING (3c MES, 2c MNQ) ---")
    static_results = {}
    for sp in ['train', 'validation', 'test']:
        r = evaluate_combo(sp, dynamic=False)
        static_results[sp] = r
        print(f"  {sp.upper():12s}: Net +${r['net_pnl']:>9,.2f}  |  Drawdown: ${r['intrabar_dd']:>8,.2f}")
    static_7yr_net = sum(r['net_pnl'] for r in static_results.values())
    static_worst_dd = max(r['intrabar_dd'] for r in static_results.values())
    print(f"  7-YEAR NET  : +${static_7yr_net:>9,.2f}  |  Worst DD : ${static_worst_dd:>8,.2f}")

    print("\n--- 2. CITADEL DYNAMIC VOL SIZING (MES $250 Budget, MNQ $175 Budget) ---")
    dyn_results = {}
    for sp in ['train', 'validation', 'test']:
        r = evaluate_combo(sp, dynamic=True, mes_budget=250.0, mnq_budget=175.0)
        dyn_results[sp] = r
        print(f"  {sp.upper():12s}: Net +${r['net_pnl']:>9,.2f}  |  Drawdown: ${r['intrabar_dd']:>8,.2f}")
    dyn_7yr_net = sum(r['net_pnl'] for r in dyn_results.values())
    dyn_worst_dd = max(r['intrabar_dd'] for r in dyn_results.values())
    print(f"  7-YEAR NET  : +${dyn_7yr_net:>9,.2f}  |  Worst DD : ${dyn_worst_dd:>8,.2f}")

    print("\n--- 3. CITADEL ULTRA-CONSERVATIVE VOL SIZING (MES $200 Budget, MNQ $150 Budget) ---")
    ultra_results = {}
    for sp in ['train', 'validation', 'test']:
        r = evaluate_combo(sp, dynamic=True, mes_budget=200.0, mnq_budget=150.0)
        ultra_results[sp] = r
        print(f"  {sp.upper():12s}: Net +${r['net_pnl']:>9,.2f}  |  Drawdown: ${r['intrabar_dd']:>8,.2f}")
    ultra_7yr_net = sum(r['net_pnl'] for r in ultra_results.values())
    ultra_worst_dd = max(r['intrabar_dd'] for r in ultra_results.values())
    print(f"  7-YEAR NET  : +${ultra_7yr_net:>9,.2f}  |  Worst DD : ${ultra_worst_dd:>8,.2f}")


if __name__ == '__main__':
    main()

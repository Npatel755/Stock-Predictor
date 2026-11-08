"""Institutional Relative Volume (RVOL) & Order Flow Expansion Engine.
Evaluates volume-confirmed momentum breakouts strictly on Training data (2020-2023).
"""
import ast
import json
from pathlib import Path
import sys
import time
import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'scripts'))

from quant_futures.data import canonical

RUN_DIR = ROOT / 'runs/overnight_institutional_research'
RUN_DIR.mkdir(parents=True, exist_ok=True)

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


def simulate_trades(opens, highs, lows, closes, mins, atrs, sigs, stop_mult, target_r, trail_mult, max_hold, mult, tick=0.25, fee_per_side=0.50, slip_ticks=1.0, risk_target=200.0, max_qty=2):
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
                dollar_risk_per_c = point_risk * mult + 2.0 * fee_per_side + 2.0 * adverse * mult
                qty = max(1, min(max_qty, int(np.floor(risk_target / dollar_risk_per_c))))

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
    intrabar_dd = np.max(peak - worst)
    net_pnl = cash - 50000.0

    wins = [t for t in trades if t['net_pnl'] > 0]
    losses = [t for t in trades if t['net_pnl'] < 0]
    win_rate = len(wins) / len(trades) if trades else 0.0
    gross_win = sum(t['net_pnl'] for t in wins)
    gross_loss = abs(sum(t['net_pnl'] for t in losses))
    pf = (gross_win / gross_loss) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0)

    return {
        'net_pnl': net_pnl,
        'trades': len(trades),
        'win_rate': win_rate,
        'profit_factor': pf,
        'intrabar_dd': intrabar_dd
    }


def main():
    print("=" * 85, flush=True)
    print("ORDER FLOW & RELATIVE VOLUME (RVOL) INSTITUTIONAL ALPHA RESEARCH")
    print("STRICT MANDATE: 100% Training Data (2020-2023). Zero touch on Validation/Test.", flush=True)
    print("=" * 85, flush=True)

    b_mnq = load_split('MNQ', 'train')
    b_mnq['atr'] = compute_atr(b_mnq['high'], b_mnq['low'], b_mnq['close'])

    local = b_mnq['timestamp_utc'].dt.tz_convert('America/New_York')
    mins = (local.dt.hour * 60 + local.dt.minute).to_numpy()
    weekdays = (local.dt.weekday < 5).to_numpy()

    opens = b_mnq['open'].to_numpy(dtype=np.float64)
    highs = b_mnq['high'].to_numpy(dtype=np.float64)
    lows = b_mnq['low'].to_numpy(dtype=np.float64)
    closes = b_mnq['close'].to_numpy(dtype=np.float64)
    volumes = b_mnq['volume'].to_numpy(dtype=np.float64)
    atrs = b_mnq['atr'].to_numpy(dtype=np.float64)

    # Compute Relative Volume (RVOL = volume / rolling 20-bar avg volume)
    vol_sma20 = pd.Series(volumes).rolling(20).mean().to_numpy()
    rvol = np.where(vol_sma20 > 0, volumes / vol_sma20, 1.0)

    # Momentum baseline
    mnq_mom = (pd.Series(closes) - pd.Series(closes).shift(10)) / (atrs * np.sqrt(10))

    rvol_results = []
    # Test different RVOL thresholds
    for rvol_thresh in [1.0, 1.25, 1.5, 1.75, 2.0]:
        in_am = (mins >= 600) & (mins < 720) & weekdays & (rvol >= rvol_thresh)
        sigs = np.where(in_am & (mnq_mom > 1.25), 1, np.where(in_am & (mnq_mom < -1.25), -1, 0)).astype(np.int8)

        for tr in [2.25, 2.5, 3.0]:
            res = simulate_trades(opens, highs, lows, closes, mins, atrs, sigs, stop_mult=1.75, target_r=tr, trail_mult=2.0, max_hold=8, mult=2.0, risk_target=200.0)
            if res['trades'] >= 50:
                rvol_results.append({
                    'rvol_thresh': rvol_thresh,
                    'target_r': tr,
                    'net_pnl': res['net_pnl'],
                    'intrabar_dd': res['intrabar_dd'],
                    'win_rate': res['win_rate'],
                    'profit_factor': res['profit_factor'],
                    'trades': res['trades']
                })

    df = pd.DataFrame(rvol_results)
    if not df.empty:
        df = df.sort_values('profit_factor', ascending=False)
        out = RUN_DIR / 'rvol_orderflow_train_results.csv'
        df.to_csv(out, index=False)
        print("\nTop RVOL Institutional Breakout Qualifiers (TRAINING ONLY):")
        print(df.head(6).to_string(index=False))

        best = df.iloc[0]
        print(f"\nOptimal RVOL Threshold: {best['rvol_thresh']}x | Net: +${best['net_pnl']:,.2f} | PF: {best['profit_factor']:.2f} | DD: ${best['intrabar_dd']:,.2f} | WR: {best['win_rate']*100:.1f}%")


if __name__ == '__main__':
    main()

"""Cross-Asset Lead-Lag Predictive Horizon Alpha Engine.
Evaluates whether S&P 500 (MES) momentum leads Nasdaq (MNQ) breakouts by 1 to 2 bars (15-30m).
Strictly on Training data (2020-2023). Zero touch on Validation/Test.
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


def simulate_trades(opens, highs, lows, closes, mins, atrs, sigs, stop_mult, target_r, trail_mult, max_hold, mult=2.0, tick=0.25, fee_per_side=0.50, slip_ticks=1.0, risk_target=200.0, max_qty=2):
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
    print("CROSS-ASSET LEAD-LAG HORIZON ARBITRAGE (TRAINING 2020-2023)")
    print("Evaluating whether lagged S&P (MES) impulse predicts Nasdaq (MNQ) continuation...", flush=True)
    print("=" * 85, flush=True)

    b_mes = load_split('MES', 'train')
    b_mnq = load_split('MNQ', 'train')

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

    opens = aligned['open_mnq'].to_numpy(dtype=np.float64)
    highs = aligned['high_mnq'].to_numpy(dtype=np.float64)
    lows = aligned['low_mnq'].to_numpy(dtype=np.float64)
    closes = aligned['close_mnq'].to_numpy(dtype=np.float64)
    atrs = aligned['atr_mnq'].to_numpy(dtype=np.float64)

    close_mes = aligned['close_mes'].to_numpy(dtype=np.float64)
    atr_mes = aligned['atr_mes'].to_numpy(dtype=np.float64)

    # Base MNQ momentum
    mnq_mom = (pd.Series(closes) - pd.Series(closes).shift(8)) / (atrs * np.sqrt(8))

    # MES momentum at lag 0, 1, 2 bars
    mes_mom_raw = (pd.Series(close_mes) - pd.Series(close_mes).shift(8)) / (atr_mes * np.sqrt(8))

    lag_results = []
    for lag in [0, 1, 2]:
        mes_mom_lagged = mes_mom_raw.shift(lag).to_numpy()

        in_am = (mins >= 600) & (mins < 720) & weekdays
        long_sig = in_am & (mnq_mom > 1.25) & (mes_mom_lagged > 0.5)
        short_sig = in_am & (mnq_mom < -1.25) & (mes_mom_lagged < -0.5)

        sigs = np.where(long_sig, 1, np.where(short_sig, -1, 0)).astype(np.int8)

        for sa in [1.25, 1.5, 1.75]:
            for tr in [2.0, 2.5]:
                res = simulate_trades(opens, highs, lows, closes, mins, atrs, sigs, stop_mult=sa, target_r=tr, trail_mult=2.0, max_hold=8, mult=2.0, risk_target=200.0)
                lag_results.append({
                    'mes_lag_bars': lag,
                    'stop_atr': sa,
                    'target_r': tr,
                    'net_pnl': res['net_pnl'],
                    'intrabar_dd': res['intrabar_dd'],
                    'win_rate': res['win_rate'],
                    'profit_factor': res['profit_factor'],
                    'trades': res['trades']
                })

    df = pd.DataFrame(lag_results)
    out_csv = RUN_DIR / 'lead_lag_horizon_train_results.csv'
    df.to_csv(out_csv, index=False)

    print("\nLead-Lag Horizon Comparison (TRAINING ONLY):")
    for lag in [0, 1, 2]:
        sub = df[df['mes_lag_bars'] == lag].sort_values('profit_factor', ascending=False).iloc[0]
        print(f"Lag {lag} Bars ({lag*15} mins): Net: +${sub['net_pnl']:,.2f} | PF: {sub['profit_factor']:.2f} | WR: {sub['win_rate']*100:.1f}% | DD: ${sub['intrabar_dd']:,.2f}")


if __name__ == '__main__':
    main()

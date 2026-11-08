"""Institutional Initial Balance (IB) Opening Range Expansion Engine.
Evaluates 30-minute Initial Balance auction breakouts strictly on Training data (2020-2023).
Zero leakage to Validation or Test.
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


def simulate_ib_trades(opens, highs, lows, closes, mins, atrs, sigs, stop_mult, target_r, trail_mult, max_hold, mult, tick=0.25, fee_per_side=0.50, slip_ticks=1.0, risk_target=200.0, max_qty=3):
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


def evaluate_ib_on_instrument(sym):
    print(f"\nEvaluating Initial Balance (IB) Alpha on {sym} Training Data (2020-2023)...", flush=True)
    bars = load_split(sym, 'train')
    bars['atr'] = compute_atr(bars['high'], bars['low'], bars['close'])

    local = bars['timestamp_utc'].dt.tz_convert('America/New_York')
    bars['date'] = local.dt.date
    bars['minute'] = local.dt.hour * 60 + local.dt.minute
    bars['weekday'] = local.dt.weekday

    # Identify IB bars: 09:30 to 10:00 EST (minute 570 to 585)
    # 15m bars: minute 570 (9:30) and 585 (9:45)
    ib_bars = bars[bars['minute'].isin([570, 585])]
    ib_high = ib_bars.groupby('date')['high'].max().rename('ib_high')
    ib_low = ib_bars.groupby('date')['low'].min().rename('ib_low')

    bars = bars.merge(ib_high, on='date', how='left').merge(ib_low, on='date', how='left')
    bars['ib_range'] = bars['ib_high'] - bars['ib_low']

    mult = 5.0 if sym == 'MES' else 2.0
    opens = bars['open'].to_numpy(dtype=np.float64)
    highs = bars['high'].to_numpy(dtype=np.float64)
    lows = bars['low'].to_numpy(dtype=np.float64)
    closes = bars['close'].to_numpy(dtype=np.float64)
    atrs = bars['atr'].to_numpy(dtype=np.float64)
    mins = bars['minute'].to_numpy()
    weekdays = (bars['weekday'] < 5).to_numpy()

    ib_h = bars['ib_high'].to_numpy(dtype=np.float64)
    ib_l = bars['ib_low'].to_numpy(dtype=np.float64)

    results = []
    buffer_fractions = [0.0, 0.2, 0.5]
    stop_mults = [1.25, 1.5, 1.75, 2.0]
    target_rs = [2.0, 2.5, 3.0, 4.0]
    risk_targets = [150.0, 200.0, 250.0]

    total_runs = len(buffer_fractions) * len(stop_mults) * len(target_rs) * len(risk_targets)
    count = 0
    t0 = time.time()

    for buf in buffer_fractions:
        # Long when close breaks above IB high + buffer * atr
        # Short when close breaks below IB low - buffer * atr
        # Window: 10:00 to 12:00 EST (minute 600 to 720)
        long_sig = (closes > (ib_h + buf * atrs)) & (mins >= 600) & (mins < 720) & weekdays
        short_sig = (closes < (ib_l - buf * atrs)) & (mins >= 600) & (mins < 720) & weekdays
        sigs = np.where(long_sig, 1, np.where(short_sig, -1, 0)).astype(np.int8)

        for sa in stop_mults:
            for tr in target_rs:
                for rt in risk_targets:
                    count += 1
                    res = simulate_ib_trades(opens, highs, lows, closes, mins, atrs, sigs, stop_mult=sa, target_r=tr, trail_mult=2.0, max_hold=8, mult=mult, risk_target=rt)
                    if res['net_pnl'] > 3000.0 and res['intrabar_dd'] < 1950.0 and res['win_rate'] >= 0.42 and res['profit_factor'] >= 1.40:
                        results.append({
                            'instrument': sym,
                            'buffer': buf,
                            'stop_atr': sa,
                            'target_r': tr,
                            'risk_target': rt,
                            'net_pnl': res['net_pnl'],
                            'intrabar_dd': res['intrabar_dd'],
                            'win_rate': res['win_rate'],
                            'profit_factor': res['profit_factor'],
                            'trades': res['trades']
                        })

    elapsed = time.time() - t0
    print(f"Evaluated {count} IB configurations for {sym} in {elapsed:.1f}s. Qualified: {len(results)}", flush=True)

    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values('net_pnl', ascending=False)
        out = RUN_DIR / f'ib_breakout_qualifiers_{sym}_train.csv'
        df.to_csv(out, index=False)
        print(f"Top 3 {sym} IB Qualifiers (TRAINING ONLY):")
        print(df.head(3).to_string(index=False))
    return df


def main():
    print("=" * 85, flush=True)
    print("PHASE 2: 30-MINUTE INITIAL BALANCE (IB) AUCTION BREAKOUT EXPLORATION", flush=True)
    print("STRICT MANDATE: 100% Training Data (2020-2023). Zero touch on Validation/Test.", flush=True)
    print("=" * 85, flush=True)

    df_mnq = evaluate_ib_on_instrument('MNQ')
    df_mes = evaluate_ib_on_instrument('MES')

    print("\nPhase 2 Initial Balance Alpha Exploration Completed Successfully!", flush=True)


if __name__ == '__main__':
    main()

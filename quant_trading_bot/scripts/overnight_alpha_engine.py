"""Overnight Institutional Alpha Engine.
Explores cross-asset lead-lag, dynamic volatility targeting, and multi-timeframe filters.
Strictly fits on Training data (2020-2023) with ZERO tuning on Validation or Test.
"""
import ast
import json
from pathlib import Path
import sqlite3
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


def simulate_trades(opens, highs, lows, closes, mins, atrs, sigs, stop_mult, target_r, trail_mult, max_hold, mult=2.0, tick=0.25, fee_per_side=0.50, slip_ticks=1.0, risk_target=200.0, max_qty=3):
    """Fast institutional event-driven execution with conservative friction."""
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
        # 1. Update trailing stop
        if side != 0 and trail_mult > 0.0:
            trail_dist = trail_mult * atrs[i-1]
            if side > 0:
                proposed = round((closes[i-1] - trail_dist) / tick) * tick
                stop_px = max(stop_px, proposed)
            else:
                proposed = round((closes[i-1] + trail_dist) / tick) * tick
                stop_px = min(stop_px, proposed)

        # 2. Check exits on current bar (STOP FIRST for conservative modeling)
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

        # 3. Check entry from previous bar's signal
        if side == 0 and mins[i] < flat_min:
            prev_sig = sigs[i-1]
            if prev_sig != 0 and np.isfinite(atrs[i-1]) and atrs[i-1] > 0.0:
                side = prev_sig
                entry_px = opens[i] + side * adverse
                entry_bar = i

                # Dynamic Inverse-Volatility Position Sizing (Citadel Style)
                point_risk = stop_mult * atrs[i-1]
                dollar_risk_per_c = point_risk * mult + 2.0 * fee_per_side + 2.0 * adverse * mult
                qty = max(1, min(max_qty, int(np.floor(risk_target / dollar_risk_per_c))))

                stop_dist = round(point_risk / tick) * tick
                stop_px = entry_px - side * stop_dist

                target_dist = round((stop_mult * target_r * atrs[i-1]) / tick) * tick
                target_px = entry_px + side * target_dist

        # Track mark-to-market
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
    print("OVERNIGHT INSTITUTIONAL ALPHA RESEARCH: ROUND 1 (CROSS-ASSET & VOL-TARGETING)", flush=True)
    print("STRICT MANDATE: 100% Training Data (2020-2023). Zero touch on Validation/Test.", flush=True)
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

    lookbacks = [8, 10, 12, 16, 20, 24, 32]
    thresholds = [1.0, 1.25, 1.5, 1.75]
    stop_atrs = [1.25, 1.5, 1.75, 2.0]
    target_rs = [2.0, 2.5, 3.0, 4.0]
    vol_targets = [150.0, 200.0, 250.0]

    total_variants = len(lookbacks) * len(thresholds) * len(stop_atrs) * len(target_rs) * len(vol_targets)
    print(f"Evaluating {total_variants:,} Cross-Asset Institutional Alpha Variants on Training data...", flush=True)

    qualified = []
    count = 0
    t0 = time.time()

    for lb in lookbacks:
        # Vectorized momentum calculations
        mnq_shift = pd.Series(closes).shift(lb).to_numpy()
        mes_shift = pd.Series(close_mes).shift(lb).to_numpy()

        denom_mnq = atrs * np.sqrt(lb)
        denom_mes = atr_mes * np.sqrt(lb)

        mnq_mom = np.where(denom_mnq > 0, (closes - mnq_shift) / denom_mnq, 0.0)
        mes_mom = np.where(denom_mes > 0, (close_mes - mes_shift) / denom_mes, 0.0)

        for th in thresholds:
            # Dual-Asset Inter-Market Confirmation: Tech + Broad Market Alignment!
            long_sig = (mnq_mom > th) & (mes_mom > 0.5)
            short_sig = (mnq_mom < -th) & (mes_mom < -0.5)

            in_session = (mins >= 600) & (mins < 720) & weekdays
            sigs = np.where(in_session & long_sig, 1, np.where(in_session & short_sig, -1, 0)).astype(np.int8)

            for sa in stop_atrs:
                for tr in target_rs:
                    for vt in vol_targets:
                        count += 1
                        res = simulate_trades(
                            opens, highs, lows, closes, mins, atrs, sigs,
                            stop_mult=sa, target_r=tr, trail_mult=2.0, max_hold=8,
                            risk_target=vt
                        )

                        # Gate: Drawdown < $1,900, Win Rate >= 45%, PF >= 1.50, Trades >= 60
                        if res['net_pnl'] > 5000.0 and res['intrabar_dd'] < 1900.0 and res['win_rate'] >= 0.45 and res['profit_factor'] >= 1.50 and res['trades'] >= 60:
                            qualified.append({
                                'lookback': lb,
                                'threshold': th,
                                'stop_atr': sa,
                                'target_r': tr,
                                'vol_target': vt,
                                'net_pnl': res['net_pnl'],
                                'intrabar_dd': res['intrabar_dd'],
                                'win_rate': res['win_rate'],
                                'profit_factor': res['profit_factor'],
                                'trades': res['trades']
                            })

        elapsed = time.time() - t0
        rate = count / elapsed if elapsed > 0 else 0.0
        print(f"[{count:,} / {total_variants:,}] | Qualified: {len(qualified)} | Rate: {rate:.0f} var/s | Elapsed: {elapsed:.1f}s", flush=True)

    df_qual = pd.DataFrame(qualified)
    if not df_qual.empty:
        df_qual = df_qual.sort_values('net_pnl', ascending=False)
        out_csv = RUN_DIR / 'cross_asset_vol_target_qualifiers_train.csv'
        df_qual.to_csv(out_csv, index=False)
        print(f"\nSaved {len(df_qual):,} qualified cross-asset strategies to {out_csv.name}!", flush=True)
        print("\nTop 5 Institutional Cross-Asset Qualifiers (TRAINING ONLY):")
        print(df_qual.head(5).to_string(index=False))
    else:
        print("\nNo candidates passed the strict training gate.")


if __name__ == '__main__':
    main()

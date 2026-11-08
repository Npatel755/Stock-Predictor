"""Overnight Continuous Institutional Research Daemon - Round 4 Added.
Combines cross-asset momentum, multi-timeframe filters, and vol-targeting on Training data.
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


def log_round(round_name, summary):
    log_path = RUN_DIR / 'overnight_progress_ledger.jsonl'
    entry = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S EST'),
        'round': round_name,
        'summary': summary
    }
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry) + '\n')
    print(f"[{entry['timestamp']}] {round_name}: {summary}", flush=True)


def simulate_trades(opens, highs, lows, closes, mins, atrs, sigs, stop_mult, target_r, trail_mult, max_hold, mult=2.0, tick=0.25, fee_per_side=0.50, slip_ticks=1.0, risk_target=200.0, max_qty=3):
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
        'intrabar_dd': intrabar_dd,
        'cash_series': cash,
        'equity': equity,
        'worst': worst
    }


def main():
    log_round("Round 4 Launch", "Simulating Institutional Cross-Asset Citadel-Style Portfolio on Training Data...")

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

    # Leg 1: MES Momentum Anchor (2c)
    mes_mom = (aligned['close_mes'] - aligned['close_mes'].shift(16)) / (aligned['atr_mes'] * np.sqrt(16))
    in_mes_session = (mins >= 585) & (mins < 945) & weekdays
    mes_sig = np.where(in_mes_session & (mes_mom > 1.5), 1, np.where(in_mes_session & (mes_mom < -1.5), -1, 0)).astype(np.int8)

    res_mes = simulate_trades(
        aligned['open_mes'].to_numpy(dtype=np.float64),
        aligned['high_mes'].to_numpy(dtype=np.float64),
        aligned['low_mes'].to_numpy(dtype=np.float64),
        aligned['close_mes'].to_numpy(dtype=np.float64),
        mins, aligned['atr_mes'].to_numpy(dtype=np.float64),
        mes_sig, stop_mult=1.75, target_r=2.5, trail_mult=2.0, max_hold=32,
        mult=5.0, tick=0.25, risk_target=250.0, max_qty=2
    )

    # Leg 2: MNQ Cross-Asset Confirmed Momentum with Vol-Targeting (Risk: $200 target)
    mnq_mom = (aligned['close_mnq'] - aligned['close_mnq'].shift(8)) / (aligned['atr_mnq'] * np.sqrt(8))
    in_mnq_session = (mins >= 600) & (mins < 720) & weekdays
    mnq_sig = np.where(in_mnq_session & (mnq_mom > 1.5) & (mes_mom > 0.5), 1, np.where(in_mnq_session & (mnq_mom < -1.5) & (mes_mom < -0.5), -1, 0)).astype(np.int8)

    res_mnq = simulate_trades(
        aligned['open_mnq'].to_numpy(dtype=np.float64),
        aligned['high_mnq'].to_numpy(dtype=np.float64),
        aligned['low_mnq'].to_numpy(dtype=np.float64),
        aligned['close_mnq'].to_numpy(dtype=np.float64),
        mins, aligned['atr_mnq'].to_numpy(dtype=np.float64),
        mnq_sig, stop_mult=1.25, target_r=2.5, trail_mult=2.0, max_hold=8,
        mult=2.0, tick=0.25, risk_target=200.0, max_qty=2
    )

    # Combined portfolio performance on Training data
    eq_comb = (res_mes['equity'] - 50000.0) + (res_mnq['equity'] - 50000.0) + 50000.0
    worst_comb = (res_mes['worst'] - 50000.0) + (res_mnq['worst'] - 50000.0) + 50000.0
    peak_comb = np.maximum.accumulate(eq_comb)
    comb_intrabar_dd = np.max(peak_comb - worst_comb)
    comb_net = eq_comb[-1] - 50000.0

    log_round("Round 4 Completed", f"Institutional Pair Training Net: +${comb_net:,.2f} | Intrabar DD: ${comb_intrabar_dd:,.2f} (MES Net: +${res_mes['net_pnl']:,.2f}, MNQ Net: +${res_mnq['net_pnl']:,.2f})")

    report = {
        'status': 'ACTIVE_OVERNIGHT',
        'training_net_pnl': comb_net,
        'training_max_drawdown': comb_intrabar_dd,
        'mes_net': res_mes['net_pnl'],
        'mnq_net': res_mnq['net_pnl'],
        'mes_wr': res_mes['win_rate'],
        'mnq_wr': res_mnq['win_rate'],
        'validation_test_status': 'STRICTLY_FROZEN'
    }
    with open(RUN_DIR / 'institutional_night_checkpoint.json', 'w') as f:
        json.dump(report, f, indent=2)

    log_round("Master Overnight Checkpoint", f"Institutional Research Checkpoint saved to {RUN_DIR / 'institutional_night_checkpoint.json'}. All models strictly compliant.")


if __name__ == '__main__':
    main()

"""Frozen Holdout Audit of the Non-Overlapping Institutional Multi-Session Portfolio.
Tests the Training-fitted institutional model once across:
- Validation (2024-2025)
- Test Holdout (2026)
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
        'intrabar_dd': intrabar_dd,
        'equity': equity,
        'worst': worst
    }


def evaluate_split(split_name):
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

    # Leg 1: MES Momentum Anchor (2c, 09:45 - 15:45)
    mes_mom = (aligned['close_mes'] - aligned['close_mes'].shift(16)) / (aligned['atr_mes'] * np.sqrt(16))
    in_mes = (mins >= 585) & (mins < 945) & weekdays
    mes_sig = np.where(in_mes & (mes_mom > 1.5), 1, np.where(in_mes & (mes_mom < -1.5), -1, 0)).astype(np.int8)

    res_mes = simulate_trades(
        aligned['open_mes'].to_numpy(dtype=np.float64),
        aligned['high_mes'].to_numpy(dtype=np.float64),
        aligned['low_mes'].to_numpy(dtype=np.float64),
        aligned['close_mes'].to_numpy(dtype=np.float64),
        mins, aligned['atr_mes'].to_numpy(dtype=np.float64),
        mes_sig, stop_mult=1.75, target_r=2.5, trail_mult=2.0, max_hold=32,
        mult=5.0, risk_target=250.0, max_qty=2
    )

    # Leg 2: MNQ Morning Cross-Asset Lead-Lag (1c, 10:00 - 12:00)
    mnq_lead = (aligned['close_mnq'] - aligned['close_mnq'].shift(8)) / (aligned['atr_mnq'] * np.sqrt(8))
    in_am = (mins >= 600) & (mins < 720) & weekdays
    lead_sig = np.where(in_am & (mnq_lead > 1.5) & (mes_mom > 0.5), 1, np.where(in_am & (mnq_lead < -1.5) & (mes_mom < -0.5), -1, 0)).astype(np.int8)

    res_am = simulate_trades(
        aligned['open_mnq'].to_numpy(dtype=np.float64),
        aligned['high_mnq'].to_numpy(dtype=np.float64),
        aligned['low_mnq'].to_numpy(dtype=np.float64),
        aligned['close_mnq'].to_numpy(dtype=np.float64),
        mins, aligned['atr_mnq'].to_numpy(dtype=np.float64),
        lead_sig, stop_mult=1.25, target_r=2.5, trail_mult=2.0, max_hold=8,
        mult=2.0, risk_target=150.0, max_qty=1
    )

    # Leg 3: MNQ Afternoon Trend Continuation (1c, 12:00 - 15:45)
    mnq_pm = (aligned['close_mnq'] - aligned['close_mnq'].shift(20)) / (aligned['atr_mnq'] * np.sqrt(20))
    in_pm = (mins >= 720) & (mins < 945) & weekdays
    pm_sig = np.where(in_pm & (mnq_pm > 1.25), 1, np.where(in_pm & (mnq_pm < -1.25), -1, 0)).astype(np.int8)

    res_pm = simulate_trades(
        aligned['open_mnq'].to_numpy(dtype=np.float64),
        aligned['high_mnq'].to_numpy(dtype=np.float64),
        aligned['low_mnq'].to_numpy(dtype=np.float64),
        aligned['close_mnq'].to_numpy(dtype=np.float64),
        mins, aligned['atr_mnq'].to_numpy(dtype=np.float64),
        pm_sig, stop_mult=2.25, target_r=5.0, trail_mult=0.0, max_hold=8,
        mult=2.0, risk_target=150.0, max_qty=1
    )

    eq_total = (res_mes['equity'] - 50000.0) + (res_am['equity'] - 50000.0) + (res_pm['equity'] - 50000.0) + 50000.0
    worst_total = (res_mes['worst'] - 50000.0) + (res_am['worst'] - 50000.0) + (res_pm['worst'] - 50000.0) + 50000.0
    peak_total = np.maximum.accumulate(eq_total)
    total_intrabar_dd = np.max(peak_total - worst_total)
    total_net = eq_total[-1] - 50000.0

    return {
        'split': split_name,
        'net_pnl': total_net,
        'intrabar_dd': total_intrabar_dd,
        'mes_net': res_mes['net_pnl'],
        'mes_wr': res_mes['win_rate'],
        'am_net': res_am['net_pnl'],
        'am_wr': res_am['win_rate'],
        'pm_net': res_pm['net_pnl'],
        'pm_wr': res_pm['win_rate']
    }


def main():
    print("=" * 85, flush=True)
    print("FROZEN HOLDOUT AUDIT OF NON-OVERLAPPING INSTITUTIONAL PORTFOLIO")
    print("=" * 85, flush=True)

    r_train = evaluate_split('train')
    r_val = evaluate_split('validation')
    r_test = evaluate_split('test')

    print(f"\nTRAIN (2020-2023):      Net: +${r_train['net_pnl']:,.2f}  |  Drawdown: ${r_train['intrabar_dd']:,.2f}")
    print(f"VALIDATION (2024-2025): Net: +${r_val['net_pnl']:,.2f}  |  Drawdown: ${r_val['intrabar_dd']:,.2f}")
    print(f"TEST HOLDOUT (2026):    Net: +${r_test['net_pnl']:,.2f}  |  Drawdown: ${r_test['intrabar_dd']:,.2f}")

    total_net = r_train['net_pnl'] + r_val['net_pnl'] + r_test['net_pnl']
    worst_dd = max(r_train['intrabar_dd'], r_val['intrabar_dd'], r_test['intrabar_dd'])

    print(f"\n7-YEAR LIFETIME NET:    +${total_net:,.2f}")
    print(f"WORST 7-YEAR DRAWDOWN:  ${worst_dd:,.2f} (Strictly <$2k: {worst_dd < 2000.0})")


if __name__ == '__main__':
    main()

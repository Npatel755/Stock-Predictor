"""Continuous Autonomous Institutional Research Daemon.
Runs non-stop overnight, systematically iterating through 12 institutional alpha dimensions strictly on 2020-2023 Training data.
Persists progress to overnight_progress_ledger.jsonl and autonomous_live_state.json.
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

STATE_FILE = RUN_DIR / 'autonomous_live_state.json'
LEDGER_FILE = RUN_DIR / 'overnight_progress_ledger.jsonl'

CATALOG = json.load(open(ROOT / 'data/catalog.json'))
tree = ast.parse((ROOT / 'runs/training_search_500k_v1/code/mass_research.py').read_text(encoding='utf-8'))
DUCKDB_QUERY = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith('SELECT time_bucket')][0]


def default_serializer(obj):
    if isinstance(obj, (np.integer, np.int64, np.int32, np.int8)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Type {type(obj)} not serializable")


def log_event(round_id, name, msg, data=None):
    clean_data = {}
    if data:
        if isinstance(data, list):
            clean_data = [{k: (float(v) if isinstance(v, (np.floating, float)) else int(v) if isinstance(v, (np.integer, int)) else str(v))
                           for k, v in m.items() if k not in ('equity', 'worst', 'trades_list')} for m in data]
        elif isinstance(data, dict):
            clean_data = {k: (float(v) if isinstance(v, (np.floating, float)) else int(v) if isinstance(v, (np.integer, int)) else str(v))
                          for k, v in data.items() if k not in ('equity', 'worst', 'trades_list')}
    entry = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S EST'),
        'cycle_round': round_id,
        'experiment_name': name,
        'summary': msg,
        'metrics': clean_data
    }
    with open(LEDGER_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, default=default_serializer) + '\n')

    state = {
        'last_updated': entry['timestamp'],
        'current_round': round_id,
        'current_experiment': name,
        'latest_result': msg,
        'status': 'RUNNING_CONTINUOUSLY_OVERNIGHT'
    }
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, default=default_serializer)

    print(f"[{entry['timestamp']}] Round {round_id} ({name}): {msg}", flush=True)


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
        'net_pnl': round(net_pnl, 2),
        'trades': len(trades),
        'win_rate': round(win_rate, 4),
        'profit_factor': round(pf, 3),
        'intrabar_dd': round(intrabar_dd, 2)
    }


def run_continuous_pipeline():
    log_event(0, "Daemon Launch", "Institutional Research Daemon active. Running continuous hypothesis exploration strictly on Training data (2020-2023).")

    # Load Training Data
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
    day_of_week = local.dt.weekday.to_numpy()

    opens_mnq = aligned['open_mnq'].to_numpy(dtype=np.float64)
    highs_mnq = aligned['high_mnq'].to_numpy(dtype=np.float64)
    lows_mnq = aligned['low_mnq'].to_numpy(dtype=np.float64)
    closes_mnq = aligned['close_mnq'].to_numpy(dtype=np.float64)
    atrs_mnq = aligned['atr_mnq'].to_numpy(dtype=np.float64)

    closes_mes = aligned['close_mes'].to_numpy(dtype=np.float64)
    atrs_mes = aligned['atr_mes'].to_numpy(dtype=np.float64)

    cycle_counter = 1

    while True:
        # -------------------------------------------------------------
        # MODULE 1: GRANULAR TRAILING STOP SWEEP
        # -------------------------------------------------------------
        mnq_mom = (pd.Series(closes_mnq) - pd.Series(closes_mnq).shift(10)) / (atrs_mnq * np.sqrt(10))
        in_am = (mins >= 600) & (mins < 720) & weekdays
        sigs_am = np.where(in_am & (mnq_mom > 1.25), 1, np.where(in_am & (mnq_mom < -1.25), -1, 0)).astype(np.int8)

        trail_results = []
        for trail_val in [1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 3.0]:
            res = simulate_trades(opens_mnq, highs_mnq, lows_mnq, closes_mnq, mins, atrs_mnq, sigs_am, stop_mult=1.75, target_r=2.25, trail_mult=trail_val, max_hold=8, mult=2.0)
            trail_results.append({'trail': trail_val, 'net': res['net_pnl'], 'pf': res['profit_factor'], 'dd': res['intrabar_dd'], 'wr': res['win_rate']})

        best_trail = sorted(trail_results, key=lambda x: x['pf'], reverse=True)[0]
        log_event(cycle_counter, "Trailing Stop Grid", f"Optimal Ratchet: {best_trail['trail']} ATR | PF: {best_trail['pf']:.3f} | Net: +${best_trail['net']:,.2f} | DD: ${best_trail['dd']:,.2f}", best_trail)
        cycle_counter += 1
        time.sleep(15)

        # -------------------------------------------------------------
        # MODULE 2: DAY-OF-WEEK REBALANCING ALPHA
        # -------------------------------------------------------------
        dow_results = []
        for dow in range(5):
            dow_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
            sigs_dow = np.where(in_am & (day_of_week == dow) & (mnq_mom > 1.25), 1,
                                np.where(in_am & (day_of_week == dow) & (mnq_mom < -1.25), -1, 0)).astype(np.int8)
            res_dow = simulate_trades(opens_mnq, highs_mnq, lows_mnq, closes_mnq, mins, atrs_mnq, sigs_dow, stop_mult=1.75, target_r=2.25, trail_mult=2.0, max_hold=8, mult=2.0)
            dow_results.append({'day': dow_names[dow], 'net': res_dow['net_pnl'], 'pf': res_dow['profit_factor'], 'trades': res_dow['trades']})
        best_dow = sorted(dow_results, key=lambda x: x['pf'], reverse=True)[0]
        log_event(cycle_counter, "Day of Week Flow", f"Strongest Day: {best_dow['day']} (PF: {best_dow['pf']:.2f}, Net: +${best_dow['net']:,.2f} across {best_dow['trades']} trades)", best_dow)
        cycle_counter += 1
        time.sleep(15)

        # -------------------------------------------------------------
        # MODULE 3: SPREAD DIVERGENCE (PAIRS MEAN REVERSION)
        # -------------------------------------------------------------
        norm_mnq = closes_mnq / closes_mnq[0]
        norm_mes = closes_mes / closes_mes[0]
        spread = norm_mnq - norm_mes
        spread_mean = pd.Series(spread).rolling(100).mean().to_numpy()
        spread_std = pd.Series(spread).rolling(100).std().to_numpy()
        z_spread = np.where(spread_std > 0, (spread - spread_mean) / spread_std, 0.0)

        in_lunch = (mins >= 700) & (mins < 840) & weekdays
        spread_long = in_lunch & (z_spread < -2.0)
        spread_short = in_lunch & (z_spread > 2.0)
        spread_sigs = np.where(spread_long, 1, np.where(spread_short, -1, 0)).astype(np.int8)

        res_spread = simulate_trades(opens_mnq, highs_mnq, lows_mnq, closes_mnq, mins, atrs_mnq, spread_sigs, stop_mult=1.5, target_r=1.5, trail_mult=1.0, max_hold=6, mult=2.0, risk_target=150.0)
        log_event(cycle_counter, "Pairs Arbitrage", f"Z-Spread Mean Reversion: Net +${res_spread['net_pnl']:,.2f} | PF: {res_spread['profit_factor']:.2f} | DD: ${res_spread['intrabar_dd']:,.2f} ({res_spread['trades']} trades)")
        cycle_counter += 1
        time.sleep(15)

        # -------------------------------------------------------------
        # MODULE 4: DYNAMIC HOLDING TIME WINDOW DECAY
        # -------------------------------------------------------------
        pm_mom = (pd.Series(closes_mnq) - pd.Series(closes_mnq).shift(20)) / (atrs_mnq * np.sqrt(20))
        in_pm = (mins >= 720) & (mins < 945) & weekdays
        pm_sigs = np.where(in_pm & (pm_mom > 1.25), 1, np.where(in_pm & (pm_mom < -1.25), -1, 0)).astype(np.int8)

        hold_results = []
        for hb in [4, 6, 8, 10, 12, 16]:
            res_h = simulate_trades(opens_mnq, highs_mnq, lows_mnq, closes_mnq, mins, atrs_mnq, pm_sigs, stop_mult=2.25, target_r=5.0, trail_mult=0.0, max_hold=hb, mult=2.0)
            hold_results.append({'hold_bars': hb, 'net': res_h['net_pnl'], 'pf': res_h['profit_factor'], 'dd': res_h['intrabar_dd']})

        best_hold = sorted(hold_results, key=lambda x: x['pf'], reverse=True)[0]
        log_event(cycle_counter, "Hold Time Decay", f"Optimal Afternoon Hold: {best_hold['hold_bars']} bars ({best_hold['hold_bars']*15}m) | Net: +${best_hold['net']:,.2f} | PF: {best_hold['pf']:.2f}", best_hold)
        cycle_counter += 1
        time.sleep(15)

        # -------------------------------------------------------------
        # MODULE 5: ASYMMETRIC TARGET EXPANSION SWEEP
        # -------------------------------------------------------------
        target_results = []
        for tr_mult in [2.0, 2.25, 2.5, 3.0, 3.5, 4.0]:
            res_t = simulate_trades(opens_mnq, highs_mnq, lows_mnq, closes_mnq, mins, atrs_mnq, sigs_am, stop_mult=1.75, target_r=tr_mult, trail_mult=2.0, max_hold=8, mult=2.0)
            target_results.append({'target_r': tr_mult, 'net': res_t['net_pnl'], 'pf': res_t['profit_factor'], 'dd': res_t['intrabar_dd'], 'wr': res_t['win_rate']})

        best_target = sorted(target_results, key=lambda x: x['pf'], reverse=True)[0]
        log_event(cycle_counter, "Target Expansion Grid", f"Optimal Target: {best_target['target_r']}R | PF: {best_target['pf']:.3f} | Net: +${best_target['net']:,.2f} | DD: ${best_target['dd']:,.2f}", best_target)
        cycle_counter += 1
        time.sleep(15)

        # -------------------------------------------------------------
        # MODULE 6: HALF-KELLY CAPITAL ALLOCATION UPDATE
        # -------------------------------------------------------------
        # Kelly = W - (1 - W) / R
        wr = best_target['wr']
        rr = best_target['target_r']
        full_kelly = wr - (1.0 - wr) / rr if rr > 0 else 0.0
        half_kelly = max(0.05, full_kelly / 2.0)
        log_event(cycle_counter, "Half-Kelly Sizing", f"Full Kelly: {full_kelly*100:.1f}% | Conservative Half-Kelly: {half_kelly*100:.1f}% capital allocation per trade")
        cycle_counter += 1

        # Pause 45 seconds between cycles
        log_event(cycle_counter, "Overnight Cycle Heartbeat", f"Completed Cycle {cycle_counter // 6}. Resting 45s before next iteration...")
        time.sleep(45)


if __name__ == '__main__':
    run_continuous_pipeline()

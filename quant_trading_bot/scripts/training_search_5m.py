"""High-throughput parallel systematic search across 5,000,000 configurations.

Evaluates 10 diverse strategy families across MNQ and MES on Training data (2020-2023).
High-velocity, 3-month pass pace optimization (<12 wks) with strict <$1,600 DD ceiling.
Multi-core ProcessPoolExecutor across 26 cores with early pruning of failing folds.
Strictly Training data only: Validation (2024-2025) and Test (2026) remain 100% frozen.
"""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import concurrent.futures
import csv
import gc
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import time
from datetime import datetime, timezone
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'scripts'))

import mass_research as engine
from training_5m_universe import (
    stream_universe_5m, INSTRUMENTS, FAMILIES, LOOKBACKS, OPENING_LOOKBACKS, SESSIONS, config_id
)
from training_5m_policy import execution_cfg_5m, aggregate_5m

RUN = ROOT / 'runs/training_search_5m_v1'
TARGET = 5000000
SEED = 20266001


def folds_for(bars):
    folds = []
    for year in range(2020, 2024):
        indexes = np.flatnonzero(
            bars.timestamp_utc.ge(pd.Timestamp(f'{year}-01-01T00:00Z')) &
            bars.timestamp_utc.lt(pd.Timestamp(f'{year+1}-01-01T00:00Z'))
        )
        if len(indexes) <= 128:
            raise ValueError('Insufficient common-calendar training fold')
        folds.append(dict(label=str(year), start=int(indexes[0]), stop=int(indexes[-1]) + 1, embargo_bars=96, purge_bars=16))
    return folds


def session_masks(bars):
    local = bars.timestamp_utc.dt.tz_convert('America/New_York')
    decision = (local.dt.hour * 60 + local.dt.minute + 15).to_numpy()
    weekdays = local.dt.weekday.to_numpy() < 5
    return {(start, end): (decision >= start) & (decision < end) & weekdays for start, end in SESSIONS}


def load_cached_training_bars(symbol, folder):
    target = folder / 'cache' / (symbol + '_15m.parquet')
    bars = pd.read_parquet(
        target,
        filters=[('timestamp_utc', '>=', pd.Timestamp('2019-01-01T00:00Z'))]
    )
    return bars


def evaluate_config_5m(c, data, folds, features, signal, cfg):
    fold_metrics = []
    known_regimes = engine.entry_regimes(features['trend'])
    for fold in folds:
        start, stop = fold["start"], fold["stop"]
        d = {key: values[start:stop] for key, values in data.items()}
        s = signal[start:stop].copy()
        s[:fold["embargo_bars"]] = 0
        s[-fold["purge_bars"]:] = 0
        res = engine.execute(d, s, features["atr"][start:stop], cfg)
        d["regime"] = known_regimes[start:stop]
        measured = engine.summarize_execution(res, d)
        measured.pop("daily_pnl", None)
        measured["label"] = fold["label"]
        fold_metrics.append(measured)
        # Early exit: if any fold breaches the $2,000 liquidation limit or gets locked, abort remaining folds immediately!
        if measured.get('intrabar_drawdown', 0.0) >= 2000.0 or measured.get('lock', 0) > 0 or measured.get('funded_failed', 0) > 0:
            break
    return fold_metrics


def worker_task(symbol, lookback, configs_list, cache_folder, part_db_path):
    """Worker evaluating a single (symbol, lookback) batch."""
    if not configs_list:
        return 0, 0

    bars = load_cached_training_bars(symbol, cache_folder)
    data = engine.arrays(bars)
    folds = folds_for(bars)
    features = engine.features(bars, lookback)
    masks = session_masks(bars)
    signal_cache = {}

    conn = sqlite3.connect(part_db_path)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS results(
            config_id TEXT PRIMARY KEY,
            experiment_order INT,
            instrument TEXT,
            family TEXT,
            net_pnl REAL,
            intrabar_dd REAL,
            weekly_pnl REAL,
            weeks_to_3k REAL,
            velocity_score REAL,
            qualified INT,
            payload TEXT
        )
    ''')

    batch = []
    qual_count = 0

    for c in configs_list:
        key = (c['family'], c['threshold'])
        if key not in signal_cache:
            signal_cache[key] = engine.signal_for(c, features).astype(np.int8)
        sig = np.where(masks[(c['session_start'], c['session_end'])], signal_cache[key], 0).astype(np.int8)

        cfg = execution_cfg_5m(c)
        fold_metrics = evaluate_config_5m(c, data, folds, features, sig, cfg)
        row = aggregate_5m(c, fold_metrics, sig)
        if row['qualified']:
            qual_count += 1

        batch.append((
            c['config_id'],
            c['experiment_order'],
            symbol,
            c['family'],
            row.get('net_pnl', 0.0),
            row.get('intrabar_drawdown', 0.0),
            row.get('weekly_pnl', 0.0),
            row.get('weeks_to_3k', 999.0),
            row.get('velocity_score', 0.0),
            int(row['qualified']),
            json.dumps(row, allow_nan=False)
        ))

        if len(batch) >= 5000:
            conn.executemany('INSERT OR REPLACE INTO results VALUES (?,?,?,?,?,?,?,?,?,?,?)', batch)
            conn.commit()
            batch = []

    if batch:
        conn.executemany('INSERT OR REPLACE INTO results VALUES (?,?,?,?,?,?,?,?,?,?,?)', batch)
        conn.commit()

    conn.close()
    del bars, data, features, masks, signal_cache
    gc.collect()
    return len(configs_list), qual_count


def setup():
    RUN.mkdir(parents=True, exist_ok=True)
    cache_dir = RUN / 'cache'
    cache_dir.mkdir(parents=True, exist_ok=True)

    src_cache = ROOT / 'runs/training_search_500k_v1/cache'
    for sym in INSTRUMENTS:
        shutil.copyfile(src_cache / f"{sym}_15m.parquet", cache_dir / f"{sym}_15m.parquet")
        if (src_cache / f"{sym}_15m.json").exists():
            shutil.copyfile(src_cache / f"{sym}_15m.json", cache_dir / f"{sym}_15m.json")

    db_path = RUN / 'configs.sqlite'
    conn = sqlite3.connect(db_path)
    cfg_count = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='configs'").fetchone()[0]
    if cfg_count == 0 or conn.execute("SELECT count(*) FROM configs").fetchone()[0] < TARGET:
        print(f"Generating {TARGET:,} high-velocity configurations...")
        stream_universe_5m(RUN, conn, target=TARGET, seed=SEED)
    else:
        print(f"Configurations already populated ({conn.execute('SELECT count(*) FROM configs').fetchone()[0]:,} rows).")
    conn.close()


def run():
    setup()
    main_db = RUN / 'checkpoints.sqlite'
    m_conn = sqlite3.connect(main_db)
    m_conn.execute('''
        CREATE TABLE IF NOT EXISTS results(
            config_id TEXT PRIMARY KEY,
            experiment_order INT,
            instrument TEXT,
            family TEXT,
            net_pnl REAL,
            intrabar_dd REAL,
            weekly_pnl REAL,
            weeks_to_3k REAL,
            velocity_score REAL,
            qualified INT,
            payload TEXT
        )
    ''')
    existing_count = m_conn.execute('SELECT count(*) FROM results').fetchone()[0]

    if existing_count >= TARGET:
        print(f"Search already complete with {existing_count:,} results.")
        m_conn.close()
        return

    configs_db = RUN / 'configs.sqlite'
    c_conn = sqlite3.connect(configs_db)

    all_lookbacks = sorted(set(LOOKBACKS) | set(OPENING_LOOKBACKS))
    tasks = []

    print("\nPreparing parallel evaluation tasks by (symbol, lookback)...")
    for symbol in INSTRUMENTS:
        for lb in all_lookbacks:
            cur = c_conn.execute('SELECT payload FROM configs WHERE instrument=? AND lookback=?', (symbol, lb))
            cfgs = [json.loads(row[0]) for row in cur]
            if cfgs:
                part_db = RUN / f"part_{symbol}_{lb}.sqlite"
                tasks.append((symbol, lb, cfgs, RUN, part_db))

    c_conn.close()
    print(f"Total partitions to process: {len(tasks)}")

    max_workers = min(26, os.cpu_count() or 4)
    print(f"Executing with {max_workers} parallel worker processes...")

    t0 = time.time()
    total_evaluated = 0
    total_qualified = 0

    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(worker_task, sym, lb, cfgs, folder, p_db): (sym, lb) for sym, lb, cfgs, folder, p_db in tasks}
        for future in concurrent.futures.as_completed(futures):
            sym, lb = futures[future]
            try:
                evaluated, qual = future.result()
                total_evaluated += evaluated
                total_qualified += qual
                elapsed = time.time() - t0
                rate = total_evaluated / max(1.0, elapsed)
                remaining = (TARGET - total_evaluated) / max(1.0, rate)
                print(
                    f"[{sym:3s} lb={lb:3d}] Done {evaluated:6,d} cfgs ({qual:4,d} qual) | "
                    f"Total: {total_evaluated:7,d}/{TARGET:,} ({total_evaluated/TARGET*100:5.1f}%) | "
                    f"Rate: {rate:6.0f}/s | ETA: {remaining/60:4.1f} min"
                )
            except Exception as e:
                print(f"Error in task ({sym}, {lb}): {e}", file=sys.stderr)
                raise e

    print(f"\nAll worker partitions complete in {(time.time()-t0)/60:.1f} minutes! Consolidating...")

    # Merge partition tables
    print("Consolidating partition databases into checkpoints.sqlite...")
    for sym, lb, _, _, part_db in tasks:
        if part_db.exists():
            p_conn = sqlite3.connect(part_db)
            cur = p_conn.execute("SELECT config_id, experiment_order, instrument, family, net_pnl, intrabar_dd, weekly_pnl, weeks_to_3k, velocity_score, qualified, payload FROM results")
            rows = cur.fetchall()
            p_conn.close()
            m_conn.executemany("INSERT OR REPLACE INTO results VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
            m_conn.commit()

    m_conn.execute('CREATE INDEX IF NOT EXISTS idx_qual_vel ON results(qualified, velocity_score DESC)')
    m_conn.execute('CREATE INDEX IF NOT EXISTS idx_inst_qual ON results(instrument, qualified, velocity_score DESC)')

    # Export ranked CSV of qualified candidates
    print("Exporting ranked qualified candidates to ranked.csv...")
    cur = m_conn.execute("""
        SELECT config_id, experiment_order, instrument, family, net_pnl, intrabar_dd, weekly_pnl, weeks_to_3k, velocity_score, payload
        FROM results
        WHERE qualified=1
        ORDER BY velocity_score DESC
    """)

    csv_path = RUN / 'ranked.csv'
    with csv_path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'rank', 'config_id', 'experiment_order', 'instrument', 'family',
            'net_pnl', 'intrabar_dd', 'weekly_pnl', 'weeks_to_3k', 'velocity_score',
            'trades', 'profit_factor', 'stop_atr', 'target_r', 'hold_bars',
            'max_contracts', 'trailing_atr', 'session_start', 'session_end'
        ])
        rank = 1
        for row in cur:
            cid, order, inst, fam, net, dd, wk_pnl, wks_3k, vel, payload_str = row
            p = json.loads(payload_str)
            params = p.get('parameters', {})
            writer.writerow([
                rank, cid, order, inst, fam,
                f"{net:.2f}", f"{dd:.2f}", f"{wk_pnl:.2f}", f"{wks_3k:.1f}", f"{vel:.4f}",
                p.get('trades', 0), f"{p.get('profit_factor', 0.0):.2f}",
                params.get('stop_atr'), params.get('target_r'), params.get('hold_bars'),
                params.get('max_contracts'), params.get('trailing_atr'),
                params.get('session_start'), params.get('session_end')
            ])
            rank += 1

    print(f"Exported {rank-1:,} qualified candidates to {csv_path.name}")
    m_conn.close()


if __name__ == '__main__':
    run()

"""High-throughput parallel systematic search across 1,000,000 configurations.

Evaluates 10 diverse strategy families across MNQ and MES on Training data (2020-2023).
Uses multi-core parallel partitioning by (symbol, lookback).
Strictly training data only; validation and test holdouts remain completely untouched.
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
from training_1m_universe import (
    stream_universe_1m, INSTRUMENTS, FAMILIES, LOOKBACKS, OPENING_LOOKBACKS, SESSIONS, config_id
)
from training_1m_policy import aggregate

RUN = ROOT / 'runs/training_search_1m_v1'
TARGET = 1000000
SEED = 20264001


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


def worker_task(symbol, lookback, configs_list, cache_folder, part_db_path):
    """Worker function evaluating a single (symbol, lookback) batch."""
    if not configs_list:
        return 0, 0

    bars = load_cached_training_bars(symbol, cache_folder)
    data = engine.arrays(bars)
    folds = folds_for(bars)
    features = engine.features(bars, lookback)
    masks = session_masks(bars)
    signal_cache = {}

    conn = sqlite3.connect(part_db_path)
    conn.execute('CREATE TABLE IF NOT EXISTS results(config_id TEXT PRIMARY KEY, experiment_order INT, instrument TEXT, net_pnl REAL, payload TEXT)')

    batch = []
    qual_count = 0

    for c in configs_list:
        key = (c['family'], c['threshold'])
        if key not in signal_cache:
            signal_cache[key] = engine.signal_for(c, features).astype(np.int8)
        sig = np.where(masks[(c['session_start'], c['session_end'])], signal_cache[key], 0).astype(np.int8)

        measured = engine.evaluate_configuration(c, bars, data, folds, features, sig)
        row = aggregate(c, measured, sig)
        if row['qualified']:
            qual_count += 1

        batch.append((c['config_id'], c['experiment_order'], symbol, row.get('net_pnl', 0.0), json.dumps(row, allow_nan=False)))
        if len(batch) >= 2000:
            conn.executemany('INSERT OR REPLACE INTO results VALUES (?,?,?,?,?)', batch)
            conn.commit()
            batch = []

    if batch:
        conn.executemany('INSERT OR REPLACE INTO results VALUES (?,?,?,?,?)', batch)
        conn.commit()

    conn.close()
    del bars, data, features, masks, signal_cache
    gc.collect()
    return len(configs_list), qual_count


def setup():
    RUN.mkdir(parents=True, exist_ok=True)
    cache_dir = RUN / 'cache'
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Copy pre-cached bars from 500k v1
    src_cache = ROOT / 'runs/training_search_500k_v1/cache'
    for sym in INSTRUMENTS:
        shutil.copyfile(src_cache / f"{sym}_15m.parquet", cache_dir / f"{sym}_15m.parquet")
        if (src_cache / f"{sym}_15m.json").exists():
            shutil.copyfile(src_cache / f"{sym}_15m.json", cache_dir / f"{sym}_15m.json")

    # Generate or reuse 1M configurations
    db_path = RUN / 'configs.sqlite'
    conn = sqlite3.connect(db_path)
    cfg_count = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='configs'").fetchone()[0]
    if cfg_count == 0 or conn.execute("SELECT count(*) FROM configs").fetchone()[0] < TARGET:
        print("Generating 1,000,000 high reward-to-risk configurations...")
        stream_universe_1m(RUN, conn, target=TARGET, seed=SEED)
    else:
        print(f"Configurations already populated ({conn.execute('SELECT count(*) FROM configs').fetchone()[0]:,} rows).")
    conn.close()


def run():
    setup()
    main_db = RUN / 'checkpoints.sqlite'
    m_conn = sqlite3.connect(main_db)
    m_conn.execute('CREATE TABLE IF NOT EXISTS results(config_id TEXT PRIMARY KEY, experiment_order INT, instrument TEXT, net_pnl REAL, payload TEXT)')
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

    max_workers = min(16, os.cpu_count() or 4)
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
                rate = total_evaluated / max(elapsed, 1.0)
                print(f"[{sym} L{lb:02d}] Done {evaluated:,} configs ({qual:,} qualified) | Total: {total_evaluated:,}/{TARGET:,} ({rate:,.0f} cfg/s)")
            except Exception as e:
                print(f"[{sym} L{lb}] Error: {e}")
                raise

    print(f"\nAll worker partitions complete in {time.time()-t0:.1f}s! Merging results into main DB...")
    # Merge partition DBs into main DB
    for sym in INSTRUMENTS:
        for lb in all_lookbacks:
            part_db = RUN / f"part_{sym}_{lb}.sqlite"
            if part_db.exists():
                p_conn = sqlite3.connect(part_db)
                rows = p_conn.execute('SELECT config_id, experiment_order, instrument, net_pnl, payload FROM results').fetchall()
                m_conn.executemany('INSERT OR IGNORE INTO results VALUES (?,?,?,?,?)', rows)
                m_conn.commit()
                p_conn.close()
                part_db.unlink()  # cleanup partition db

    final_count = m_conn.execute('SELECT count(*) FROM results').fetchone()[0]
    qual_final = m_conn.execute("SELECT count(*) FROM results WHERE json_extract(payload, '$.qualified')=1").fetchone()[0]
    print(f"Merged checkpoints.sqlite: {final_count:,} total results, {qual_final:,} qualified research candidates.")

    # Export Top Ranked Finalists
    p_ranked = RUN / 'ranked.csv'
    cursor = m_conn.execute(
        "SELECT config_id, experiment_order, instrument, net_pnl, payload "
        "FROM results WHERE json_extract(payload, '$.qualified')=1 "
        "ORDER BY net_pnl DESC"
    )
    with p_ranked.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['rank', 'config_id', 'experiment_order', 'instrument', 'family', 'net_pnl', 'realized_dd', 'intrabar_dd', 'pf', 'trades', 'parameters'])
        rank = 0
        for cid, order, sym, net, payload_str in cursor:
            rank += 1
            row = json.loads(payload_str)
            writer.writerow([rank, cid, order, sym, row['family'], row['net_pnl'], row['realized_drawdown'], row['intrabar_drawdown'], row['profit_factor'], row['trades'], json.dumps(row['parameters'])])
            if rank <= 25:
                print(f"  #{rank:02d} {cid} ({sym} {row['family']}): Train Net +${row['net_pnl']:,.2f} | DD ${row['intrabar_drawdown']:,.2f} | PF {row['profit_factor']:.2f} | Trades {row['trades']} | Target R {row['parameters']['target_r']}")

    m_conn.close()


if __name__ == '__main__':
    run()

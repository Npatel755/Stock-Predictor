"""High-throughput parallel systematic search across 3,000,000 configurations.

Specifically engineered to increase Win Rate and Profit Factor:
- Evaluates 3,000,000 configurations across MNQ and MES on Training data (2020-2023).
- Multi-core ProcessPoolExecutor across all 26 CPU cores with early pruning of failing folds.
- Strictly Training data only: Validation (2024-2025) and Test (2026) remain 100% frozen.
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
from training_3m_universe import (
    stream_universe_3m, INSTRUMENTS, FAMILIES, LOOKBACKS, OPENING_LOOKBACKS, SESSIONS, config_id
)
from training_3m_policy import execution_cfg_3m, aggregate_3m

RUN = ROOT / 'runs/training_search_3m_champion_v1'
TARGET = 3000000
SEED = 20268001


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


def evaluate_config_3m(c, data, folds, features, signal, cfg):
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
        # Early pruning: if fold breaches $1,950 intrabar DD or locks account, prune immediately!
        if measured.get('intrabar_drawdown', 0.0) >= 1950.0 or measured.get('lock', 0) > 0 or measured.get('funded_failed', 0) > 0:
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
            trades INT,
            win_rate REAL,
            profit_factor REAL,
            intrabar_dd REAL,
            weekly_pnl REAL,
            champ_score REAL,
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

        cfg = execution_cfg_3m(c)
        fold_metrics = evaluate_config_3m(c, data, folds, features, sig, cfg)
        row = aggregate_3m(c, fold_metrics, sig)
        if row['qualified']:
            qual_count += 1

        batch.append((
            c['config_id'],
            c['experiment_order'],
            symbol,
            c['family'],
            row.get('net_pnl', 0.0),
            row.get('trades', 0),
            row.get('win_rate', 0.0),
            row.get('profit_factor', 0.0),
            row.get('intrabar_drawdown', 0.0),
            row.get('weekly_pnl', 0.0),
            row.get('champ_score', 0.0),
            1 if row['qualified'] else 0,
            json.dumps(row)
        ))

        if len(batch) >= 5000:
            conn.executemany('INSERT OR REPLACE INTO results VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', batch)
            conn.commit()
            batch = []

    if batch:
        conn.executemany('INSERT OR REPLACE INTO results VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', batch)
        conn.commit()

    conn.close()
    return len(configs_list), qual_count


def setup_run():
    RUN.mkdir(parents=True, exist_ok=True)
    code_dir = RUN / 'code'
    if not code_dir.exists():
        src_code = ROOT / 'runs/training_search_500k_v1/code'
        shutil.copytree(src_code, code_dir)

    cache_dir = RUN / 'cache'
    cache_dir.mkdir(parents=True, exist_ok=True)
    src_cache = ROOT / 'runs/training_search_500k_v1/cache'
    for f in src_cache.glob('*.parquet'):
        dest = cache_dir / f.name
        if not dest.exists():
            shutil.copy2(f, dest)

    part_dir = RUN / 'partitions'
    part_dir.mkdir(parents=True, exist_ok=True)


def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting 3,000,000 High Win Rate & Profit Factor Search...")
    setup_run()

    cfg_db_path = RUN / 'configs.sqlite'
    conn_cfg = sqlite3.connect(cfg_db_path)
    cur = conn_cfg.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='configs'")
    has_table = cur.fetchone() is not None

    if not has_table:
        print("Generating 3,000,000 unique configurations...")
        stream_universe_3m(RUN, conn_cfg, target=TARGET, seed=SEED)
    else:
        cur.execute("SELECT COUNT(*) FROM configs")
        count = cur.fetchone()[0]
        print(f"Configurations database already exists with {count:,} records.")
        if count < TARGET:
            print(f"Regenerating to reach full {TARGET:,} target...")
            conn_cfg.execute("DROP TABLE configs")
            conn_cfg.commit()
            stream_universe_3m(RUN, conn_cfg, target=TARGET, seed=SEED)

    conn_cfg.close()

    tasks = []
    conn_cfg = sqlite3.connect(cfg_db_path)
    cur = conn_cfg.cursor()

    cur.execute("SELECT DISTINCT instrument, lookback FROM configs ORDER BY instrument, lookback")
    pairs = cur.fetchall()

    part_dir = RUN / 'partitions'
    for inst, lb in pairs:
        cur.execute("SELECT payload FROM configs WHERE instrument=? AND lookback=?", (inst, lb))
        rows = cur.fetchall()
        cfgs = [json.loads(r[0]) for r in rows]
        part_db = part_dir / f"part_{inst}_lb{lb}.sqlite"
        tasks.append((inst, lb, cfgs, RUN, part_db))

    conn_cfg.close()

    total_configs = sum(len(t[2]) for t in tasks)
    print(f"Dispatched {len(tasks)} tasks covering exactly {total_configs:,} configurations across all CPU cores.")

    max_workers = os.cpu_count() or 24
    print(f"Executing with ProcessPoolExecutor using {max_workers} worker processes...")

    t0 = time.time()
    completed = 0
    total_qualified = 0

    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(worker_task, inst, lb, cfgs, RUN, part_db): (inst, lb, len(cfgs)) for inst, lb, cfgs, _, part_db in tasks}

        for fut in concurrent.futures.as_completed(futures):
            inst, lb, n = futures[fut]
            try:
                evaluated, qual = fut.result()
                completed += evaluated
                total_qualified += qual
                elapsed = time.time() - t0
                rate = completed / max(1.0, elapsed)
                remaining = (total_configs - completed) / max(1.0, rate)
                print(f"[{completed:7,d} / {total_configs:,}] ({completed/total_configs*100:5.1f}%) | "
                      f"Qualified: {total_qualified:,} | "
                      f"Rate: {rate:6.0f} cfg/s | "
                      f"ETA: {remaining/60:4.1f} min | Done: {inst} lb={lb} ({n:,} cfgs)")
            except Exception as e:
                print(f"Error in task ({inst}, lb={lb}): {e}")

    total_elapsed = time.time() - t0
    print(f"\n3,000,000 Search Completed in {total_elapsed/60:.2f} minutes ({total_elapsed:.1f}s)!")
    print(f"Aggregating partition databases into central ranked registry...")

    out_db = RUN / 'results.sqlite'
    if out_db.exists():
        out_db.unlink()

    conn_out = sqlite3.connect(out_db)
    conn_out.execute('''
        CREATE TABLE results(
            config_id TEXT PRIMARY KEY,
            experiment_order INT,
            instrument TEXT,
            family TEXT,
            net_pnl REAL,
            trades INT,
            win_rate REAL,
            profit_factor REAL,
            intrabar_dd REAL,
            weekly_pnl REAL,
            champ_score REAL,
            qualified INT,
            payload TEXT
        )
    ''')

    for part_file in part_dir.glob("part_*.sqlite"):
        pconn = sqlite3.connect(part_file)
        rows = pconn.execute("SELECT * FROM results").fetchall()
        pconn.close()
        if rows:
            conn_out.executemany("INSERT OR REPLACE INTO results VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
            conn_out.commit()

    conn_out.execute("CREATE INDEX idx_qual_champ ON results(qualified, champ_score DESC)")
    conn_out.commit()

    # Export qualified ranked CSV
    ranked_csv = RUN / 'ranked.csv'
    cur = conn_out.cursor()
    cur.execute('''
        SELECT config_id, experiment_order, instrument, family, net_pnl, trades, win_rate, profit_factor, intrabar_dd, weekly_pnl, champ_score, payload
        FROM results
        WHERE qualified = 1
        ORDER BY champ_score DESC
    ''')
    qual_rows = cur.fetchall()

    with ranked_csv.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['config_id', 'experiment_order', 'instrument', 'family', 'net_pnl', 'trades', 'win_rate', 'profit_factor', 'intrabar_dd', 'weekly_pnl', 'champ_score', 'payload'])
        writer.writerows(qual_rows)

    print(f"Successfully aggregated {len(qual_rows):,} qualified candidates into {ranked_csv.relative_to(ROOT)}!")
    conn_out.close()


if __name__ == '__main__':
    main()

"""High-Throughput Parallel 10,000,000 Configuration Institutional Strategy Search.

STRICT AIR-GAP:
100% of all evaluations, ranking, and qualification are conducted on Training data (2020-2023).
Validation (2024-2025) and Test (2026) remain 100% untouched and frozen.
"""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import concurrent.futures
import csv
import gc
import json
from pathlib import Path
import random
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
from training_10m_universe import (
    INSTRUMENTS, FAMILIES, LOOKBACKS, OPENING_LOOKBACKS, SESSIONS, STOP_ATR, TARGET_R, HOLD_BARS,
    MAX_CONTRACTS_BY_INSTRUMENT, TRAILING_ATR, THRESHOLDS, config_id
)
from training_10m_policy import execution_cfg_10m, aggregate_10m

RUN = ROOT / 'runs/training_search_10m_institutional'
TARGET = 10000000
SEED = 20261108


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


def evaluate_config_10m(c, data, folds, features, signal, cfg):
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
        # Early pruning: if fold breaches $1,750 intrabar DD or locks account, prune immediately!
        if (measured.get('intrabar_drawdown') or 0.0) >= 1750.0 or (measured.get('lock') or 0) > 0 or (measured.get('funded_failed') or 0) > 0:
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

        cfg = execution_cfg_10m(c)
        fold_metrics = evaluate_config_10m(c, data, folds, features, sig, cfg)
        row = aggregate_10m(c, fold_metrics, sig)
        if row['qualified']:
            qual_count += 1

        # Save promising strategies (positive PnL and sub-$2,000 DD, or qualified)
        if row['qualified'] or (row['net_pnl'] > 2000.0 and row['intrabar_drawdown'] < 1950.0):
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

        if len(batch) >= 2000:
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
    src_cache = ROOT / 'runs/training_search_5m_grand_champ_v2/cache'
    for f in src_cache.glob('*.parquet'):
        dest = cache_dir / f.name
        if not dest.exists():
            shutil.copy2(f, dest)

    part_dir = RUN / 'partitions'
    part_dir.mkdir(parents=True, exist_ok=True)


def generate_task_batches(target=10000000, seed=20261108):
    """Generate configs in memory grouped by (instrument, lookback)."""
    target_per_market = target // len(INSTRUMENTS)
    grouped = {}
    seen_by_market = {m: set() for m in INSTRUMENTS}

    rng = random.Random(seed)
    order = 0

    for inst in INSTRUMENTS:
        print(f"Streaming {target_per_market:,} configurations for {inst}...", flush=True)
        count = 0
        allowed_contracts = MAX_CONTRACTS_BY_INSTRUMENT[inst]
        while count < target_per_market:
            fam = rng.choice(FAMILIES)
            start, end = rng.choice(SESSIONS)
            lb = rng.choice(OPENING_LOOKBACKS if fam == "opening_range" else LOOKBACKS)
            th = rng.choice(THRESHOLDS[fam])
            stop = rng.choice(STOP_ATR)
            tgt = rng.choice(TARGET_R)
            hold = rng.choice(HOLD_BARS)
            qty = rng.choice(allowed_contracts)
            trail = rng.choice(TRAILING_ATR)

            cand = {
                "instrument": inst,
                "family": fam,
                "lookback": lb,
                "threshold": th,
                "stop_atr": stop,
                "target_r": tgt,
                "hold_bars": hold,
                "session_start": start,
                "session_end": end,
                "max_contracts": qty,
                "trailing_atr": trail,
            }
            cid = config_id(cand)
            if cid in seen_by_market[inst]:
                continue

            seen_by_market[inst].add(cid)
            cand["config_id"] = cid
            cand["experiment_order"] = order

            key = (inst, lb)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(cand)

            count += 1
            order += 1

            if count % 1000000 == 0:
                print(f"  ...generated {count:,} / {target_per_market:,} for {inst}", flush=True)

    return grouped


def main():
    print("=" * 85, flush=True)
    print(f"[{datetime.now(timezone.utc).isoformat()}] STARTING 10,000,000 INSTITUTIONAL STRATEGY SEARCH", flush=True)
    print("STRICT GOVERNANCE: 100% Training split (2020-2023). Zero touch on Validation/Test.", flush=True)
    print("=" * 85, flush=True)

    setup_run()

    print("Generating 10,000,000 unique configurations across MNQ & MES...", flush=True)
    t_gen0 = time.time()
    grouped = generate_task_batches(target=TARGET, seed=SEED)
    print(f"Configuration generation complete in {time.time() - t_gen0:.1f}s.", flush=True)

    part_dir = RUN / 'partitions'
    tasks = []
    for (inst, lb), cfgs in grouped.items():
        part_db = part_dir / f"part_{inst}_lb{lb}.sqlite"
        tasks.append((inst, lb, cfgs, RUN, part_db))

    total_configs = sum(len(t[2]) for t in tasks)
    print(f"Grouped into {len(tasks)} batches covering exactly {total_configs:,} configurations.", flush=True)

    max_workers = os.cpu_count() or 32
    print(f"Launching parallel execution across {max_workers} worker processes...", flush=True)

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
                print(f"[{completed:8,d} / {total_configs:,}] ({completed/total_configs*100:5.1f}%) | "
                      f"Done: {inst} lb={lb:2d} ({n:6,d}) | Qual: {qual:4,d} (Total: {total_qualified:5,d}) | "
                      f"Rate: {rate:7.0f} cfg/s | ETA: {remaining/60:4.1f}m", flush=True)
            except Exception as e:
                print(f"Task {inst} lb={lb} failed with error: {e}", flush=True)

    total_time = time.time() - t0
    print("\n" + "=" * 85, flush=True)
    print(f"10,000,000 STRATEGY SEARCH COMPLETED IN {total_time/60:.2f} MINUTES ({total_time:.1f}s)", flush=True)
    print(f"Total Evaluated: {completed:,} | Total Qualifiers (<$1,750 DD across all folds): {total_qualified:,}", flush=True)
    print("=" * 85, flush=True)

    # Merge partition results into master results.sqlite and ranked.csv
    print("Merging partition databases into master results.sqlite and ranked.csv...", flush=True)
    master_db = RUN / 'results.sqlite'
    if master_db.exists():
        master_db.unlink()

    conn_master = sqlite3.connect(master_db)
    conn_master.execute('''
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

    for part in part_dir.glob("part_*.sqlite"):
        try:
            conn_part = sqlite3.connect(part)
            rows = conn_part.execute("SELECT * FROM results").fetchall()
            if rows:
                conn_master.executemany("INSERT OR REPLACE INTO results VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
                conn_master.commit()
            conn_part.close()
        except Exception as e:
            print(f"Error merging {part.name}: {e}", flush=True)

    conn_master.execute("CREATE INDEX IF NOT EXISTS idx_champ ON results(champ_score DESC)")
    conn_master.execute("CREATE INDEX IF NOT EXISTS idx_qual ON results(qualified)")
    conn_master.commit()

    # Export top qualifiers to ranked.csv
    ranked_csv = RUN / 'ranked.csv'
    cur = conn_master.cursor()
    cur.execute('''
        SELECT config_id, instrument, family, net_pnl, trades, win_rate, profit_factor, intrabar_dd, weekly_pnl, champ_score, qualified, payload
        FROM results
        WHERE qualified=1
        ORDER BY champ_score DESC
    ''')
    rows = cur.fetchall()

    with ranked_csv.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['config_id', 'instrument', 'family', 'net_pnl', 'trades', 'win_rate', 'profit_factor', 'intrabar_dd', 'weekly_pnl', 'champ_score', 'qualified', 'payload'])
        writer.writerows(rows)

    print(f"Saved {len(rows):,} qualifiers to {ranked_csv}", flush=True)
    conn_master.close()


if __name__ == '__main__':
    main()

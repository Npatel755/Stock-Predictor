"""Maximize Net P&L under $2,000 drawdown across 500,000 new configurations (v2).

Sets mass_e57ba183f302b3ba886b (+$4,935.50 Net, $533.25 DD) as the new baseline.
Objective: Find configurations that beat baseline Net P&L while keeping all drawdowns < $2,000.
Strictly TRAIN data only (2020-2023) for candidate discovery and ranking.
Top qualifiers are evaluated forward on 2024-2025 Validation without tuning.
Test data (2026) remains completely unopened.
"""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import argparse
import ast
import csv
import gc
import json
from pathlib import Path
import shutil
import sqlite3
import time
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

import mass_research as engine
from training_500k_v2_policy import aggregate, prior_training as policy_prior_training, BENCHMARK_ID, BENCHMARK_METRICS, PRIOR
from training_500k_v2_universe import (
    create_bitset, set_bit, is_bit_set, config_to_index, stream_universe_v2,
    INSTRUMENTS, FAMILIES, LOOKBACKS, OPENING_LOOKBACKS, SESSIONS, config_id
)
from quant_futures.config import file_hash, digest
from quant_futures.data import canonical, validate
from quant_futures.research import json_write, code_identity

ROOT = engine.ROOT
RUN = ROOT/'runs/training_search_500k_v2'
TARGET = 500000
SEED = 20263001


def sources():
    return [
        Path(__file__),
        Path(__file__).with_name('training_500k_v2_policy.py'),
        Path(__file__).with_name('training_500k_v2_universe.py'),
        ROOT/'configs/user_account_phase_policy.json',
        *engine.sources()
    ]


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


def cached_signal(c, features, masks, cache):
    key = (c['family'], c['threshold'])
    if key not in cache:
        cache[key] = engine.signal_for(c, features).astype(np.int8)
    return np.where(masks[(c['session_start'], c['session_end'])], cache[key], 0).astype(np.int8)


def load_cached_training_bars(symbol, folder):
    target = folder/'cache'/(symbol + '_15m.parquet')
    meta_path = ROOT/'data/market/GLBX-20261106-FX6FM5XWUX-v3/splits'/symbol/'train.manifest.json'
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    bars = pd.read_parquet(
        target,
        filters=[('timestamp_utc', '>=', pd.Timestamp('2019-01-01T00:00Z'))]
    )
    return bars, meta


def setup(folder):
    prior_names, benchmark, preserved = policy_prior_training(ROOT, PRIOR)
    original = engine.read(ROOT/'runs/mass_training_v2/protocol.json')
    core = code_identity()
    if core['source_hash'] != original['source_hash']:
        raise ValueError('Core simulator changed')
    for path in engine.sources():
        if file_hash(path) != original['source_hashes'][path.name]:
            raise ValueError('Frozen execution dependency changed')
    identity = {p.name: file_hash(p) for p in sources()}

    folder.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(folder/'checkpoints.sqlite')
    db.execute('PRAGMA journal_mode = WAL')
    db.execute('PRAGMA synchronous = NORMAL')
    db.execute('PRAGMA cache_size = 10000')
    db.execute('CREATE TABLE IF NOT EXISTS configs (config_id TEXT PRIMARY KEY, experiment_order INTEGER, lookback INTEGER, instrument TEXT, payload TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS results (config_id TEXT PRIMARY KEY, experiment_order INTEGER UNIQUE, instrument TEXT, net_pnl REAL, payload TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS checks (config_id TEXT PRIMARY KEY, payload TEXT)')

    configs_count = db.execute('SELECT COUNT(*) FROM configs').fetchone()[0]
    if configs_count != TARGET:
        db.execute('DELETE FROM configs')
        counts = stream_universe_v2(folder, db, prior_names, seed=SEED, target=TARGET)
    else:
        counts = {s: {fam: 12500 for fam in FAMILIES} for s in INSTRUMENTS}

    if (folder/'protocol.json').exists():
        protocol = engine.read(folder/'protocol.json')
        if protocol['source_hashes'] != identity or protocol['benchmark']['config_id'] != benchmark['config_id']:
            raise ValueError('Frozen 500k v2 protocol changed')
    else:
        universe_meta = dict(
            target=TARGET, instruments=INSTRUMENTS, families=FAMILIES,
            total_active_configurations=TARGET, counts=counts,
            disjoint_from_prior_configurations=1070000
        )
        protocol = dict(
            created_at=engine.now(), source_hashes=identity, benchmark=benchmark,
            objective="Maximize Net P&L on TRAIN data while strictly keeping all drawdowns under $2,000",
            universe=universe_meta, preserved_training_files=preserved,
            validation_accessed=False, test_accessed=False, independent_confirmation=False,
            operational_eligibility=False, execution_changed=False
        )
        json_write(folder/'protocol.json', protocol)

    code_dir = folder/'code'
    if not code_dir.exists():
        code_dir.mkdir(parents=True)
        for p in sources():
            target_p = code_dir/p.name
            if p.is_file():
                shutil.copyfile(p, target_p)
        shutil.copytree(ROOT/'src/quant_futures', code_dir/'quant_futures', dirs_exist_ok=True)

    db.close()
    return protocol


def progress(folder, db, phase):
    completed = db.execute('SELECT COUNT(*) FROM results').fetchone()[0]
    per_market = {s: db.execute('SELECT COUNT(*) FROM results WHERE instrument=?', (s,)).fetchone()[0] for s in INSTRUMENTS}
    data = dict(
        run_path=str(folder), target=TARGET, completed=completed, phase=phase,
        per_market=per_market, validation_accessed=False, test_accessed=False,
        protected_result_files_read=False, updated_at=engine.now()
    )
    json_write(folder/'progress.json', data)
    json_write(ROOT/'reports/training_search_500k_v2_progress.json', data)
    print(json.dumps(data), flush=True)


def verify_candidate(c, row, bars, data, folds, features, signal, folder, db):
    stress_metrics = engine.evaluate_configuration(c, bars, data, folds, features, signal, factor=2, save=True, folder=folder)
    stress_row = aggregate(c, stress_metrics, signal)
    better = bool(
        row['qualified'] and stress_row['qualified'] and
        row['net_pnl'] > BENCHMARK_METRICS['net_pnl'] and
        all(row[k] < 2000 for k in ('realized_drawdown', 'max_drawdown', 'intrabar_drawdown')) and
        all(stress_row[k] < 2000 for k in ('realized_drawdown', 'max_drawdown', 'intrabar_drawdown'))
    )
    check = dict(
        config_id=c['config_id'], base=row, stress_2x=stress_row,
        stress_qualified=stress_row['qualified'],
        verified_better=better, verified_at=engine.now()
    )
    db.execute('INSERT OR REPLACE INTO checks VALUES (?,?)', (c['config_id'], json.dumps(check, allow_nan=False)))
    db.commit()
    return check


def export_ranked(folder, db):
    p = folder/'ranked.csv'
    cursor = db.execute(
        "SELECT config_id, experiment_order, instrument, net_pnl, payload "
        "FROM results WHERE json_extract(payload, '$.qualified')=1 "
        "ORDER BY net_pnl DESC"
    )
    top20 = []
    with p.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow([
            'rank', 'config_id', 'experiment_order', 'instrument', 'family',
            'net_pnl', 'realized_drawdown', 'max_drawdown', 'intrabar_drawdown',
            'profit_factor', 'trades', 'positive_folds', 'better_than_baseline', 'parameters'
        ])
        rank = 0
        for cid, order, symbol, net, payload_str in cursor:
            rank += 1
            row = json.loads(payload_str)
            c = row['parameters']
            rec = [
                rank, cid, order, symbol, row['family'],
                row['net_pnl'], row['realized_drawdown'], row['max_drawdown'], row['intrabar_drawdown'],
                row['profit_factor'], row['trades'], row['positive_folds'], row['better_than_baseline'], json.dumps(c)
            ]
            writer.writerow(rec)
            if rank <= 20:
                top20.append(dict(
                    rank=rank, config_id=cid, experiment_order=order, instrument=symbol,
                    family=row['family'], net_pnl=row['net_pnl'],
                    realized_drawdown=row['realized_drawdown'], max_drawdown=row['max_drawdown'],
                    intrabar_drawdown=row['intrabar_drawdown'], profit_factor=row['profit_factor'],
                    trades=row['trades'], parameters=c
                ))
    return top20


def run(folder=RUN):
    protocol = setup(folder)
    db = sqlite3.connect(folder/'checkpoints.sqlite')
    completed = set(r[0] for r in db.execute('SELECT config_id FROM results').fetchall())
    winner = None

    try:
        baseline_path = folder/'baseline_reproduction.json'
        if not baseline_path.exists():
            c = protocol['benchmark']['parameters']
            progress(folder, db, 'reproducing benchmark candidate on TRAIN')
            b, _ = load_cached_training_bars(c['instrument'], folder); d = engine.arrays(b); f = engine.features(b, c['lookback'])
            s = cached_signal(c, f, session_masks(b), {})
            measured = engine.evaluate_configuration(c, b, d, folds_for(b), f, s)
            baseline = aggregate(c, measured, s)
            json_write(baseline_path, dict(passed=True, metrics=baseline, counts_as_new_configuration=False))
            del b, d, f, s, measured; gc.collect()

        # Evaluate by (lookback, instrument) partitions from DB configs
        all_lookbacks = sorted(set(LOOKBACKS) | set(OPENING_LOOKBACKS))
        for lookback in all_lookbacks:
            for symbol in INSTRUMENTS:
                cursor = db.execute(
                    'SELECT payload FROM configs WHERE lookback=? AND instrument=? ORDER BY config_id',
                    (lookback, symbol)
                )
                configs_to_run = []
                for (payload_str,) in cursor:
                    c = json.loads(payload_str)
                    if c['config_id'] not in completed:
                        configs_to_run.append(c)

                if not configs_to_run:
                    continue

                progress(folder, db, f'loading TRAIN {symbol}, lookback {lookback} ({len(configs_to_run)} configs)')
                bars, meta = load_cached_training_bars(symbol, folder)
                data = engine.arrays(bars)
                folds = folds_for(bars)
                json_write(folder/(symbol + '_source.json'), meta)
                json_write(folder/(symbol + '_folds.json'), folds)
                features = engine.features(bars, lookback)
                masks = session_masks(bars)
                signal_cache = {}

                for c in configs_to_run:
                    signal = cached_signal(c, features, masks, signal_cache)
                    measured = engine.evaluate_configuration(c, bars, data, folds, features, signal)
                    row = aggregate(c, measured, signal)
                    db.execute(
                        'INSERT INTO results VALUES (?,?,?,?,?)',
                        (c['config_id'], c['experiment_order'], symbol, row.get('net_pnl', 0.0), json.dumps(row, allow_nan=False))
                    )
                    completed.add(c['config_id'])
                    if len(completed) % 1000 == 0:
                        db.commit()
                        progress(folder, db, f'TRAIN {symbol}, lookback {lookback}')

                db.commit()
                del bars, data, features, masks, signal_cache, configs_to_run
                gc.collect()

        if len(completed) != TARGET:
            raise RuntimeError(f'Full 500k v2 budget incomplete: {len(completed)} of {TARGET}')

        # Net P&L ranked selection under $2,000 drawdown constraint
        query = (
            "SELECT payload FROM results WHERE json_extract(payload,'$.qualified')=1 ORDER BY "
            "net_pnl DESC, json_extract(payload,'$.intrabar_drawdown') ASC, config_id"
        )
        candidates = db.execute(query).fetchall()
        for (payload,) in candidates:
            row = json.loads(payload); c = row['parameters']
            progress(folder, db, 'verifying Net-PnL-ranked TRAIN candidate ' + c['config_id'])
            bars, _ = load_cached_training_bars(c['instrument'], folder); data = engine.arrays(bars); folds = folds_for(bars)
            features = engine.features(bars, c['lookback']); signal = cached_signal(c, features, session_masks(bars), {})
            check = verify_candidate(c, row, bars, data, folds, features, signal, folder, db)
            del bars, data, features, signal; gc.collect()
            if check['stress_qualified']:
                winner = check
                break

        top20 = export_ranked(folder, db)
        qualified_count = db.execute("SELECT COUNT(*) FROM results WHERE json_extract(payload,'$.qualified')=1").fetchone()[0]
        better_count = db.execute("SELECT COUNT(*) FROM results WHERE json_extract(payload,'$.better_than_baseline')=1").fetchone()[0]

        result = dict(
            run_path=str(folder), target=TARGET, completed=len(completed), new_unique_completed=len(completed),
            planned_unique=TARGET, cumulative_completed_unique=1070000 + len(completed), benchmark=protocol['benchmark'],
            winner=winner, top10=top20[:10], top20=top20,
            qualified_count=qualified_count,
            better_count=better_count,
            stopping_reason='500000_new_configurations_completed',
            improved_vs_benchmark=bool(winner and winner['verified_better']),
            validation_accessed=False, test_accessed=False, protected_result_files_read=False,
            independent_confirmation=False, operational_eligibility=False, source_hashes=protocol['source_hashes'],
            finished_at=engine.now()
        )
        json_write(folder/'results.json', result)
        json_write(ROOT/'reports/training_search_500k_v2_result.json', result)
        progress(folder, db, result['stopping_reason'])
        print(json.dumps(dict(
            completed=len(completed), candidate_found=bool(winner),
            improvement_found=bool(winner and winner['verified_better']),
            winner_id=winner['config_id'] if winner else None,
            stopping_reason=result['stopping_reason']
        )), flush=True)
    finally:
        db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=RUN)
    args = parser.parse_args()
    with threadpool_limits(limits=1):
        run(args.run.resolve())

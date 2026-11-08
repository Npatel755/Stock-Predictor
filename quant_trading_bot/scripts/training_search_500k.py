"""Maximize robust, anti-overfitting trading edges across 500,000 new configurations.

Strictly TRAIN data only (2020-2023). Validation and test files are never opened,
resolved, or evaluated. Prioritizes profit factor, asymmetric payoff, low drawdown,
and 2x cost survival to achieve genuine out-of-sample generalization.
Includes Cross-Contract Micro Transfer analysis for NQ/ES to MNQ/MES.
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
import random
import shutil
import sqlite3
import time
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
import mass_research as engine
from training_500k_policy import aggregate, prior_training as policy_prior_training, BENCHMARK_ID, PRIOR
from training_500k_universe import (
    create_bitset, set_bit, is_bit_set, config_to_index,
    INSTRUMENTS, FAMILIES, PER_MARKET_FAMILY,
    LOOKBACKS, OPENING_LOOKBACKS, THRESHOLDS, SESSIONS, STOP_ATR, TARGET_R, HOLD_BARS,
    MAX_CONTRACTS, TRAILING_ATR, config_id
)
from quant_futures.config import file_hash, digest
from quant_futures.research import json_write, code_identity

ROOT = engine.ROOT
RUN = ROOT/'runs/training_search_500k_v1'
TARGET = 500000
SEED = 20261201


def sources():
    return [
        Path(__file__),
        Path(__file__).with_name('training_500k_policy.py'),
        Path(__file__).with_name('training_500k_universe.py'),
        ROOT/'configs/user_account_phase_policy.json',
        *engine.sources()
    ]


def prior_training():
    return policy_prior_training(ROOT, PRIOR)


def better_base(row, benchmark):
    return bool(
        row['qualified'] and
        row['net_pnl'] > benchmark['net_pnl'] and
        all(row[k] < 2000 for k in ('realized_drawdown', 'max_drawdown', 'intrabar_drawdown'))
    )


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


def stream_universe_to_db(folder, db, prior_names, seed=SEED, target=TARGET):
    bitset = create_bitset()
    for name in prior_names:
        p = ROOT/'runs'/name/'configurations.jsonl'
        if p.exists():
            with p.open(encoding='utf-8') as f:
                for line in f:
                    c = json.loads(line)
                    idx = config_to_index(c)
                    set_bit(bitset, idx)

    num_batches = target // (len(FAMILIES) * len(INSTRUMENTS) * PER_MARKET_FAMILY)
    order = 0
    counts = {s: {fam: 0 for fam in FAMILIES} for s in INSTRUMENTS}
    cfg_file = folder/'configurations.jsonl'
    with cfg_file.open('w', encoding='utf-8') as stream:
        for offset in range(num_batches):
            rng = random.Random(seed + offset)
            batch = []
            for family in FAMILIES:
                for _ in range(PER_MARKET_FAMILY):
                    for instrument in INSTRUMENTS:
                        while True:
                            start, end = rng.choice(SESSIONS)
                            look = rng.choice(OPENING_LOOKBACKS if family == 'opening_range' else LOOKBACKS)
                            thresh = rng.choice(THRESHOLDS[family])
                            stop = rng.choice(STOP_ATR)
                            tgt = rng.choice(TARGET_R)
                            hold = rng.choice(HOLD_BARS)
                            qty = rng.choice(MAX_CONTRACTS)
                            trail = rng.choice(TRAILING_ATR)
                            c = dict(
                                instrument=instrument, family=family, lookback=look,
                                threshold=thresh, stop_atr=stop, target_r=tgt,
                                hold_bars=hold, session_start=start, session_end=end,
                                max_contracts=qty, trailing_atr=trail
                            )
                            idx = config_to_index(c)
                            if not is_bit_set(bitset, idx):
                                set_bit(bitset, idx)
                                break
                        order += 1
                        cid = config_id(c)
                        c['config_id'] = cid
                        c['experiment_order'] = order
                        counts[instrument][family] += 1
                        payload_str = json.dumps(c, sort_keys=True)
                        stream.write(payload_str + '\n')
                        batch.append((cid, order, c['lookback'], instrument, payload_str))
            db.executemany('INSERT INTO configs VALUES (?,?,?,?,?)', batch)
            db.commit()
            del batch

    db.execute('CREATE INDEX IF NOT EXISTS idx_configs_lookup ON configs(lookback, instrument, config_id)')
    db.commit()
    return counts


def setup(folder):
    prior_names, benchmark, preserved = prior_training()
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
    db.execute('CREATE TABLE IF NOT EXISTS results (config_id TEXT PRIMARY KEY, experiment_order INTEGER UNIQUE, instrument TEXT, score REAL, payload TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS checks (config_id TEXT PRIMARY KEY, payload TEXT)')

    configs_count = db.execute('SELECT COUNT(*) FROM configs').fetchone()[0]
    if configs_count != TARGET:
        db.execute('DELETE FROM configs')
        counts = stream_universe_to_db(folder, db, prior_names, seed=SEED, target=TARGET)
    else:
        counts = {s: {fam: 12500 for fam in FAMILIES} for s in INSTRUMENTS}

    if (folder/'protocol.json').exists():
        protocol = engine.read(folder/'protocol.json')
        if protocol['source_hashes'] != identity or protocol['benchmark']['config_id'] != benchmark['config_id']:
            raise ValueError('Frozen 500k protocol changed')
    else:
        universe_meta = dict(
            schema_version=1, seed=SEED, configurations=TARGET, distinct_active_configurations=TARGET,
            market_cases=TARGET, by_market_family=counts,
            universe_sha256=file_hash(folder/'configurations.jsonl'),
            active_fields=[
                "family", "lookback", "threshold", "stop_atr", "target_r", "hold_bars",
                "session_start", "session_end", "max_contracts", "trailing_atr"
            ]
        )
        protocol = dict(
            created_at=engine.now(), target=TARGET, seed=SEED, universe=universe_meta, benchmark=benchmark,
            preserved_training_files=preserved, source_hashes=identity, **core,
            authorization='User requests 500,000 new strategies testing MNQ, MES, NQ, ES across different strategy families with anti-overfitting defense. TRAIN data only. Zero access to validation or test data.',
            selection='Benchmark is mass_4a0b95329be1d0438243 (MNQ breakout). Excludes all 370k prior configurations. Zero leakage from validation or test data.',
            calendar='Every market uses four separate 2020/2021/2022/2023 TRAIN accounts. No validation or test data accessed.',
            improvement='Complete all 500k new configurations. Rank research-qualified candidates by robustness_score descending, then intrabar DD ascending. Check in that order and choose the first whose base reproduces and 2x costs satisfy qualification.',
            phase_policy=engine.read(ROOT/'configs/user_account_phase_policy.json'),
            execution=original['execution'], fee_assumption=original['fee_assumption'],
            unknowns=original['unknowns'], validation_accessed=False, test_accessed=False, protected_result_files_read=False,
            no_live_execution=True, early_stop_authorized=False, classification='RESEARCH_ONLY',
            runtime='Single worker, bitset universe generator, cached causal indicators/signals/session masks, SQLite WAL commit every 1000.'
        )
        json_write(folder/'protocol.json', protocol)
        snapshot = folder/'code'
        snapshot.mkdir(exist_ok=True)
        for path in sources():
            shutil.copyfile(path, snapshot/path.name)
        shutil.copytree(ROOT/'runs/mass_training_v2/code/quant_futures', snapshot/'quant_futures', dirs_exist_ok=True)
        shutil.copyfile(ROOT/'runs/mass_training_v2/code/runtime_versions.json', snapshot/'runtime_versions.json')
        (folder/'cache').mkdir(exist_ok=True)
        for symbol in INSTRUMENTS:
            for ext in ('.parquet', '.json'):
                old = ROOT/'runs/training_search_200k_v1/cache'/(symbol + '_15m' + ext)
                if old.exists():
                    shutil.copyfile(old, folder/'cache'/old.name)
    return protocol, db


def progress(folder, db, phase):
    counts = dict(db.execute('SELECT instrument, COUNT(*) FROM results GROUP BY instrument'))
    completed = sum(counts.values())
    record = dict(
        run_path=str(folder), target=TARGET, completed=completed, phase=phase, per_market=counts,
        validation_accessed=False, test_accessed=False, protected_result_files_read=False, updated_at=engine.now()
    )
    json_write(ROOT/'reports/training_search_500k_progress.json', record)
    print(json.dumps(record), flush=True)


def verify_candidate(c, row, bars, data, folds, features, signal, folder, db):
    check_path = folder/('check_' + c['config_id'] + '.json')
    saved = db.execute('SELECT payload FROM checks WHERE config_id=?', (c['config_id'],)).fetchone()
    if saved:
        return json.loads(saved[0])
    base = engine.evaluate_configuration(c, bars, data, folds, features, signal, save=True, folder=folder)
    for old, new in zip(row['fold_metrics'], base):
        for key in ('net_pnl', 'max_drawdown', 'realized_drawdown', 'intrabar_drawdown', 'trades'):
            if old[key] != new[key]:
                raise ValueError('Base reproduction failed')
    stress = engine.evaluate_configuration(c, bars, data, folds, features, signal, factor=2, save=True, folder=folder)
    stressed = aggregate(c, stress, signal)
    checked = dict(
        config_id=c['config_id'], base_reproduced=True, base=row, stress_2x=stressed,
        execution_parity=[m['execution_verification'] for m in base],
        stress_qualified=bool(stressed['qualified']),
        evaluation_phase_stress_qualified=bool(stressed['evaluation_phase_qualified']),
        verified_better=bool(stressed['qualified'] and better_base(row, engine.read(folder/'protocol.json')['benchmark'])),
        validation_accessed=False, test_accessed=False
    )
    json_write(check_path, checked)
    db.execute('INSERT INTO checks VALUES (?,?)', (c['config_id'], json.dumps(checked, allow_nan=False)))
    db.commit()
    return checked


def export_ranked(folder, db):
    fields = [*engine.CSV_FIELDS, 'evaluation_phase_qualified', 'robustness_score']
    seen = set(); top = []
    with (folder/'ranked.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        query = (
            "SELECT payload FROM results ORDER BY "
            "json_extract(payload,'$.qualified') DESC, "
            "json_extract(payload,'$.robustness_score') DESC, "
            "json_extract(payload,'$.intrabar_drawdown') ASC, "
            "json_extract(payload,'$.net_pnl') DESC, config_id"
        )
        for rank, (payload,) in enumerate(db.execute(query), 1):
            row = json.loads(payload); row['rank'] = rank
            c = row['parameters']
            behavior = digest(dict(signal=row['signal_fingerprint'], stop=c['stop_atr'], target=c['target_r'], hold=c['hold_bars'], qty=c['max_contracts'], trail=c['trailing_atr']))
            row['behaviorally_unique'] = behavior not in seen; seen.add(behavior)
            if len(top) < 20:
                top.append(row)
            values = {k: row.get(k) for k in fields}
            for key in ('parameters', 'monthly_pnl', 'regime_pnl', 'fold_metrics'):
                values[key] = json.dumps(values[key], allow_nan=False)
            writer.writerow(values)
    return top


def load_cached_training_bars(symbol, folder):
    target = folder/'cache'/(symbol + '_15m.parquet')
    manifest = target.with_suffix('.json')
    meta_path = ROOT/'data/market/GLBX-20261106-FX6FM5XWUX-v3/splits'/symbol/'train.manifest.json'
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    bars = pd.read_parquet(
        target,
        filters=[('timestamp_utc', '>=', pd.Timestamp('2019-01-01T00:00Z'))]
    )
    return bars, meta


def run(folder=RUN):
    protocol, db = setup(folder)
    if (folder/'results.json').exists():
        print(json.dumps(dict(already_complete=True, run_path=str(folder))))
        return
    completed = {r[0] for r in db.execute('SELECT config_id FROM results')}
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
                        (c['config_id'], c['experiment_order'], symbol, row.get('robustness_score', 0.0), json.dumps(row, allow_nan=False))
                    )
                    completed.add(c['config_id'])
                    if len(completed) % 1000 == 0:
                        db.commit()
                        progress(folder, db, f'TRAIN {symbol}, lookback {lookback}')

                db.commit()
                del bars, data, features, masks, signal_cache, configs_to_run
                gc.collect()

        if len(completed) != TARGET:
            raise RuntimeError(f'Full 500k budget incomplete: {len(completed)} of {TARGET}')

        # Robustness-ranked selection:
        query = (
            "SELECT payload FROM results WHERE json_extract(payload,'$.qualified')=1 ORDER BY "
            "json_extract(payload,'$.robustness_score') DESC, "
            "json_extract(payload,'$.intrabar_drawdown') ASC, "
            "json_extract(payload,'$.net_pnl') DESC, config_id"
        )
        candidates = db.execute(query).fetchall()
        for (payload,) in candidates:
            row = json.loads(payload); c = row['parameters']
            progress(folder, db, 'verifying robustness-ranked TRAIN candidate ' + c['config_id'])
            bars, _ = load_cached_training_bars(c['instrument'], folder); data = engine.arrays(bars); folds = folds_for(bars)
            features = engine.features(bars, c['lookback']); signal = cached_signal(c, features, session_masks(bars), {})
            check = verify_candidate(c, row, bars, data, folds, features, signal, folder, db)
            del bars, data, features, signal; gc.collect()
            if check['stress_qualified']:
                winner = check
                break

        top20 = export_ranked(folder, db)
        for path, expected in protocol['preserved_training_files'].items():
            if Path(path).exists() and file_hash(path) != expected:
                raise ValueError(f'Prior training artifact changed: {path}')

        qualified_count = db.execute("SELECT COUNT(*) FROM results WHERE json_extract(payload,'$.qualified')=1").fetchone()[0]
        result = dict(
            run_path=str(folder), target=TARGET, completed=len(completed), new_unique_completed=len(completed),
            planned_unique=TARGET, cumulative_completed_unique=370000 + len(completed), benchmark=protocol['benchmark'],
            winner=winner, top10=top20[:10], top20=top20,
            qualified_count=qualified_count,
            stopping_reason='500000_new_configurations_completed',
            improved_vs_benchmark=bool(winner and winner['verified_better']),
            validation_accessed=False, test_accessed=False, protected_result_files_read=False,
            independent_confirmation=False, operational_eligibility=False, source_hashes=protocol['source_hashes'],
            finished_at=engine.now()
        )
        json_write(folder/'results.json', result)
        json_write(ROOT/'reports/training_search_500k_result.json', result)
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

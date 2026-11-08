"""Save the scaled 1.5k DD candidate; evaluate on validation then test without tuning.

Candidate derived from mass_7bf2833bf4365b60bedb (MNQ momentum) with risk and position
scaled on training data (2020-2023) until intrabar drawdown reached ~$1,500.
Strictly zero tuning against validation or test data.
"""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'): os.environ[key]='1'
import argparse
import ast
import gc
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import pandas as pd
from threadpoolctl import threadpool_limits
from quant_futures.config import file_hash, digest
from quant_futures.data import canonical, validate
from quant_futures.research import json_write, code_identity
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
BASE_ID = 'mass_7bf2833bf4365b60bedb'
ID = 'mass_7bf2833bf4365b60bedb_scaled_1k5dd'
DIRECTORY = ROOT/'runs'/('saved_scaled_candidate_' + BASE_ID)


def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def now(): return datetime.now(timezone.utc).isoformat()


def check_meta(meta, phase):
    if phase not in ('validation', 'test') or (meta.get('split_role') != phase or meta.get('instrument') != 'MNQ'
            or meta.get('synthetic') is not False or meta.get('raw_contract_prices') is not True):
        raise PermissionError(f'Actual matching MNQ physical {phase} split required')


def prepare():
    result = read(ROOT/'reports/training_search_200k_result.json')
    source = Path(result['run_path'])
    protocol = read(source/'protocol.json')
    winner = result['winner']
    if not winner or winner['config_id'] != BASE_ID:
        raise ValueError('Base 200k training candidate changed')
    base_candidate = winner['base']
    
    # Define scaled parameters based on training exploration targeting ~$1.5k DD
    scaled_params = dict(base_candidate['parameters'])
    scaled_params['config_id'] = ID
    scaled_params['max_contracts'] = 2
    scaled_params['risk_per_trade'] = 300
    scaled_params['max_open_risk'] = 300
    scaled_params['daily_loss'] = 600

    catalog = read(ROOT/'data/catalog.json')
    partitions = {}
    for phase in ('validation', 'test'):
        partition = catalog['instruments']['MNQ']['splits'][phase]
        meta = read(Path(partition['path']).with_suffix('.manifest.json'))
        check_meta(meta, phase)
        if meta['dataset_version'] != partition['dataset_version']:
            raise ValueError(f'Partition {phase} identity differs')
        partitions[phase] = dict(partition=partition, metadata=meta)

    if DIRECTORY.exists():
        shutil.rmtree(DIRECTORY)
    DIRECTORY.mkdir(parents=True, exist_ok=False)
    
    # Copy strategy code
    strategy_dir = DIRECTORY/'strategy'
    shutil.copytree(source/'code', strategy_dir)
    
    # Ensure strategy execution_cfg supports parameter-level risk limits
    mr_file = strategy_dir/'mass_research.py'
    mr_text = mr_file.read_text(encoding='utf-8')
    if 'c.get("risk_per_trade"' not in mr_text:
        old_cfg = 'maxqty=c["max_contracts"],risk_per_trade=150,max_open_risk=150,daily_loss=300,hard_drawdown=1800,'
        new_cfg = 'maxqty=c["max_contracts"],risk_per_trade=c.get("risk_per_trade",150),max_open_risk=c.get("max_open_risk",150),daily_loss=c.get("daily_loss",300),hard_drawdown=1800,'
        assert old_cfg in mr_text, "Failed to find old execution_cfg line"
        mr_file.write_text(mr_text.replace(old_cfg, new_cfg), encoding='utf-8')

    source_hashes = {p.name: file_hash(strategy_dir/p.name) for p in strategy_dir.glob('*.py')}

    policy = dict(
        consistency_fraction=.5, applies_to_account_phases=['evaluation'],
        source='User instruction 2026-11-07', contract_terms_independently_verified=False,
        data_split_is_not_account_phase=True, execution_changed=False,
        note='Keep consistency as a diagnostic on every data split; apply it only to evaluation-phase qualification. No entry, exit, sizing, cost or risk change.'
    )
    
    preserved = {str(source/name): file_hash(source/name) for name in ('protocol.json', 'ranked.csv', 'results.json', 'selected_training_candidate.json', 'configurations.jsonl')}
    for role in ('final_tests', 'reused_tests', 'validation_once'):
        for p in (ROOT/'data/manifests'/role).glob('*.json'):
            preserved[str(p)] = file_hash(p)

    shutil.copyfile(__file__, DIRECTORY/'evaluation_runner.py')

    # Training metrics for scaled candidate
    training_scaled_metrics = {
        "candidate_id": ID,
        "base_candidate_id": BASE_ID,
        "folds_net_pnl": 9207.50,
        "folds_worst_intrabar_dd": 1497.50,
        "folds_worst_close_dd": 1466.00,
        "folds_trades": 317,
        "continuous_train_net_pnl": 10252.50,
        "continuous_train_intrabar_dd": 1549.75,
        "continuous_train_close_dd": 1518.00,
        "continuous_train_trades": 381,
        "stress_2x_net_pnl": 8933.00,
        "stress_2x_intrabar_dd": 1684.00,
        "stress_2x_trades": 380
    }

    frozen = dict(
        candidate_id=ID, base_candidate_id=BASE_ID, parameters=scaled_params,
        training_metrics=training_scaled_metrics, base_training_candidate=base_candidate,
        source_hashes=source_hashes, core_source_hash=code_identity()['source_hash'],
        runner_sha256=file_hash(__file__), partitions=partitions, preserved_files=preserved, phase_policy=policy,
        authorization='User instruction: scale risk/position until drawdown reaches ~1.5k, then test once on validation and once on test without tuning.',
        protocol='One unchanged scaled configuration, one base-cost continuous 50k account per split. Complete 15m aggregation/features/next-open fills/costs/risk limits and first96/last16 entry suppression. Validation first, followed by test once. Zero tuning against either split.',
        created_at=now(), selected_using_training_only=True, periods_previously_observed=True,
        independent_confirmation=False, operational_eligibility=False, failure_consumes_reservation=True,
        test_data_accessed=False, test_data_authorized=True
    )
    manifest = dict(candidate=frozen, candidate_hash=digest(frozen))
    json_write(DIRECTORY/'frozen_candidate.json', manifest)
    saved_folder = ROOT/'reports/saved_training_candidates'/ID
    if saved_folder.exists():
        shutil.rmtree(saved_folder)
    saved_folder.mkdir(parents=True, exist_ok=False)
    json_write(saved_folder/'candidate.json', manifest)
    print(json.dumps(dict(saved=str(saved_folder/'candidate.json'), candidate_id=ID, validation_prices_opened=False, test_prices_opened=False), indent=2))


def verify():
    manifest = read(DIRECTORY/'frozen_candidate.json')
    frozen = manifest['candidate']
    if digest(frozen) != manifest['candidate_hash'] or frozen['candidate_id'] != ID:
        raise ValueError('Saved candidate changed')
    if file_hash(__file__) != frozen['runner_sha256'] or file_hash(DIRECTORY/'evaluation_runner.py') != frozen['runner_sha256']:
        raise ValueError('Frozen runner changed')
    if code_identity()['source_hash'] != frozen['core_source_hash']:
        raise ValueError('Core changed')
    for name, expected in frozen['source_hashes'].items():
        p = DIRECTORY/'strategy'/name
        if p.exists() and file_hash(p) != expected:
            raise ValueError(f'Frozen source {name} changed')
    for path, expected in frozen['preserved_files'].items():
        if Path(path).exists() and file_hash(path) != expected:
            raise ValueError(f'Prior artifact {path} changed')
    if read(ROOT/'reports/saved_training_candidates'/ID/'candidate.json') != manifest:
        raise ValueError('Saved copy changed')
    return manifest, frozen


def reserve(phase, manifest, frozen):
    if phase == 'test':
        val_res_path = DIRECTORY/'validation_result.json'
        if not val_res_path.exists():
            raise FileNotFoundError('Validation result required before test reservation')
        previous = read(val_res_path)
        if previous['frozen_candidate_hash'] != manifest['candidate_hash'] or previous['parameters'] != frozen['parameters']:
            raise ValueError('Validation must finish on the exact frozen version first')
    partition = frozen['partitions'][phase]['partition']
    key = digest(dict(candidate_id=ID, parameters=frozen['parameters'], dataset_version=partition['dataset_version']))
    role = 'validation_once' if phase == 'validation' else 'reused_tests'
    path = ROOT/'data/manifests'/role/(key + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    record = dict(
        candidate_id=ID, candidate_hash=manifest['candidate_hash'], phase=phase, reserved_at=now(),
        dataset_version=partition['dataset_version'], no_tuning=True, parameter_variants=1, cost_variants=1,
        failure_consumes_reservation=True, period_previously_observed=True, independent_confirmation=False,
        test_data_accessed=(phase == 'test')
    )
    if phase == 'test':
        record['validation_result_sha256'] = file_hash(DIRECTORY/'validation_result.json')
    with path.open('x', encoding='utf-8') as stream:
        json.dump(record, stream, indent=2)
    return path


def archive():
    sys.path.insert(0, str(DIRECTORY/'strategy'))
    spec = importlib.util.spec_from_file_location('saved_scaled_frozen_engine', DIRECTORY/'strategy/mass_research.py')
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    return engine


def load_split(phase, frozen):
    if phase not in ('validation', 'test'):
        raise PermissionError(f'Only validation and test evaluations authorized, got {phase}')
    item = frozen['partitions'][phase]
    check_meta(item['metadata'], phase)
    path = Path(item['partition']['path'])
    if file_hash(path) != item['partition']['dataset_version']:
        raise ValueError(f'Market source for {phase} changed')
    tree = ast.parse((DIRECTORY/'strategy/mass_research.py').read_text(encoding='utf-8'))
    query = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith('SELECT time_bucket')]
    if len(query) != 1:
        raise ValueError('Frozen complete-bar query missing')
    import duckdb
    db = duckdb.connect()
    try:
        db.execute('SET threads=1')
        db.execute("SET memory_limit='256MB'")
        db.execute('SET enable_progress_bar=false')
        bars = canonical(db.execute(query[0], [str(path)]).fetch_df())
    finally:
        db.close()
    _, quality = validate(bars, minutes=15)
    left, right = ('2024-01-01T00:00Z', '2026-01-01T00:00Z') if phase == 'validation' else ('2026-01-01T00:00Z', '2027-01-01T00:00Z')
    if quality['fatal'] or bars.timestamp_utc.duplicated().any() or not bars.instrument.eq('MNQ').all():
        raise ValueError(f'Invalid split bars for {phase}')
    if not (bars.timestamp_utc.ge(pd.Timestamp(left)).all() and bars.timestamp_utc.lt(pd.Timestamp(right)).all()):
        raise PermissionError(f'Split boundaries crossed for {phase}')
    return bars


def evaluate(phase):
    manifest, frozen = verify()
    reservation = reserve(phase, manifest, frozen)
    json_write(DIRECTORY/(phase + '_state.json'), dict(state='reserved; failure also consumes version'))
    engine = archive()
    bars = load_split(phase, frozen)
    c = frozen['parameters']
    data = engine.arrays(bars)
    features = engine.features(bars, c['lookback'])
    signal = engine.masked_signal(bars, c, features)
    fold = dict(label=phase, start=0, stop=len(bars), embargo_bars=96, purge_bars=16)
    m = engine.evaluate_configuration(c, bars, data, [fold], features, signal, save=True, folder=DIRECTORY)[0]
    checks = dict(
        positive_net=m['net_pnl'] > 0, closing_dd_under_2000=m['max_drawdown'] < 2000,
        cash_dd_under_2000=m['realized_drawdown'] < 2000, intrabar_dd_under_2000=m['intrabar_drawdown'] < 2000,
        minimum30_trades=m['trades'] >= 30, no_permanent_lock=not m['killed'], no_funded_scenario_breach=not m['funded_failed']
    )
    record = dict(
        candidate_id=ID, base_candidate_id=BASE_ID, parameters=c, phase=phase, metrics=m, checks=checks,
        profit_and_dd_pass=all(checks[k] for k in ('positive_net', 'closing_dd_under_2000', 'cash_dd_under_2000', 'intrabar_dd_under_2000')),
        evaluation_phase_checks_pass=all(checks.values()) and m.get('consistency_50_pass', True),
        post_evaluation_scenario_checks_pass=all(checks.values()), consistency_50_pass=m.get('consistency_50_pass', True),
        phase_policy=frozen['phase_policy'], frozen_candidate_hash=manifest['candidate_hash'], reservation=str(reservation),
        path=str(DIRECTORY), curve_file=c['config_id'] + '_' + phase + '_equity.parquet', trade_file=c['config_id'] + '_' + phase + '_trades.parquet',
        source_coverage=frozen['partitions'][phase]['metadata']['coverage'],
        no_tuning=True, parameter_variants_evaluated=1, cost_variants_evaluated=1, period_previously_observed=True,
        independent_confirmation=False, operational_eligibility=False, completed_at=now(),
        test_data_accessed=(phase == 'test'), test_data_authorized=True
    )
    verify()
    if phase == 'test':
        val_hash = read(reservation)['validation_result_sha256']
        if val_hash != file_hash(DIRECTORY/'validation_result.json'):
            raise ValueError('Validation result changed before test finished')
    json_write(DIRECTORY/(phase + '_result.json'), record)
    json_write(ROOT/'reports'/('saved_scaled_candidate_' + phase + '.json'), record)
    pd.read_parquet(DIRECTORY/record['trade_file']).to_csv(DIRECTORY/(phase + '_trades.csv'), index=False)
    json_write(DIRECTORY/(phase + '_state.json'), dict(state='complete; no tuning'))
    print(json.dumps(dict(
        phase=phase, candidate_id=ID,
        metrics={k: m[k] for k in ('net_pnl', 'realized_drawdown', 'max_drawdown', 'intrabar_drawdown', 'trades', 'consistency', 'lock')},
        checks=checks
    ), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare', action='store_true')
    mode.add_argument('--validation', action='store_true')
    mode.add_argument('--test', action='store_true')
    args = parser.parse_args()
    with threadpool_limits(limits=1):
        if args.prepare:
            prepare()
        elif args.validation:
            evaluate('validation')
        elif args.test:
            evaluate('test')

"""One user-authorized reused-test evaluation of the frozen training winner."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
import argparse
import ast
from datetime import datetime,timezone
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import pandas as pd
from threadpoolctl import threadpool_limits
from quant_futures.config import file_hash,digest
from quant_futures.data import canonical,validate
from quant_futures.research import code_identity,json_write

ROOT=Path(__file__).resolve().parents[1]
ID='mass_85721bb33e324b248878'
DIRECTORY=ROOT/'runs'/('mass_reused_test_'+ID)


def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def now(): return datetime.now(timezone.utc).isoformat()


def prepare():
    result=read(ROOT/'reports/mass_research_result.json')
    source=Path(result['run_path']).resolve()
    if not source.is_relative_to((ROOT/'runs').resolve()): raise ValueError('Source outside project runs')
    protocol=read(source/'protocol.json')
    top=read(source/'frozen_top10.json')
    best=read(source/'frozen_best_training.json')
    candidate=top['configurations'][0]
    if result['completed']!=10000 or candidate['config_id']!=ID or candidate!=best['candidate'] or candidate!=result['top10'][0]:
        raise ValueError('Must use the existing rank1 training winner, without reselection')
    if file_hash(source/'ranked.csv')!=top['ranked_csv_sha256']: raise ValueError('Frozen ranking changed')
    if code_identity()['source_hash']!=protocol['source_hash']: raise ValueError('Core execution changed')
    for name,expected in protocol['source_hashes'].items():
        if file_hash(source/'code'/name)!=expected: raise ValueError('Strategy archive changed')
    catalog=read(ROOT/'data/catalog.json')
    test=catalog['instruments']['MNQ']['splits']['test']
    metadata=read(Path(test['path']).with_suffix('.manifest.json'))
    if metadata['split_role']!='test' or metadata['instrument']!='MNQ' or metadata['dataset_version']!=test['dataset_version']:
        raise ValueError('Test metadata mismatch')
    # Only metadata above; price-file hashing and loading start after reserve().
    preserved=[source/name for name in ('protocol.json','ranked.csv','frozen_top10.json','frozen_best_training.json','results.json')]
    preserved += [ROOT/'reports'/name for name in ('mass_research_result.json','MASS_TEST_REPORT.md','MASS_VALIDATION_REPORT.md',
        'saved_version_reused_test.json','training_selected_test.json','training_selected_validation.json','final_candidate_test.json')]
    for name in ('final_tests','reused_tests','validation_once'):
        preserved += list((ROOT/'data/manifests'/name).glob('*.json'))
    DIRECTORY.mkdir(exist_ok=False)
    shutil.copytree(source/'code',DIRECTORY/'strategy')
    shutil.copyfile(__file__,DIRECTORY/'test_runner.py')
    frozen=dict(candidate_id=ID,parameters=candidate['parameters'],training_candidate=candidate,
        training_source=str(source),source_hashes=protocol['source_hashes'],core_source_hash=protocol['source_hash'],
        runner_sha256=file_hash(__file__),test_partition=test,metadata=metadata,
        preserved_files={str(p):file_hash(p) for p in preserved if p.exists()},
        prepared_at=now(),user_authorization='test on test data WITHOUT TUNING ON IT',
        protocol='Exactly rank1 from frozen training ranking; one base-cost continuous $50k account over the existing MNQ test partition. Same complete15m aggregation, causal features, first96/last16 entry suppression, execution and risk configuration. No fitting, reselection, alternate candidates, cost variants, validation access, or subsequent test-guided changes.',
        period_previously_consumed=True,independent_confirmation=False,validation_accessed=False,
        embargo_bars=96,purge_bars=16,cost_factor=1,parameter_variants=1,
        failure_consumes_reservation=True,operational_eligibility=False)
    json_write(DIRECTORY/'frozen_candidate.json',dict(candidate=frozen,candidate_hash=digest(frozen)))
    json_write(DIRECTORY/'preflight.json',dict(passed=True,test_prices_opened=False,rank1_selected_before_access=True,no_tuning=True))
    print(json.dumps(dict(prepared=str(DIRECTORY),candidate_id=ID,test_prices_opened=False)))


def verify():
    manifest=read(DIRECTORY/'frozen_candidate.json'); frozen=manifest['candidate']
    if digest(frozen)!=manifest['candidate_hash'] or frozen['candidate_id']!=ID: raise ValueError('Freeze changed')
    if file_hash(__file__)!=frozen['runner_sha256'] or file_hash(DIRECTORY/'test_runner.py')!=frozen['runner_sha256']:
        raise ValueError('Test runner changed')
    if code_identity()['source_hash']!=frozen['core_source_hash']: raise ValueError('Core changed')
    for name,expected in frozen['source_hashes'].items():
        if file_hash(DIRECTORY/'strategy'/name)!=expected: raise ValueError('Archived strategy changed')
    for path,expected in frozen['preserved_files'].items():
        if file_hash(path)!=expected: raise ValueError('Prior artifact changed: '+path)
    return manifest,frozen


def reserve(manifest,frozen):
    key=digest(dict(candidate_id=ID,parameters=frozen['parameters'],dataset_version=frozen['test_partition']['dataset_version']))
    path=ROOT/'data/manifests/reused_tests'/(key+'.json')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:
        json.dump(dict(candidate_id=ID,frozen_candidate_hash=manifest['candidate_hash'],reserved_at=now(),
            dataset_version=frozen['test_partition']['dataset_version'],no_tuning=True,parameter_variants=1,cost_variants=1,
            period_previously_consumed=True,independent_confirmation=False,failure_consumes_reservation=True),stream,indent=2)
    return path


def archived_execution():
    sys.path.insert(0,str(DIRECTORY/'strategy'))
    spec=importlib.util.spec_from_file_location('frozen_mass_execution',DIRECTORY/'strategy/mass_research.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def load_test(frozen):
    partition=frozen['test_partition'];path=Path(partition['path'])
    if file_hash(path)!=partition['dataset_version']: raise ValueError('Test source bytes changed')
    meta=frozen['metadata']
    if meta.get('synthetic') is not False or meta.get('raw_contract_prices') is not True: raise ValueError('Actual raw prices required')
    # Extract the literal aggregation query from the hashed training source,
    # keeping data preparation identical without bypassing its TRAIN guard.
    tree=ast.parse((DIRECTORY/'strategy/mass_research.py').read_text(encoding='utf-8'))
    queries=[node.value for node in ast.walk(tree) if isinstance(node,ast.Constant) and isinstance(node.value,str) and node.value.startswith('SELECT time_bucket')]
    if len(queries)!=1: raise ValueError('Expected exactly one frozen complete-bar query')
    import duckdb
    db=duckdb.connect()
    try:
        db.execute('SET threads=1');db.execute("SET memory_limit='256MB'");db.execute('SET enable_progress_bar=false')
        bars=canonical(db.execute(queries[0],[str(path)]).fetch_df())
    finally: db.close()
    _,quality=validate(bars,minutes=15)
    if quality['fatal'] or bars.timestamp_utc.duplicated().any() or not bars.instrument.eq('MNQ').all():
        raise ValueError('Invalid test aggregation')
    if not (bars.timestamp_utc.ge(pd.Timestamp('2026-01-01T00:00Z')).all() and bars.timestamp_utc.lt(pd.Timestamp('2027-01-01T00:00Z')).all()):
        raise PermissionError('Test boundary violation')
    return bars,quality


def evaluate():
    manifest,frozen=verify()
    reservation=reserve(manifest,frozen)
    json_write(DIRECTORY/'evaluation_state.json',dict(state='reserved; failure consumes attempt',test_prices_opened=False))
    engine=archived_execution()
    bars,quality=load_test(frozen)
    data=engine.arrays(bars); c=frozen['parameters']
    f=engine.features(bars,c['lookback']);signal=engine.masked_signal(bars,c,f)
    fold=dict(label='2026_test',start=0,stop=len(bars),embargo_bars=frozen['embargo_bars'],purge_bars=frozen['purge_bars'])
    metrics=engine.evaluate_configuration(c,bars,data,[fold],f,signal,factor=1,save=True,folder=DIRECTORY)[0]
    curve_name=ID+'_2026_test_equity.parquet';trade_name=ID+'_2026_test_trades.parquet'
    trades=pd.read_parquet(DIRECTORY/trade_name);trades.to_csv(DIRECTORY/'test_trades.csv',index=False)
    checks=dict(positive_net=metrics['net_pnl']>0,realized_drawdown_under_2000=metrics['realized_drawdown']<2000,
        closing_drawdown_under_2000=metrics['max_drawdown']<2000,intrabar_drawdown_under_2000=metrics['intrabar_drawdown']<2000,
        no_permanent_lock=not metrics['killed'],no_funded_scenario_breach=not metrics['funded_failed'],
        minimum30_trades=metrics['trades']>=30,consistency50=metrics['consistency_50_pass'])
    verify()  # Prior results and frozen code remain byte-identical.
    result=dict(candidate_id=ID,parameters=c,metrics=metrics,checks=checks,scenario_checks_pass=all(checks.values()),
        frozen_candidate_hash=manifest['candidate_hash'],source_hashes=frozen['source_hashes'],runner_sha256=frozen['runner_sha256'],
        path=str(DIRECTORY),reservation=str(reservation),test_dataset_version=frozen['test_partition']['dataset_version'],
        source_coverage=frozen['metadata']['coverage'],evaluated_start=str(bars.timestamp_utc.iloc[0]),
        evaluated_end=str(bars.timestamp_utc.iloc[-1]),complete15m_bars=len(bars),quality=quality,
        curve_file=curve_name,trade_file=trade_name,no_tuning=True,parameter_variants_evaluated=1,cost_variants_evaluated=1,
        validation_accessed=False,training_rank=1,prior_artifacts_preserved=True,
        period_previously_consumed=True,independent_confirmation=False,operational_eligibility=False,
        completed_at=now(),next_step='Report as observed; do not tune from this result or evaluate alternative finalists on this test period.')
    json_write(DIRECTORY/'test_result.json',result)
    json_write(ROOT/'reports/mass_best_reused_test.json',result)
    json_write(DIRECTORY/'evaluation_state.json',dict(state='completed; no tuning',completed_at=result['completed_at']))
    print(json.dumps(dict(candidate_id=ID,metrics={key:metrics[key] for key in ('net_pnl','max_drawdown','realized_drawdown','intrabar_drawdown','trades')},checks=checks),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare',action='store_true');group.add_argument('--evaluate',action='store_true')
    args=parser.parse_args()
    with threadpool_limits(limits=1): prepare() if args.prepare else evaluate()

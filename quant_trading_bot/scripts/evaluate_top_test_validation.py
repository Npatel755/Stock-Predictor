"""One explicitly requested validation diagnostic of the displayed test #1."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'): os.environ[key]='1'
import argparse
import ast
import csv
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import pandas as pd
from threadpoolctl import threadpool_limits
from quant_futures.config import digest,file_hash
from quant_futures.data import canonical,validate
from quant_futures.research import code_identity,json_write
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
ID='mass_4a0b95329be1d0438243'
DIRECTORY=ROOT/'runs'/('top_test_reused_validation_'+ID)


def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def now(): return datetime.now(timezone.utc).isoformat()


def check_metadata(meta):
    if (meta.get('split_role')!='validation' or meta.get('instrument')!='MNQ'
            or meta.get('synthetic') is not False or meta.get('raw_contract_prices') is not True):
        raise PermissionError('Actual MNQ physical validation partition required')


def prepare():
    summary=read(ROOT/'reports/positive_cohort_test_summary.json');source=Path(summary['run_path'])
    if file_hash(source/'test_results.csv')!=summary['results_csv_sha256']: raise ValueError('Saved tests changed')
    with (source/'test_results.csv').open(encoding='utf-8',newline='') as stream:
        rows=[r for r in csv.DictReader(stream) if r['user_test_checks_pass']=='True']
    rows.sort(key=lambda r:(-float(r['test_net']),max(float(r[k]) for k in ('test_cash_dd','test_closing_dd','test_intrabar_dd')),r['config_id']))
    if rows[0]['config_id']!=ID: raise ValueError('Displayed #1 identity changed')
    cohort=read(source/'frozen_cohort.json')['candidate']
    candidate=next(c for c in cohort['cohort'] if c['config_id']==ID)
    test=read(source/'results'/(ID+'.json'))
    if test['parameters']!=candidate['parameters']: raise ValueError('Saved test parameters differ')
    if code_identity()['source_hash']!=cohort['core_source_hash']: raise ValueError('Core changed')
    partition=read(ROOT/'data/catalog.json')['instruments']['MNQ']['splits']['validation']
    meta=read(Path(partition['path']).with_suffix('.manifest.json'));check_metadata(meta)
    if meta['dataset_version']!=partition['dataset_version']: raise ValueError('Validation metadata changed')
    DIRECTORY.mkdir(exist_ok=False)
    shutil.copytree(source/'strategy',DIRECTORY/'strategy')
    shutil.copyfile(__file__,DIRECTORY/'validation_runner.py')
    preserved=[source/'test_results.csv',source/'frozen_cohort.json',source/'results'/(ID+'.json'),
        source/'curves'/(ID+'.parquet'),source/'trades'/(ID+'.parquet'),ROOT/'reports/positive_cohort_test_summary.json']
    for kind in ('final_tests','reused_tests','validation_once'):
        preserved+=list((ROOT/'data/manifests'/kind).glob('*.json'))
    frozen=dict(candidate_id=ID,parameters=candidate['parameters'],source_training_candidate=candidate,
        saved_test_result=str(source/'results'/(ID+'.json')),source_test_display_row=rows[0],
        strategy_hashes=cohort['strategy_hashes'],core_source_hash=cohort['core_source_hash'],
        runner_sha256=file_hash(__file__),validation_partition=partition,metadata=meta,
        preserved_files={str(p):file_hash(p) for p in preserved},created_at=now(),
        user_authorization='Show the number1 strategy results on validation WITHOUT TUNING ON IT',
        selection='Highest recorded test net in the already displayed top100 list; selected before validation access. Not an independently training-selected finalist.',
        protocol='One unchanged configuration and base-cost replay over existing MNQ2024-2025 validation, single continuous50k account, frozen complete15m aggregation/features/execution/risk, first96/last16 entry suppression. No training, fitting, parameter changes, validation-guided alternatives or test replay. Warmup within validation only.',
        validation_previously_observed=True,test_selected=True,independent_confirmation=False,
        operational_eligibility=False,failure_consumes_reservation=True)
    json_write(DIRECTORY/'frozen_candidate.json',dict(candidate=frozen,candidate_hash=digest(frozen)))
    print(json.dumps(dict(prepared=True,candidate_id=ID,validation_prices_opened=False,test_replayed=False)))


def verify():
    manifest=read(DIRECTORY/'frozen_candidate.json');frozen=manifest['candidate']
    if digest(frozen)!=manifest['candidate_hash'] or frozen['candidate_id']!=ID: raise ValueError('Candidate freeze changed')
    if file_hash(__file__)!=frozen['runner_sha256'] or file_hash(DIRECTORY/'validation_runner.py')!=frozen['runner_sha256']:
        raise ValueError('Runner changed')
    if code_identity()['source_hash']!=frozen['core_source_hash']: raise ValueError('Core changed')
    for name,expected in frozen['strategy_hashes'].items():
        if file_hash(DIRECTORY/'strategy'/name)!=expected: raise ValueError('Strategy changed')
    for path,expected in frozen['preserved_files'].items():
        if file_hash(path)!=expected: raise ValueError('Prior artifact changed')
    return manifest,frozen


def reserve(manifest,frozen):
    key=digest(dict(candidate_id=ID,parameters=frozen['parameters'],dataset_version=frozen['validation_partition']['dataset_version']))
    path=ROOT/'data/manifests/validation_once'/(key+'.json');path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:
        json.dump(dict(candidate_id=ID,candidate_hash=manifest['candidate_hash'],reserved_at=now(),
            dataset_version=frozen['validation_partition']['dataset_version'],no_tuning=True,
            failure_consumes_attempt=True,period_previously_observed=True,test_selected=True,independent_confirmation=False),stream,indent=2)
    return path


def archive():
    sys.path.insert(0,str(DIRECTORY/'strategy'))
    spec=importlib.util.spec_from_file_location('validation_frozen_engine',DIRECTORY/'strategy/mass_research.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def load_validation(frozen):
    partition=frozen['validation_partition'];path=Path(partition['path']);check_metadata(frozen['metadata'])
    if file_hash(path)!=partition['dataset_version']: raise ValueError('Validation source bytes changed')
    tree=ast.parse((DIRECTORY/'strategy/mass_research.py').read_text(encoding='utf-8'))
    queries=[n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value.startswith('SELECT time_bucket')]
    if len(queries)!=1: raise ValueError('Frozen aggregation query missing')
    import duckdb
    db=duckdb.connect()
    try:
        db.execute('SET threads=1');db.execute("SET memory_limit='256MB'");db.execute('SET enable_progress_bar=false')
        bars=canonical(db.execute(queries[0],[str(path)]).fetch_df())
    finally: db.close()
    _,quality=validate(bars,minutes=15)
    if quality['fatal'] or bars.timestamp_utc.duplicated().any() or not bars.instrument.eq('MNQ').all(): raise ValueError('Invalid validation bars')
    if not (bars.timestamp_utc.ge(pd.Timestamp('2024-01-01T00:00Z')).all() and bars.timestamp_utc.lt(pd.Timestamp('2026-01-01T00:00Z')).all()):
        raise PermissionError('Validation boundary violation')
    return bars


def evaluate():
    manifest,frozen=verify();reservation=reserve(manifest,frozen)
    json_write(DIRECTORY/'evaluation_state.json',dict(state='reserved; failed attempt also consumed'))
    engine=archive();bars=load_validation(frozen);c=frozen['parameters']
    data=engine.arrays(bars);features=engine.features(bars,c['lookback']);signal=engine.masked_signal(bars,c,features)
    fold=dict(label='validation2024_2025',start=0,stop=len(bars),embargo_bars=96,purge_bars=16)
    metrics=engine.evaluate_configuration(c,bars,data,[fold],features,signal,save=True,folder=DIRECTORY)[0]
    checks=dict(positive_net=metrics['net_pnl']>0,realized_drawdown_under_2000=metrics['realized_drawdown']<2000,
        closing_drawdown_under_2000=metrics['max_drawdown']<2000,intrabar_drawdown_under_2000=metrics['intrabar_drawdown']<2000,
        minimum30_trades=metrics['trades']>=30,consistency50=metrics['consistency_50_pass'],
        no_permanent_lock=not metrics['killed'],no_funded_scenario_breach=not metrics['funded_failed'])
    verify()
    result=dict(path=str(DIRECTORY),candidate_id=ID,parameters=c,metrics=metrics,checks=checks,
        scenario_checks_pass=all(checks.values()),frozen_candidate_hash=manifest['candidate_hash'],
        reservation=str(reservation),validation_dataset_version=frozen['validation_partition']['dataset_version'],
        source_coverage=frozen['metadata']['coverage'],complete15m_bars=len(bars),
        curve_file=ID+'_validation2024_2025_equity.parquet',trade_file=ID+'_validation2024_2025_trades.parquet',
        no_tuning=True,parameter_variants_evaluated=1,cost_variants_evaluated=1,test_replayed=False,
        test_selected=True,validation_previously_observed=True,independent_confirmation=False,
        prior_artifacts_preserved=True,operational_eligibility=False,completed_at=now())
    pd.read_parquet(DIRECTORY/result['trade_file']).to_csv(DIRECTORY/'validation_trades.csv',index=False)
    json_write(DIRECTORY/'validation_result.json',result)
    json_write(ROOT/'reports/top_test_number1_validation.json',result)
    json_write(DIRECTORY/'evaluation_state.json',dict(state='completed; no tuning'))
    print(json.dumps(dict(candidate_id=ID,metrics={k:metrics[k] for k in ('net_pnl','realized_drawdown','max_drawdown','intrabar_drawdown','trades')},checks=checks),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare',action='store_true');group.add_argument('--evaluate',action='store_true')
    args=parser.parse_args()
    with threadpool_limits(limits=1): prepare() if args.prepare else evaluate()

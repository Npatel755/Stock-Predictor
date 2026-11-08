"""One frozen v1.2.0 evaluation on validation then test, with zero tuning."""
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
from datetime import datetime,timezone
import pandas as pd
from threadpoolctl import threadpool_limits
from quant_futures.config import file_hash,digest
from quant_futures.research import code_identity,json_write

ROOT=Path(__file__).resolve().parents[1]
VERSION=ROOT/'strategy_versions/mnq_momentum_e57/v1.2.0-risk-profit-research'
DIRECTORY=ROOT/'runs/e57_refined_validation_test_v1'
ID='e57_f62b1be4cfe9edf434d8'
DD_FIELDS=('realized_drawdown','max_drawdown','intrabar_drawdown')


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def now():return datetime.now(timezone.utc).isoformat()


def prepare():
    if (DIRECTORY/'frozen_candidate.json').exists():verify();print(json.dumps(dict(already_frozen=True)));return
    version=read(VERSION/'candidate.json');inventory=read(VERSION/'manifest.json')
    if version['strategy_id']!=ID or digest(version['parameters'])!=version['parameter_hash']:raise ValueError('Refined version identity mismatch')
    for rel,expected in inventory['files'].items():
        if file_hash(VERSION/rel)!=expected:raise ValueError('Immutable refined version changed')
    if code_identity()['source_hash']!=version['core_source_hash']:raise ValueError('Core differs from saved version')
    catalog=read(ROOT/'data/catalog.json');partitions={}
    for phase in ('validation','test'):
        p=catalog['instruments']['MNQ']['splits'][phase];m=read(Path(p['path']).with_suffix('.manifest.json'))
        if m.get('split_role')!=phase or m.get('instrument')!='MNQ' or m.get('synthetic') is not False or m.get('raw_contract_prices') is not True or m['dataset_version']!=p['dataset_version']:
            raise PermissionError('Actual matching physical MNQ partition required')
        partitions[phase]=dict(partition=p,metadata=m)
    DIRECTORY.mkdir(exist_ok=False)
    shutil.copytree(VERSION/'code',DIRECTORY/'strategy')
    shutil.copyfile(__file__,DIRECTORY/'evaluation_runner.py')
    helper=ROOT/'scripts/evaluate_saved_50k_candidate.py';shutil.copyfile(helper,DIRECTORY/'split_loader.py')
    frozen=dict(candidate_id=ID,version=version['version'],parameters=version['parameters'],expected_execution_config=version['execution_config'],phase_policy=version['phase_policy'],partitions=partitions,
        authorization='User requests the refined v1.2.0 on validation and test WITHOUT TUNING. Both stages explicitly authorized, regardless of validation outcome.',
        protocol='One base-cost execution per split, one continuous50k account per split. Same frozen signal, exits, position/risk, costs, phase policy and scoped risk adapter as training. Split-local warmup, first96/last16 entry suppression. Complete validation before test; record/verify validation hash before test price access. No variants, fitting, reselection or optimization. Failures consume reservation; completed results reused on restart, never replayed.',
        source_hashes=version['source_hashes'],core_source_hash=version['core_source_hash'],runner_sha256=file_hash(__file__),loader_sha256=file_hash(helper),
        preserved_version_files={str(VERSION/rel):expected for rel,expected in inventory['files'].items()},version_manifest_sha256=file_hash(VERSION/'manifest.json'),
        created_at=now(),period_previously_observed=True,inherited_selection='Original parent selected after prior holdout outcomes; refined version selected with TRAIN only. Old periods remain consumed, not independent confirmation.',independent_confirmation=False,operational_eligibility=False)
    manifest=dict(candidate=frozen,candidate_hash=digest(frozen));json_write(DIRECTORY/'frozen_candidate.json',manifest)
    print(json.dumps(dict(candidate_id=ID,version=version['version'],frozen_candidate_hash=manifest['candidate_hash'],validation_prices_opened=False,test_prices_opened=False)))


def verify():
    manifest=read(DIRECTORY/'frozen_candidate.json');frozen=manifest['candidate']
    if digest(frozen)!=manifest['candidate_hash'] or frozen['candidate_id']!=ID:raise ValueError('Frozen candidate changed')
    if file_hash(__file__)!=frozen['runner_sha256'] or file_hash(DIRECTORY/'evaluation_runner.py')!=frozen['runner_sha256'] or file_hash(DIRECTORY/'split_loader.py')!=frozen['loader_sha256']:raise ValueError('Frozen runner/loader changed')
    if code_identity()['source_hash']!=frozen['core_source_hash']:raise ValueError('Core simulator changed')
    for name,expected in frozen['source_hashes'].items():
        if file_hash(DIRECTORY/'strategy'/name)!=expected:raise ValueError('Frozen strategy dependency changed')
    for path,expected in frozen['preserved_version_files'].items():
        if file_hash(path)!=expected:raise ValueError('Immutable source version changed')
    if file_hash(VERSION/'manifest.json')!=frozen['version_manifest_sha256']:raise ValueError('Version manifest changed')
    return manifest,frozen


def reserve(phase,manifest,frozen):
    if phase not in ('validation','test'):raise PermissionError('Unsupported phase')
    previous=None
    if phase=='test':
        result=read(DIRECTORY/'validation_result.json');complete=read(DIRECTORY/'validation_complete.json')
        previous=file_hash(DIRECTORY/'validation_result.json')
        if result['frozen_candidate_hash']!=manifest['candidate_hash'] or result['parameters']!=frozen['parameters'] or complete['result_sha256']!=previous:
            raise ValueError('Exact frozen validation must finish before test')
    version=frozen['partitions'][phase]['partition']['dataset_version']
    key=digest(dict(candidate_id=ID,parameters=frozen['parameters'],dataset_version=version))
    role='validation_once' if phase=='validation' else 'reused_tests'
    path=ROOT/'data/manifests'/role/(key+'.json');path.parent.mkdir(exist_ok=True,parents=True)
    record=dict(candidate_id=ID,parameters=frozen['parameters'],phase=phase,frozen_candidate_hash=manifest['candidate_hash'],dataset_version=version,reserved_at=now(),parameter_variants=1,cost_variants=1,no_tuning=True,failure_consumes_reservation=True,period_previously_observed=True,independent_confirmation=False,validation_result_sha256=previous)
    with path.open('x',encoding='utf-8') as stream:json.dump(record,stream,indent=2)
    return path,previous


def helpers():
    spec=importlib.util.spec_from_file_location('refined_frozen_loader',DIRECTORY/'split_loader.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    helper.DIRECTORY=DIRECTORY;engine=helper.archive()
    spec=importlib.util.spec_from_file_location('refined_frozen_risk_adapter',DIRECTORY/'strategy/e57_refinement_parameters.py');adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
    return helper,engine,adapter


def evaluate(phase):
    manifest,frozen=verify();result_path=DIRECTORY/(phase+'_result.json');complete_path=DIRECTORY/(phase+'_complete.json')
    if complete_path.exists():
        receipt=read(complete_path)
        if receipt['frozen_candidate_hash']!=manifest['candidate_hash'] or receipt['result_sha256']!=file_hash(result_path):raise ValueError('Completed result changed')
        print(json.dumps(dict(phase=phase,already_complete=True,no_replay=True)));return
    # Match the exact frozen execution config BEFORE a single split price is loaded.
    helper,engine,adapter=helpers();c=frozen['parameters']
    if adapter.scaled_cfg(engine.execution_cfg(c),c)!=frozen['expected_execution_config']:raise ValueError('Execution settings differ from saved version')
    reservation,previous=reserve(phase,manifest,frozen)
    bars=helper.load_split(phase,frozen);data=engine.arrays(bars);features=engine.features(bars,c['lookback']);signal=engine.masked_signal(bars,c,features)
    fold=dict(label=phase,start=0,stop=len(bars),embargo_bars=96,purge_bars=16)
    with adapter.execution_scope(engine):m=engine.evaluate_configuration(c,bars,data,[fold],features,signal,save=True,folder=DIRECTORY)[0]
    checks=dict(positive_net=m['net_pnl']>0,**{k+'_under_2000':m[k]<2000 for k in DD_FIELDS},minimum30_trades=m['trades']>=30,no_permanent_lock=not m['killed'],no_funded_scenario_breach=not m['funded_failed'])
    record=dict(candidate_id=ID,version=frozen['version'],parameters=c,phase=phase,metrics=m,checks=checks,profit_and_dd_pass=bool(checks['positive_net'] and all(checks[k+'_under_2000'] for k in DD_FIELDS)),post_evaluation_scenario_checks_pass=all(checks.values()),evaluation_phase_checks_pass=all(checks.values()) and m['consistency_50_pass'],frozen_candidate_hash=manifest['candidate_hash'],reservation=str(reservation),curve_file=ID+'_'+phase+'_equity.parquet',trade_file=ID+'_'+phase+'_trades.parquet',no_tuning=True,parameter_variants_evaluated=1,cost_variants_evaluated=1,source_coverage=frozen['partitions'][phase]['metadata']['coverage'],period_previously_observed=True,independent_confirmation=False,completed_at=now())
    verify()
    if phase=='test' and previous!=file_hash(DIRECTORY/'validation_result.json'):raise ValueError('Validation changed during test')
    if result_path.exists():raise FileExistsError('Refuse result overwrite')
    json_write(result_path,record)
    pd.read_parquet(DIRECTORY/record['trade_file']).to_csv(DIRECTORY/(phase+'_trades.csv'),index=False)
    json_write(complete_path,dict(frozen_candidate_hash=manifest['candidate_hash'],result_sha256=file_hash(result_path),completed_at=now()))
    print(json.dumps(dict(phase=phase,metrics={k:m[k] for k in ('net_pnl',*DD_FIELDS,'trades','consistency','lock')},checks=checks),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);mode=p.add_mutually_exclusive_group(required=True);mode.add_argument('--prepare',action='store_true');mode.add_argument('--validation',action='store_true');mode.add_argument('--test',action='store_true');a=p.parse_args()
    with threadpool_limits(limits=1):
        if a.prepare:prepare()
        else:evaluate('validation' if a.validation else 'test')

"""Save the requested training-profit leader; validate then test without tuning."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'): os.environ[key]='1'
import argparse
import ast
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import pandas as pd
from threadpoolctl import threadpool_limits
from quant_futures.config import file_hash,digest
from quant_futures.data import canonical,validate
from quant_futures.research import json_write,code_identity
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
ID='mass_ca28dbb9316d2d9ced10'
DIRECTORY=ROOT/'runs'/('saved_50k_candidate_'+ID)


def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def now(): return datetime.now(timezone.utc).isoformat()


def prepare():
    result=read(ROOT/'reports/training_search_50k_result.json');source=Path(result['run_path'])
    protocol=read(source/'protocol.json');saved=read(source/'highest_base_profit_candidate.json')
    candidate=saved['candidate']
    if candidate['config_id']!=ID or candidate!=result['top10'][0] or candidate['net_pnl']!=9972.5:
        raise ValueError('Requested training-profit candidate changed')
    if code_identity()['source_hash']!=protocol['source_hash']: raise ValueError('Core differs from training')
    for name,expected in protocol['source_hashes'].items():
        if file_hash(source/'code'/name)!=expected: raise ValueError('Frozen training source changed')
    catalog=read(ROOT/'data/catalog.json');partitions={}
    for phase in ('validation','test'):
        partition=catalog['instruments']['MNQ']['splits'][phase]
        meta=read(Path(partition['path']).with_suffix('.manifest.json'))
        check_meta(meta,phase)
        if meta['dataset_version']!=partition['dataset_version']: raise ValueError('Partition identity differs')
        partitions[phase]=dict(partition=partition,metadata=meta)
    DIRECTORY.mkdir(exist_ok=False)
    shutil.copytree(source/'code',DIRECTORY/'strategy');shutil.copyfile(__file__,DIRECTORY/'evaluation_runner.py')
    policy=dict(consistency_fraction=.5,applies_to_account_phases=['evaluation'],
        source='User instruction2026-11-07',contract_terms_independently_verified=False,
        data_split_is_not_account_phase=True,execution_changed=False,
        note='Keep consistency as a diagnostic on every data split; apply it only to evaluation-phase qualification. No entry, exit, sizing, cost or risk change.')
    preserved={str(source/name):file_hash(source/name) for name in ('protocol.json','ranked.csv','results.json','highest_base_profit_candidate.json','configurations.jsonl')}
    for role in ('final_tests','reused_tests','validation_once'):
        for p in (ROOT/'data/manifests'/role).glob('*.json'): preserved[str(p)]=file_hash(p)
    frozen=dict(candidate_id=ID,parameters=candidate['parameters'],training_candidate=candidate,
        training_cost_stress=saved['stress_2x'],source_hashes=protocol['source_hashes'],core_source_hash=protocol['source_hash'],
        runner_sha256=file_hash(__file__),partitions=partitions,preserved_files=preserved,phase_policy=policy,
        authorization='Save the$9972.50 candidate;50% consistency only during account evaluation phase; evaluate validation then test WITHOUT tuning.',
        protocol='One unchanged configuration, one base-cost continuous50k account per split. Same complete15m aggregation/features/next-open fills/costs/risk limits and first96/last16 entry suppression. Validation first, then the identical test configuration regardless of validation P&L; no fitting, optimization, variants or reselection. Warmup within each split only.',
        created_at=now(),selected_using_training_only=True,periods_previously_observed=True,
        independent_confirmation=False,operational_eligibility=False,failure_consumes_reservation=True)
    manifest=dict(candidate=frozen,candidate_hash=digest(frozen))
    json_write(DIRECTORY/'frozen_candidate.json',manifest)
    saved_folder=ROOT/'reports/saved_training_candidates'/ID;saved_folder.mkdir(parents=True,exist_ok=False)
    json_write(saved_folder/'candidate.json',manifest)
    json_write(ROOT/'configs/user_account_phase_policy.json',policy)
    print(json.dumps(dict(saved=str(saved_folder/'candidate.json'),candidate_id=ID,validation_prices_opened=False,test_prices_opened=False)))


def check_meta(meta,phase):
    if phase not in ('validation','test') or (meta.get('split_role')!=phase or meta.get('instrument')!='MNQ'
            or meta.get('synthetic') is not False or meta.get('raw_contract_prices') is not True):
        raise PermissionError('Actual matching MNQ physical split required')


def verify():
    manifest=read(DIRECTORY/'frozen_candidate.json');frozen=manifest['candidate']
    if digest(frozen)!=manifest['candidate_hash'] or frozen['candidate_id']!=ID: raise ValueError('Saved candidate changed')
    if file_hash(__file__)!=frozen['runner_sha256'] or file_hash(DIRECTORY/'evaluation_runner.py')!=frozen['runner_sha256']:
        raise ValueError('Frozen runner changed')
    if code_identity()['source_hash']!=frozen['core_source_hash']: raise ValueError('Core changed')
    for name,expected in frozen['source_hashes'].items():
        if file_hash(DIRECTORY/'strategy'/name)!=expected: raise ValueError('Frozen source changed')
    for path,expected in frozen['preserved_files'].items():
        if file_hash(path)!=expected: raise ValueError('Prior artifact changed')
    if read(ROOT/'reports/saved_training_candidates'/ID/'candidate.json')!=manifest: raise ValueError('Saved copy changed')
    return manifest,frozen


def reserve(phase,manifest,frozen):
    if phase=='test':
        previous=read(DIRECTORY/'validation_result.json')
        if previous['frozen_candidate_hash']!=manifest['candidate_hash'] or previous['parameters']!=frozen['parameters']:
            raise ValueError('Validation must finish on the exact frozen version first')
    partition=frozen['partitions'][phase]['partition']
    key=digest(dict(candidate_id=ID,parameters=frozen['parameters'],dataset_version=partition['dataset_version']))
    role='validation_once' if phase=='validation' else 'reused_tests'
    path=ROOT/'data/manifests'/role/(key+'.json');path.parent.mkdir(parents=True,exist_ok=True)
    record=dict(candidate_id=ID,candidate_hash=manifest['candidate_hash'],phase=phase,reserved_at=now(),
        dataset_version=partition['dataset_version'],no_tuning=True,parameter_variants=1,cost_variants=1,
        failure_consumes_reservation=True,period_previously_observed=True,independent_confirmation=False)
    if phase=='test': record['validation_result_sha256']=file_hash(DIRECTORY/'validation_result.json')
    with path.open('x',encoding='utf-8') as stream: json.dump(record,stream,indent=2)
    return path


def archive():
    sys.path.insert(0,str(DIRECTORY/'strategy'))
    spec=importlib.util.spec_from_file_location('saved_candidate_frozen_engine',DIRECTORY/'strategy/mass_research.py')
    engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
    return engine


def load_split(phase,frozen):
    item=frozen['partitions'][phase];check_meta(item['metadata'],phase);path=Path(item['partition']['path'])
    if file_hash(path)!=item['partition']['dataset_version']: raise ValueError('Market source changed')
    tree=ast.parse((DIRECTORY/'strategy/mass_research.py').read_text(encoding='utf-8'))
    query=[n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value.startswith('SELECT time_bucket')]
    if len(query)!=1: raise ValueError('Frozen complete-bar query missing')
    import duckdb
    db=duckdb.connect()
    try:
        db.execute('SET threads=1');db.execute("SET memory_limit='256MB'");db.execute('SET enable_progress_bar=false')
        bars=canonical(db.execute(query[0],[str(path)]).fetch_df())
    finally: db.close()
    _,quality=validate(bars,minutes=15)
    left,right=('2024-01-01T00:00Z','2026-01-01T00:00Z') if phase=='validation' else ('2026-01-01T00:00Z','2027-01-01T00:00Z')
    if quality['fatal'] or bars.timestamp_utc.duplicated().any() or not bars.instrument.eq('MNQ').all(): raise ValueError('Invalid split bars')
    if not (bars.timestamp_utc.ge(pd.Timestamp(left)).all() and bars.timestamp_utc.lt(pd.Timestamp(right)).all()):
        raise PermissionError('Split boundaries crossed')
    return bars


def evaluate(phase):
    manifest,frozen=verify();reservation=reserve(phase,manifest,frozen)
    json_write(DIRECTORY/(phase+'_state.json'),dict(state='reserved; failure also consumes version'))
    engine=archive();bars=load_split(phase,frozen);c=frozen['parameters']
    data=engine.arrays(bars);features=engine.features(bars,c['lookback']);signal=engine.masked_signal(bars,c,features)
    fold=dict(label=phase,start=0,stop=len(bars),embargo_bars=96,purge_bars=16)
    m=engine.evaluate_configuration(c,bars,data,[fold],features,signal,save=True,folder=DIRECTORY)[0]
    checks=dict(positive_net=m['net_pnl']>0,closing_dd_under_2000=m['max_drawdown']<2000,
        cash_dd_under_2000=m['realized_drawdown']<2000,intrabar_dd_under_2000=m['intrabar_drawdown']<2000,
        minimum30_trades=m['trades']>=30,no_permanent_lock=not m['killed'],no_funded_scenario_breach=not m['funded_failed'])
    record=dict(candidate_id=ID,parameters=c,phase=phase,metrics=m,checks=checks,
        profit_and_dd_pass=all(checks[k] for k in ('positive_net','closing_dd_under_2000','cash_dd_under_2000','intrabar_dd_under_2000')),
        evaluation_phase_checks_pass=all(checks.values()) and m['consistency_50_pass'],
        post_evaluation_scenario_checks_pass=all(checks.values()),consistency_50_pass=m['consistency_50_pass'],
        phase_policy=frozen['phase_policy'],frozen_candidate_hash=manifest['candidate_hash'],reservation=str(reservation),
        path=str(DIRECTORY),curve_file=ID+'_'+phase+'_equity.parquet',trade_file=ID+'_'+phase+'_trades.parquet',
        source_coverage=frozen['partitions'][phase]['metadata']['coverage'],
        no_tuning=True,parameter_variants_evaluated=1,cost_variants_evaluated=1,period_previously_observed=True,
        independent_confirmation=False,operational_eligibility=False,completed_at=now())
    verify()
    if phase=='test' and read(reservation)['validation_result_sha256']!=file_hash(DIRECTORY/'validation_result.json'):
        raise ValueError('Validation result changed before test finished')
    json_write(DIRECTORY/(phase+'_result.json'),record)
    json_write(ROOT/'reports'/('saved_50k_candidate_'+phase+'.json'),record)
    pd.read_parquet(DIRECTORY/record['trade_file']).to_csv(DIRECTORY/(phase+'_trades.csv'),index=False)
    json_write(DIRECTORY/(phase+'_state.json'),dict(state='complete; no tuning'))
    print(json.dumps(dict(phase=phase,candidate_id=ID,metrics={k:m[k] for k in ('net_pnl','realized_drawdown','max_drawdown','intrabar_drawdown','trades','consistency','lock')},checks=checks),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare',action='store_true');mode.add_argument('--validation',action='store_true');mode.add_argument('--test',action='store_true')
    args=parser.parse_args()
    with threadpool_limits(limits=1):
        if args.prepare: prepare()
        else: evaluate('validation' if args.validation else 'test')

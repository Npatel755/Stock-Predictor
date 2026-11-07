"""Frozen user-requested test diagnostic for every positive low-DD training case.

Each fixed candidate receives one base-cost replay. The full cohort is frozen
before price access. SQLite marks attempts before execution; interrupted or
failed attempts are consumed, never silently repeated. Existing tests are read
from their immutable records and not rerun.
"""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'): os.environ[key]='1'
import argparse
import ast
import csv
from collections import Counter
import gc
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
from itertools import groupby
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from quant_futures.config import digest,file_hash
from quant_futures.data import canonical,validate
from quant_futures.research import code_identity,json_write
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
DIRECTORY=ROOT/'runs/positive_training_cohort_test_v1'
PRIOR=('mass_training_v2','mass_training_continuation_v1')
CACHED_ID='mass_85721bb33e324b248878'
CACHED=ROOT/'reports/mass_best_reused_test.json'
DD_KEYS=('max_drawdown','realized_drawdown','intrabar_drawdown')
FIELDS=('training_order','config_id','instrument','family','training_source','source_rank','training_net',
    'training_cash_dd','training_closing_dd','training_intrabar_dd','full_training_qualified','status',
    'test_net','test_cash_dd','test_closing_dd','test_intrabar_dd','test_trades','test_profit_factor',
    'test_expectancy','test_consistency','positive_test_net','test_dd_under_2000','user_test_checks_pass',
    'full_test_scenario_checks_pass','test_lock','test_funded_failed','result_path','error')


def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def now(): return datetime.now(timezone.utc).isoformat()


def eligible(row):
    return float(row['net_pnl'])>0 and max(float(row[k]) for k in DD_KEYS)<2000


def collect_cohort():
    cohort=[];identities={}
    for name in PRIOR:
        folder=ROOT/'runs'/name
        protocol=read(folder/'protocol.json')
        if code_identity()['source_hash']!=protocol['source_hash']: raise ValueError('Core differs from training')
        identities[name]=dict(protocol_sha256=file_hash(folder/'protocol.json'),ranked_sha256=file_hash(folder/'ranked.csv'))
        with (folder/'ranked.csv').open(encoding='utf-8',newline='') as stream:
            for row in csv.DictReader(stream):
                if eligible(row):
                    cohort.append(dict(config_id=row['config_id'],instrument=row['instrument'],family=row['family'],
                        training_source=name,source_rank=int(row['rank']),score=float(row['score']),
                        training_net=float(row['net_pnl']),training_cash_dd=float(row['realized_drawdown']),
                        training_closing_dd=float(row['max_drawdown']),training_intrabar_dd=float(row['intrabar_drawdown']),
                        full_training_qualified=row['qualified']=='True',parameters=json.loads(row['parameters'])))
    cohort.sort(key=lambda c:(c['score'],c['config_id']),reverse=True)
    if len({c['config_id'] for c in cohort})!=len(cohort): raise ValueError('Repeated candidate')
    for i,c in enumerate(cohort,1): c['training_order']=i
    return cohort,identities


def reservation_key(c,dataset_version):
    return digest(dict(candidate_id=c['config_id'],parameters=c['parameters'],dataset_version=dataset_version))


def prepare():
    cohort,training=collect_cohort()
    catalog=read(ROOT/'data/catalog.json')
    partitions={}
    for symbol in sorted({c['instrument'] for c in cohort}):
        partition=catalog['instruments'][symbol]['splits']['test']
        meta=read(Path(partition['path']).with_suffix('.manifest.json'))
        if (meta['split_role']!='test' or meta['instrument']!=symbol or meta['dataset_version']!=partition['dataset_version']
                or meta['synthetic'] is not False or meta['raw_contract_prices'] is not True):
            raise ValueError('Actual matching physical test metadata required')
        partitions[symbol]=dict(partition=partition,metadata=meta)
    cached=read(CACHED)
    cached_case=next(c for c in cohort if c['config_id']==CACHED_ID)
    if (cached['parameters']!=cached_case['parameters'] or cached['parameter_variants_evaluated']!=1
            or cached['cost_variants_evaluated']!=1 or cached['test_dataset_version']!=partitions['MNQ']['partition']['dataset_version']):
        raise ValueError('Existing cached test is not the identical case')
    for c in cohort:
        key=reservation_key(c,partitions[c['instrument']]['partition']['dataset_version'])
        reservation=ROOT/'data/manifests/reused_tests'/(key+'.json')
        if reservation.exists() and c['config_id']!=CACHED_ID:
            raise FileExistsError('Prior attempt exists without a known complete saved result: '+c['config_id'])
    source=ROOT/'runs/mass_training_v2'
    protocol=read(source/'protocol.json')
    if cached['source_hashes']!=protocol['source_hashes']: raise ValueError('Cached test execution version differs')
    for name,expected in protocol['source_hashes'].items():
        if file_hash(source/'code'/name)!=expected: raise ValueError('Frozen training engine changed')
    DIRECTORY.mkdir(exist_ok=False)
    shutil.copytree(source/'code',DIRECTORY/'strategy')
    shutil.copyfile(__file__,DIRECTORY/'test_runner.py')
    for name in ('curves','trades','results','cache'): (DIRECTORY/name).mkdir()
    preserved={str(CACHED):file_hash(CACHED)}
    for name in PRIOR:
        for filename in ('protocol.json','ranked.csv','frozen_top10.json','results.json'):
            p=ROOT/'runs'/name/filename;preserved[str(p)]=file_hash(p)
    for kind in ('final_tests','reused_tests','validation_once'):
        for p in (ROOT/'data/manifests'/kind).glob('*.json'): preserved[str(p)]=file_hash(p)
    frozen=dict(created_at=now(),cohort=cohort,target=len(cohort),training_identities=training,
        strategy_hashes=protocol['source_hashes'],core_source_hash=protocol['source_hash'],
        runner_sha256=file_hash(__file__),partitions=partitions,preserved_files=preserved,
        cached_result_path=str(CACHED),cached_candidate_id=CACHED_ID,
        eligibility='Across both completed20k batches: aggregate training net>0 and maximum closing/cash/intrabar fold DD strictly<2000. No minimum trade, consistency, per-fold positivity or other gate added.',
        ordering='Descending frozen training score, then candidate ID; no test-based ranking or final-strategy selection.',
        authorization='User explicitly requests everything with positive P&L and under the drawdown limit be tested WITHOUT TUNING.',
        evaluation='Each unchanged configuration: one continuous50k account on its existing2026 test partition, original complete15m bars, costs, next-open execution, risk limits, first96/last16 entry suppression. No validation warmup, fitting, variants, optimization or feedback.',
        ledger_verification='Every trade arithmetic; up to5 evenly spaced independent shared-simulator trade samples per newly evaluated case. These are verification replays of identical trades, not parameter variants.',
        test_case_counts='One existing result reused; all remaining cases attempted once. Interrupted or failed attempts consumed, reported, not rerun.',
        period_previously_consumed=True,independent_confirmation=False,validation_accessed=False,
        no_tuning=True,parameter_variants_per_candidate=1,cost_variants_per_candidate=1,
        embargo_bars=96,purge_bars=16,operational_eligibility=False)
    json_write(DIRECTORY/'frozen_cohort.json',dict(candidate=frozen,candidate_hash=digest(frozen)))
    print(json.dumps(dict(prepared=True,target=len(cohort),cached=1,new_evaluations=len(cohort)-1,
        by_market=dict(Counter(c['instrument'] for c in cohort)),test_prices_opened=False)))


def verify():
    manifest=read(DIRECTORY/'frozen_cohort.json');frozen=manifest['candidate']
    if digest(frozen)!=manifest['candidate_hash']: raise ValueError('Frozen cohort changed')
    if file_hash(__file__)!=frozen['runner_sha256'] or file_hash(DIRECTORY/'test_runner.py')!=frozen['runner_sha256']:
        raise ValueError('Frozen runner changed')
    if code_identity()['source_hash']!=frozen['core_source_hash']: raise ValueError('Core changed')
    for name,expected in frozen['strategy_hashes'].items():
        if file_hash(DIRECTORY/'strategy'/name)!=expected: raise ValueError('Strategy changed')
    for path,expected in frozen['preserved_files'].items():
        if file_hash(path)!=expected: raise ValueError('Prior artifact changed: '+path)
    return manifest,frozen


def reserve_all(manifest,frozen):
    global_path=DIRECTORY/'reservation.json'
    if global_path.exists():
        if read(global_path)['cohort_hash']!=manifest['candidate_hash']: raise ValueError('Reservation changed')
    else:
        with global_path.open('x',encoding='utf-8') as stream:
            json.dump(dict(cohort_hash=manifest['candidate_hash'],reserved_at=now(),no_tuning=True),stream)
    for c in frozen['cohort']:
        if c['config_id']==frozen['cached_candidate_id']: continue
        key=reservation_key(c,frozen['partitions'][c['instrument']]['partition']['dataset_version'])
        p=ROOT/'data/manifests/reused_tests'/(key+'.json')
        if p.exists():
            if read(p).get('cohort_hash')!=manifest['candidate_hash']: raise FileExistsError('Candidate reserved elsewhere')
        else:
            with p.open('x',encoding='utf-8') as stream:
                json.dump(dict(candidate_id=c['config_id'],cohort_hash=manifest['candidate_hash'],reserved_at=now(),
                    dataset_version=frozen['partitions'][c['instrument']]['partition']['dataset_version'],
                    state='reserved for this frozen batch; execution state in SQLite',
                    failure_consumes_attempt=True,no_tuning=True,parameter_variants=1,cost_variants=1,
                    period_previously_consumed=True,independent_confirmation=False),stream)


def archive():
    sys.path.insert(0,str(DIRECTORY/'strategy'))
    spec=importlib.util.spec_from_file_location('cohort_frozen_engine',DIRECTORY/'strategy/mass_research.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def load_test(symbol,frozen):
    item=frozen['partitions'][symbol];source=Path(item['partition']['path'])
    if file_hash(source)!=item['partition']['dataset_version']: raise ValueError('Test source changed')
    target=DIRECTORY/'cache'/(symbol+'_15m.parquet')
    if target.exists():
        meta=read(target.with_suffix('.json'))
        if meta['source_sha256']!=item['partition']['dataset_version'] or file_hash(target)!=meta['cache_sha256']:
            raise ValueError('Test cache changed')
        bars=canonical(pd.read_parquet(target))
    else:
        tree=ast.parse((DIRECTORY/'strategy/mass_research.py').read_text(encoding='utf-8'))
        queries=[n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value.startswith('SELECT time_bucket')]
        if len(queries)!=1: raise ValueError('Expected frozen aggregation query')
        import duckdb
        db=duckdb.connect()
        try:
            db.execute('SET threads=1');db.execute("SET memory_limit='256MB'");db.execute('SET enable_progress_bar=false')
            bars=canonical(db.execute(queries[0],[str(source)]).fetch_df())
        finally: db.close()
        bars.to_parquet(target,index=False)
        json_write(target.with_suffix('.json'),dict(source_sha256=item['partition']['dataset_version'],cache_sha256=file_hash(target)))
    _,quality=validate(bars,minutes=15)
    if quality['fatal'] or bars.timestamp_utc.duplicated().any() or not bars.instrument.eq(symbol).all(): raise ValueError('Invalid bars')
    if not (bars.timestamp_utc.ge(pd.Timestamp('2026-01-01T00:00Z')).all() and bars.timestamp_utc.lt(pd.Timestamp('2027-01-01T00:00Z')).all()):
        raise PermissionError('Test boundary violation')
    return bars


def record_attempt(db,c):
    db.execute('INSERT INTO attempts VALUES (?,?,?,?)',(c['config_id'],'started',now(),None));db.commit()


def progress(db,frozen,phase):
    counts=dict(db.execute('SELECT state,COUNT(*) FROM attempts GROUP BY state'))
    value=dict(target=frozen['target'],completed=counts.get('completed',0)+counts.get('cached',0),
        new_completed=counts.get('completed',0),cached=counts.get('cached',0),failed=counts.get('error',0),
        phase=phase,states=counts,run_path=str(DIRECTORY),updated_at=now(),no_tuning=True,validation_accessed=False)
    json_write(ROOT/'reports/positive_cohort_test_progress.json',value)
    print(json.dumps(value),flush=True)


def execute_case(c,bars,data,features,engine):
    cfg=c['parameters'];signal=engine.masked_signal(bars,cfg,features)
    signal[:96]=0;signal[-16:]=0
    result=engine.execute(data,signal,features['atr'],engine.execution_cfg(cfg))
    d=dict(data,regime=engine.entry_regimes(features['trend']))
    metrics=engine.summarize_execution(result,d)
    metrics['execution_verification']=engine.verify_execution(bars,d,signal,features['atr'],cfg,engine.execution_cfg(cfg),result,max_replays=5)
    cid=c['config_id']
    pd.DataFrame(dict(timestamp_utc=bars.timestamp_utc,equity=result['equity'],cash=result['cash'],
        intrabar_worst_bound=result['worst'],quantity=result['quantity'],funded_floor=result['funded_floor'])).to_parquet(DIRECTORY/'curves'/(cid+'.parquet'),index=False)
    pd.DataFrame(dict(entry_time=pd.to_datetime(d['timestamp'][result['trade_entry']],utc=True),
        exit_time=pd.to_datetime(d['timestamp'][result['trade_exit']],utc=True),side=result['trade_side'],quantity=result['trade_qty'],
        entry_price=result['trade_entryprice'],exit_price=result['trade_exitprice'],net_pnl=result['trade_net'],fees=result['trade_fees'],
        reason=[engine.TRADE_REASONS[int(i)] for i in result['trade_reason']])).to_parquet(DIRECTORY/'trades'/(cid+'.parquet'),index=False)
    record=dict(config_id=cid,parameters=cfg,metrics=metrics,no_tuning=True,cost_variants=1,parameter_variants=1,
        validation_accessed=False,period_previously_consumed=True,independent_confirmation=False,completed_at=now())
    json_write(DIRECTORY/'results'/(cid+'.json'),record)
    return record


def _evaluate():
    manifest,frozen=verify();reserve_all(manifest,frozen)
    db=sqlite3.connect(DIRECTORY/'checkpoints.sqlite')
    db.execute('CREATE TABLE IF NOT EXISTS attempts (config_id TEXT PRIMARY KEY,state TEXT NOT NULL,started TEXT NOT NULL,payload TEXT)')
    # A previous interrupted execution consumes that attempt; never replay it.
    db.execute("UPDATE attempts SET state='error',payload=? WHERE state='started'",(json.dumps(dict(error='Interrupted attempt consumed; not replayed')),));db.commit()
    known={row[0] for row in db.execute('SELECT config_id FROM attempts')}
    if CACHED_ID not in known:
        db.execute('INSERT INTO attempts VALUES (?,?,?,?)',(CACHED_ID,'cached',now(),json.dumps(read(CACHED),allow_nan=False)));db.commit();known.add(CACHED_ID)
    engine=archive()
    for symbol in ('ES','NQ','MES','MNQ'):
        pending=[c for c in frozen['cohort'] if c['instrument']==symbol and c['config_id'] not in known]
        if not pending: continue
        progress(db,frozen,'loading frozen TEST '+symbol)
        bars=load_test(symbol,frozen);data=engine.arrays(bars)
        for lookback,group in groupby(sorted(pending,key=lambda c:c['parameters']['lookback']),key=lambda c:c['parameters']['lookback']):
            features=engine.features(bars,lookback)
            for c in group:
                record_attempt(db,c)
                try:
                    payload=execute_case(c,bars,data,features,engine);state='completed'
                except Exception as error:
                    payload=dict(config_id=c['config_id'],error=type(error).__name__+': '+str(error));state='error'
                    json_write(DIRECTORY/'results'/(c['config_id']+'.json'),payload)
                db.execute('UPDATE attempts SET state=?,payload=? WHERE config_id=?',(state,json.dumps(payload,allow_nan=False),c['config_id']));db.commit()
                known.add(c['config_id'])
                if len(known)%100==0: progress(db,frozen,'one frozen test case each: '+symbol)
            del features;gc.collect()
        del bars,data;gc.collect()
    verify()
    progress(db,frozen,'all frozen cohort attempts recorded; no tuning')
    if db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]!=frozen['target']: raise ValueError('Incomplete cohort')
    db.close()


def evaluate():
    # OS lock is released after crashes; a second worker cannot race attempts.
    import msvcrt
    with (DIRECTORY/'execution.lock').open('a+b') as lock:
        if lock.tell()==0: lock.write(b'0');lock.flush()
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        try: _evaluate()
        finally:
            lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare',action='store_true');mode.add_argument('--evaluate',action='store_true')
    args=parser.parse_args()
    with threadpool_limits(limits=1): prepare() if args.prepare else evaluate()

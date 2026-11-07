"""Maximize TRAIN profit across100k new configurations under strict$2000 DD.

This module never resolves, reads, hashes or evaluates validation/test files
or their result records. Benchmarks and exclusions come from TRAIN artifacts.
"""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'): os.environ[key]='1'
import argparse
import ast
import csv
import gc
from itertools import groupby
import json
from pathlib import Path
import shutil
import sqlite3
import time
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
import mass_research as engine
from training_100k_policy import aggregate,prior_training as policy_prior_training
from mass_continuation_configurations import generate,semantic_key
from mass_configurations import INSTRUMENTS,metadata
from quant_futures.config import file_hash,digest
from quant_futures.research import json_write,code_identity

ROOT=engine.ROOT
RUN=ROOT/'runs/training_search_100k_v1'
TARGET=100000
SEED=20261113
PRIOR=('mass_training_v2','mass_training_continuation_v1','training_search_50k_v2')


def sources():
    return [Path(__file__),Path(__file__).with_name('training_100k_policy.py'),ROOT/'configs/user_account_phase_policy.json',Path(__file__).with_name('mass_continuation_configurations.py'),*engine.sources()]


def prior_training():
    return policy_prior_training(ROOT,PRIOR)


def universe(excluded):
    seen=set(excluded);rows=[]
    for offset in range(10):
        batch=generate(seen,SEED+offset)
        seen.update(semantic_key(c) for c in batch);rows.extend(batch)
    if len(rows)!=TARGET or len({semantic_key(c) for c in rows})!=TARGET: raise AssertionError('Invalid100k universe')
    # Fixed balanced ordering within each lookback; short-horizon candidates
    # across every market are reached before the next indicator horizon.
    rows.sort(key=lambda c:(c['lookback'],INSTRUMENTS.index(c['instrument']),c['config_id']))
    for order,c in enumerate(rows,1): c['experiment_order']=order
    return rows


def better_base(row,benchmark):
    return bool(row['qualified'] and row['net_pnl']>benchmark['net_pnl'] and
        all(row[k]<2000 for k in ('realized_drawdown','max_drawdown','intrabar_drawdown')))


def folds_for(bars):
    folds=[]
    for year in range(2020,2024):
        indexes=np.flatnonzero(bars.timestamp_utc.ge(pd.Timestamp(f'{year}-01-01T00:00Z')) &
            bars.timestamp_utc.lt(pd.Timestamp(f'{year+1}-01-01T00:00Z')))
        if len(indexes)<=128: raise ValueError('Insufficient common-calendar training fold')
        folds.append(dict(label=str(year),start=int(indexes[0]),stop=int(indexes[-1])+1,embargo_bars=96,purge_bars=16))
    return folds


def session_masks(bars):
    local=bars.timestamp_utc.dt.tz_convert('America/New_York')
    decision=(local.dt.hour*60+local.dt.minute+15).to_numpy()
    weekdays=local.dt.weekday.to_numpy()<5
    from mass_configurations import SESSIONS
    return {(start,end):(decision>=start)&(decision<end)&weekdays for start,end in SESSIONS}


def cached_signal(c,features,masks,cache):
    key=(c['family'],c['threshold'])
    if key not in cache: cache[key]=engine.signal_for(c,features).astype(np.int8)
    return np.where(masks[(c['session_start'],c['session_end'])],cache[key],0).astype(np.int8)


def setup(folder):
    excluded,benchmark,preserved=prior_training();rows=universe(excluded)
    original=engine.read(ROOT/'runs/mass_training_v2/protocol.json')
    core=code_identity()
    if core['source_hash']!=original['source_hash']: raise ValueError('Core simulator changed')
    for path in engine.sources():
        if file_hash(path)!=original['source_hashes'][path.name]: raise ValueError('Frozen execution dependency changed')
    identity={p.name:file_hash(p) for p in sources()}
    universe_meta=metadata(rows,SEED)
    folder.mkdir(parents=True,exist_ok=True)
    if (folder/'protocol.json').exists():
        protocol=engine.read(folder/'protocol.json')
        if protocol['source_hashes']!=identity or protocol['universe']!=universe_meta or protocol['benchmark']!=benchmark:
            raise ValueError('Frozen100k protocol changed')
    else:
        protocol=dict(created_at=engine.now(),target=TARGET,seed=SEED,universe=universe_meta,benchmark=benchmark,
            preserved_training_files=preserved,source_hashes=identity,**core,
            authorization='User requests another100000 new strategies. TRAIN-only research, profit under2k DD, with previously instructed evaluation-only consistency scope. No validation/test stage authorized by this run.',
            selection='Benchmark is the saved9972.50 TRAIN candidate. Only prior TRAIN artifacts supply benchmark/exclusions. Original parameter domains/families are unchanged; no validation/test outcomes guide generation, filters or ranking.',
            calendar='Every market uses four separate2020/2021/2022/2023 TRAIN accounts for comparable horizons. Earlier TRAIN history supplies causal indicators only. External split boundaries unchanged.',
            improvement='Complete all100k new configurations. Use the user-provided evaluation-only consistency scope for classification, without altering executions. Rank research-qualified candidates by net profit descending, then intrabar DD ascending. Check in that order and choose the first whose base reproduces, independent ledger/shared fills verify and2x costs still satisfy the original qualification. Better than benchmark means greater training net with every DD strictly<2000; DD need not be lower than benchmark.',
            phase_policy=engine.read(ROOT/'configs/user_account_phase_policy.json'),qualification='Research/post-evaluation: positive each training fold, >=30 trades each, no permanent risk or funded-scenario breach, all DD strictly<2000. Evaluation-account-phase qualification additionally requires50% consistency. Consistency is always reported, never used to alter signals.',execution=original['execution'],fee_assumption=original['fee_assumption'],
            unknowns=original['unknowns'],validation_accessed=False,test_accessed=False,protected_result_files_read=False,
            no_live_execution=True,early_stop_authorized=False,classification='RESEARCH_ONLY',
            runtime='Single worker, cached causal indicators/signals/session masks, SQLite commit every25. Fixed100k manifest before training-price access. No GPU benefit for sequential account paths.')
        json_write(folder/'protocol.json',protocol)
        with (folder/'configurations.jsonl').open('x',encoding='utf-8') as stream:
            for c in rows: stream.write(json.dumps(c,sort_keys=True)+'\n')
        snapshot=folder/'code';snapshot.mkdir()
        for path in sources(): shutil.copyfile(path,snapshot/path.name)
        shutil.copytree(ROOT/'runs/mass_training_v2/code/quant_futures',snapshot/'quant_futures')
        shutil.copyfile(ROOT/'runs/mass_training_v2/code/runtime_versions.json',snapshot/'runtime_versions.json')
        (folder/'cache').mkdir()
        for symbol in INSTRUMENTS:
            for ext in ('.parquet','.json'):
                old=ROOT/'runs/mass_training_v2/cache'/(symbol+'_15m'+ext)
                shutil.copyfile(old,folder/'cache'/old.name)
    db=sqlite3.connect(folder/'checkpoints.sqlite')
    db.execute('CREATE TABLE IF NOT EXISTS results (config_id TEXT PRIMARY KEY,experiment_order INTEGER UNIQUE,instrument TEXT,score REAL,payload TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS checks (config_id TEXT PRIMARY KEY,payload TEXT)')
    return rows,protocol,db


def progress(folder,db,phase,qualified=None):
    counts=dict(db.execute('SELECT instrument,COUNT(*) FROM results GROUP BY instrument'))
    record=dict(run_path=str(folder),target=TARGET,completed=sum(counts.values()),phase=phase,per_market=counts,
        validation_accessed=False,test_accessed=False,protected_result_files_read=False,updated_at=engine.now())
    json_write(ROOT/'reports/training_search_100k_progress.json',record)
    print(json.dumps(record),flush=True)


def verify_candidate(c,row,bars,data,folds,features,signal,folder,db):
    check_path=folder/('check_'+c['config_id']+'.json')
    saved=db.execute('SELECT payload FROM checks WHERE config_id=?',(c['config_id'],)).fetchone()
    if saved: return json.loads(saved[0])
    base=engine.evaluate_configuration(c,bars,data,folds,features,signal,save=True,folder=folder)
    for old,new in zip(row['fold_metrics'],base):
        for key in ('net_pnl','max_drawdown','realized_drawdown','intrabar_drawdown','trades'):
            if old[key]!=new[key]: raise ValueError('Base reproduction failed')
    stress=engine.evaluate_configuration(c,bars,data,folds,features,signal,factor=2,save=True,folder=folder)
    stressed=aggregate(c,stress,signal)
    checked=dict(config_id=c['config_id'],base_reproduced=True,base=row,stress_2x=stressed,
        execution_parity=[m['execution_verification'] for m in base],stress_qualified=bool(stressed['qualified']),evaluation_phase_stress_qualified=bool(stressed['evaluation_phase_qualified']),
        verified_better=bool(stressed['qualified'] and better_base(row,engine.read(folder/'protocol.json')['benchmark'])),
        validation_accessed=False,test_accessed=False)
    json_write(check_path,checked)
    db.execute('INSERT INTO checks VALUES (?,?)',(c['config_id'],json.dumps(checked,allow_nan=False)));db.commit()
    return checked


def export_ranked(folder,db):
    fields=[*engine.CSV_FIELDS,'evaluation_phase_qualified']
    seen=set();top=[]
    with (folder/'ranked.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for rank,(payload,) in enumerate(db.execute("SELECT payload FROM results ORDER BY json_extract(payload,'$.qualified') DESC,json_extract(payload,'$.net_pnl') DESC,json_extract(payload,'$.intrabar_drawdown') ASC,config_id"),1):
            row=json.loads(payload);row['rank']=rank
            c=row['parameters']
            behavior=digest(dict(signal=row['signal_fingerprint'],stop=c['stop_atr'],target=c['target_r'],hold=c['hold_bars'],qty=c['max_contracts'],trail=c['trailing_atr']))
            row['behaviorally_unique']=behavior not in seen;seen.add(behavior)
            if len(top)<10: top.append(row)
            values={k:row.get(k) for k in fields}
            for key in ('parameters','monthly_pnl','regime_pnl','fold_metrics'): values[key]=json.dumps(values[key],allow_nan=False)
            writer.writerow(values)
    return top


def run(folder=RUN):
    rows,protocol,db=setup(folder)
    if (folder/'results.json').exists():
        print(json.dumps(dict(already_complete=True,run_path=str(folder))));return
    completed={r[0] for r in db.execute('SELECT config_id FROM results')};winner=None
    pending=[c for c in rows if c['config_id'] not in completed]
    try:
        baseline_path=folder/'baseline_reproduction.json'
        if not baseline_path.exists():
            c=protocol['benchmark']['parameters'];progress(folder,db,'reproducing existing TRAIN benchmark')
            b,_=engine.load_training(c['instrument'],folder);d=engine.arrays(b);f=engine.features(b,c['lookback'])
            s=cached_signal(c,f,session_masks(b),{})
            measured=engine.evaluate_configuration(c,b,d,folds_for(b),f,s)
            baseline=aggregate(c,measured,s)
            for key in ('net_pnl','realized_drawdown','max_drawdown','intrabar_drawdown'):
                if baseline[key]!=protocol['benchmark'][key]: raise ValueError('TRAIN baseline mismatch')
            json_write(baseline_path,dict(passed=True,metrics=baseline,counts_as_new_configuration=False))
            del b,d,f,s,measured;gc.collect()
        for lookback,lookback_group in groupby(pending,key=lambda c:c['lookback']):
            for symbol,group in groupby(lookback_group,key=lambda c:c['instrument']):
                progress(folder,db,f'loading TRAIN {symbol}, lookback{lookback}')
                bars,meta=engine.load_training(symbol,folder);data=engine.arrays(bars);folds=folds_for(bars)
                json_write(folder/(symbol+'_source.json'),meta);json_write(folder/(symbol+'_folds.json'),folds)
                features=engine.features(bars,lookback);masks=session_masks(bars);signal_cache={}
                for c in group:
                    signal=cached_signal(c,features,masks,signal_cache)
                    measured=engine.evaluate_configuration(c,bars,data,folds,features,signal)
                    row=aggregate(c,measured,signal)
                    db.execute('INSERT INTO results VALUES (?,?,?,?,?)',(c['config_id'],c['experiment_order'],symbol,row['score'],json.dumps(row,allow_nan=False)))
                    completed.add(c['config_id'])
                    if len(completed)%25==0: db.commit()
                    if len(completed)%100==0: progress(folder,db,f'TRAIN {symbol}, lookback{lookback}')
                db.commit();del bars,data,features,masks,signal_cache;gc.collect()
        if len(completed)!=TARGET: raise RuntimeError('Full100k budget incomplete')
        candidates=db.execute("SELECT payload FROM results WHERE json_extract(payload,'$.qualified')=1 ORDER BY json_extract(payload,'$.net_pnl') DESC,json_extract(payload,'$.intrabar_drawdown') ASC,config_id").fetchall()
        for (payload,) in candidates:
            row=json.loads(payload);c=row['parameters']
            progress(folder,db,'verifying profit-ranked TRAIN candidate '+c['config_id'])
            bars,_=engine.load_training(c['instrument'],folder);data=engine.arrays(bars);folds=folds_for(bars)
            features=engine.features(bars,c['lookback']);signal=cached_signal(c,features,session_masks(bars),{})
            check=verify_candidate(c,row,bars,data,folds,features,signal,folder,db)
            del bars,data,features,signal;gc.collect()
            if check['stress_qualified']:
                winner=check;break
        top10=export_ranked(folder,db)
        for path,expected in protocol['preserved_training_files'].items():
            if file_hash(path)!=expected: raise ValueError('Prior training artifact changed')
        result=dict(run_path=str(folder),target=TARGET,completed=len(completed),new_unique_completed=len(completed),
            planned_unique=TARGET,cumulative_completed_unique=70000+len(completed),benchmark=protocol['benchmark'],
            winner=winner,top10=top10,qualified_count=db.execute("SELECT COUNT(*) FROM results WHERE json_extract(payload,'$.qualified')=1").fetchone()[0],
            stopping_reason='100000_new_configurations_completed',improved_vs_benchmark=bool(winner and winner['verified_better']),
            validation_accessed=False,test_accessed=False,protected_result_files_read=False,
            independent_confirmation=False,operational_eligibility=False,source_hashes=protocol['source_hashes'],finished_at=engine.now())
        json_write(folder/'results.json',result);json_write(ROOT/'reports/training_search_100k_result.json',result)
        progress(folder,db,result['stopping_reason'])
        print(json.dumps(dict(completed=len(completed),candidate_found=bool(winner),improvement_found=bool(winner and winner['verified_better']),stopping_reason=result['stopping_reason'])),flush=True)
    finally: db.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=Path,default=RUN)
    args=parser.parse_args()
    with threadpool_limits(limits=1): run(args.run.resolve())

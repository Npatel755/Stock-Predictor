"""Freeze200k new configs, TRAIN all, then VALIDATION all and rank fixed models.

Validation is explicitly a model-selection set, not independent confirmation.
No TEST paths, prices, reservations or outcome files are accessed by this batch.
"""
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import argparse
import csv
import gc
from itertools import groupby
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import zlib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
import e57_training_refinement as training
from e57_refinement_parameters import universe,fingerprint,scaled_cfg
from quant_futures.config import file_hash,digest
from quant_futures.research import json_write,code_identity

ROOT=training.ROOT
RUN=ROOT/'runs/validation_selection_200k_v1'
TARGET=200000;SEED=20270301
PRIOR=(*training.PRIOR,'e57_training_refinement_v1','training_search_500k_v2')
DD_FIELDS=training.DD_FIELDS
TRADE_KEYS=('trade_entry','trade_exit','trade_side','trade_qty','trade_entryprice','trade_exitprice','trade_net','trade_fees','trade_reason')


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def now():return training.engine.now()
def sources():return [Path(__file__),Path(__file__).with_name('evaluate_saved_50k_candidate.py'),*training.sources()]


def connection():
    db=sqlite3.connect(RUN/'checkpoints.sqlite');db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=NORMAL')
    db.execute('CREATE TABLE IF NOT EXISTS train(config_id TEXT PRIMARY KEY,experiment_order INTEGER UNIQUE,qualified INTEGER,net REAL,dd REAL,payload TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS val(config_id TEXT PRIMARY KEY,qualified INTEGER,net REAL,dd REAL,train_qualified INTEGER,payload TEXT,ledger BLOB)')
    db.execute('CREATE TABLE IF NOT EXISTS validation_attempts(config_id TEXT PRIMARY KEY,dataset_version TEXT,reservation_key TEXT UNIQUE,state TEXT,error TEXT)')
    return db


def prepare():
    if (RUN/'training_protocol.json').exists():verify();print(json.dumps(dict(already_prepared=True)));return
    baseline=read(training.BASELINE)
    if code_identity()['source_hash']!=baseline['source_protocol']['source_hash']:raise ValueError('Original core changed')
    for p in training.engine.sources():
        if file_hash(p)!=baseline['source_protocol']['source_hashes'][p.name]:raise ValueError('Original simulator dependency changed')
    excluded=set();raw_count=0;hashes={};counts={}
    for name in PRIOR:
        path=ROOT/'runs'/name/'configurations.jsonl';hashes[str(path)]=file_hash(path);n=0
        with path.open(encoding='utf-8') as stream:
            for line in stream:excluded.add(fingerprint(json.loads(line)));n+=1
        raw_count+=n;counts[name]=n
    rows=universe(baseline['parameters'],excluded,TARGET,SEED)
    RUN.mkdir(parents=True,exist_ok=False)
    for name in ('code','cache','snapshots'): (RUN/name).mkdir()
    with (RUN/'configurations.jsonl').open('x',encoding='utf-8') as stream:
        for c in rows:stream.write(json.dumps(c,sort_keys=True)+'\n')
    identities={p.name:file_hash(p) for p in sources()}
    for p in sources():shutil.copyfile(p,RUN/'code'/p.name)
    shutil.copytree(ROOT/'runs/mass_training_v2/code/quant_futures',RUN/'code/quant_futures')
    for ext in ('.json','.parquet'):
        p=ROOT/'runs/training_search_100k_v1/cache'/('MNQ_15m'+ext);shutil.copyfile(p,RUN/'cache'/p.name)
    protocol=dict(created_at=now(),target=TARGET,seed=SEED,source_hashes=identities,core_source_hash=baseline['source_protocol']['source_hash'],configuration_sha256=file_hash(RUN/'configurations.jsonl'),prior_manifest_hashes=hashes,prior_raw_cases=raw_count,prior_unique_excluded=len(excluded),prior_counts=counts,baseline_training=baseline['training'],baseline_artifact=str(training.BASELINE),baseline_artifact_sha256=file_hash(training.BASELINE),phase_policy=baseline['phase_policy'],
        authorization='User explicitly clarified ALL strategies in the NEW200000 batch must be evaluated on validation once, WITHOUT parameter/rule tuning, then RANKED by validation performance. Full200k train+full200k validation; test access not authorized.',
        hypothesis='Continuation of the already registered MNQ momentum/risk parameter domains with a new seed. No indicator, filter, holiday rule or gap/risk guard changes from prior holdout outcomes. Training never reads validation-policy outcomes or validation results.',
        training='All200k fixed configs over four2020-2023 TRAIN annual accounts reset50k. Every year positive,>=30trades/year,PF>=1.30,<=800total trades,no permanent/funded failure,allDD<2000 marks TRAIN quality. No candidate is excluded from validation for failing these gates. No training-based finalist selection or early stop.',
        freeze='Entire200k manifest and all trading code frozen before training prices; TRAIN finishes and its results hash is sealed before ANY validation price access. Only after all validation results are sealed is the complete validation ranking published.',
        execution='Unchanged completed15m raw-contract OHLCV, causal features,next-open fills,conservative stops/targets,gaps/rolls/volume,costs and prior risk scaling adapter.96/16 entry suppression. HardDD1800/fundedDD2000 retained; risk scales/max positions remain the same registered research scenarios.',
        ranking='Validation scenario pass first, then validation net descending,intrabarDD ascending,ID. All200k included, training qualification shown separately. A second filtered ranking requires both TRAIN and validation gates; accepted superiority additionally requires validation net above original saved v1 validation net. Validation is a consumed model-selection set, not independent unseen evidence.',
        no_feedback='No parameters or variants change during/after validation, no validation-driven follow-up search, no automatic retries to find a pass. Test prices, metadata resolution,reservations and outcomes remain unopened by this run.',
        capture='Compressed trade ledger for every validation case in SQLite. Capture raw account paths for running top10 overall and top10 both-split qualifiers, with display-only ranking and no parameter changes. Selected fill checks use saved raw execution outputs, never a second full validation backtest.',
        unknowns=baseline['source_protocol']['unknowns'],inherited_selection='Original v1 was user-selected after old holdout observations. All partitions were previously used; no independence can be restored by relabeling.',test_accessed=False,independent_confirmation=False)
    json_write(RUN/'training_protocol.json',protocol)
    # Acceptance reference is isolated from the training worker; only the validation
    # coordinator reads these already-observed baseline results, never for parameters.
    ref_path=ROOT/'strategy_versions/mnq_momentum_e57/v1.0.0/validation_existing_result.json';reference=read(ref_path)
    if reference['config_id']!='mass_e57ba183f302b3ba886b':raise ValueError('Original validation benchmark changed')
    catalog=read(ROOT/'data/catalog.json');p=catalog['instruments']['MNQ']['splits']['validation'];meta=read(Path(p['path']).with_suffix('.manifest.json'))
    if meta.get('split_role')!='validation' or meta.get('instrument')!='MNQ' or meta.get('synthetic') is not False or meta.get('raw_contract_prices') is not True or meta['dataset_version']!=p['dataset_version']:raise PermissionError('Physical MNQ validation metadata required')
    policy=dict(created_at=now(),partitions={'validation':dict(partition=p,metadata=meta)},configuration_sha256=protocol['configuration_sha256'],baseline_validation_net=reference['net_pnl'],baseline_reference_sha256=file_hash(ref_path),
        primary_gate='Positive validation net; cash,closing,intrabarDD each strictly<2000;>=30trades;no permanent lock;no funded breach.50% consistency is separately reported for the account evaluation phase only.',
        good_model='Training-qualified AND validation scenario-qualified.',better_than_baseline='Good model AND validation net strictly greater than archived original-v1 validation net. Risk increase allowed only below2000DD. This is model selection, not independent confirmation or account certification.',
        validation_evaluations_per_configuration=1,cost_variants=1,no_parameter_tuning=True,validation_used_for_model_selection=True,independent_confirmation=False,test_accessed=False)
    json_write(RUN/'validation_policy.json',policy)
    connection().close()
    print(json.dumps(dict(prepared=True,new_unique=TARGET,prior_raw_cases=raw_count,prior_unique_excluded=len(excluded),training_prices_opened=False,validation_prices_opened=False,test_accessed=False)))


def verify():
    p=read(RUN/'training_protocol.json')
    if p['source_hashes']!={f.name:file_hash(f) for f in sources()}:raise ValueError('Frozen trading/orchestration code changed')
    for name,expected in p['source_hashes'].items():
        if file_hash(RUN/'code'/name)!=expected:raise ValueError('Archived code changed')
    if code_identity()['source_hash']!=p['core_source_hash'] or file_hash(training.BASELINE)!=p['baseline_artifact_sha256'] or file_hash(RUN/'configurations.jsonl')!=p['configuration_sha256']:raise ValueError('Frozen baseline,core or configurations changed')
    return p


def progress(db,phase):
    r=dict(target=TARGET,training_completed=db.execute('SELECT COUNT(*) FROM train').fetchone()[0],validation_completed=db.execute('SELECT COUNT(*) FROM val').fetchone()[0],phase=phase,validation_used_for_model_selection=True,test_accessed=False,updated_at=now())
    json_write(ROOT/'reports/VALIDATION_SELECTION_200K_progress.json',r);print(json.dumps(r),flush=True)


def configurations():
    with (RUN/'configurations.jsonl').open(encoding='utf-8') as stream:return [json.loads(line) for line in stream]


def train():
    protocol=verify();db=connection()
    try:
        if (RUN/'training_complete.json').exists():return
        done={r[0] for r in db.execute('SELECT config_id FROM train')};rows=[c for c in configurations() if c['config_id'] not in done]
        progress(db,'Loading verified physical MNQ TRAIN only')
        bars,meta=training.engine.load_training('MNQ',RUN);data=training.engine.arrays(bars);folds=training.folds_for(bars);masks=training.session_masks(bars)
        json_write(RUN/'training_source.json',meta);json_write(RUN/'training_folds.json',folds)
        for lookback,group in groupby(rows,key=lambda c:c['lookback']):
            f=training.engine.features(bars,lookback);cache={}
            for c in group:
                s=training.cached_signal(c,f,masks,cache)
                measured=training.measured(c,bars,data,folds,f,s)
                row=training.aggregate(c,measured,s)
                db.execute('INSERT INTO train VALUES(?,?,?,?,?,?)',(c['config_id'],c['experiment_order'],int(row['qualified']),row['net_pnl'],row['intrabar_drawdown'],json.dumps(row,allow_nan=False)));done.add(c['config_id'])
                if len(done)%250==0:db.commit()
                if len(done)%1000==0:progress(db,f'TRAIN L{lookback}')
            db.commit();del f,cache;gc.collect()
        assert len(done)==TARGET
        fields=list(training.engine.CSV_FIELDS)+['evaluation_phase_qualified','robustness_score']
        with (RUN/'training_results.csv').open('w',encoding='utf-8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
            for (payload,) in db.execute('SELECT payload FROM train ORDER BY experiment_order'):
                row=json.loads(payload);out={k:row.get(k) for k in fields}
                for k in ('parameters','monthly_pnl','regime_pnl','fold_metrics'):out[k]=json.dumps(out[k],allow_nan=False)
                writer.writerow(out)
        json_write(RUN/'training_complete.json',dict(completed=TARGET,configuration_sha256=protocol['configuration_sha256'],source_hashes=protocol['source_hashes'],training_csv_sha256=file_hash(RUN/'training_results.csv'),completed_at=now(),validation_prices_accessed=False,test_accessed=False))
        progress(db,'TRAIN complete; no validation prices loaded yet')
    finally:db.close()


def validation_checks(row):
    primary=bool(row['net_pnl']>0 and all(row[k]<2000 for k in DD_FIELDS))
    scenario=bool(primary and row['trades']>=30 and row['locks']==0 and row['funded_breaches']==0)
    return primary,scenario


def execute_validation(c,bars,data,features,signal):
    s=signal.copy();s[:96]=0;s[-16:]=0
    cfg=scaled_cfg(training.engine.execution_cfg(c),c)
    raw=training.engine.execute(data,s,features['atr'],cfg)
    enriched=dict(data,regime=training.engine.entry_regimes(features['trend']))
    m=training.engine.summarize_execution(raw,enriched);m['label']='validation';m.pop('daily_pnl')
    row=training.engine.aggregate(c,[m],signal)
    primary,scenario=validation_checks(row)
    row.update(profit_dd_pass=primary,qualified=scenario,evaluation_phase_qualified=bool(scenario and m['consistency_50_pass']))
    return row,raw


def order_key(row):return (-int(row['qualified']),-row['net_pnl'],row['intrabar_drawdown'],row['config_id'])


def snapshot_if_top(row,raw,overall,both):
    take=False
    for heap,eligible in ((overall,True),(both,row['qualified'] and row['training_qualified'])):
        if eligible and (len(heap)<10 or order_key(row)<order_key(heap[-1])):
            heap.append(row);heap.sort(key=order_key);del heap[10:];take=True
    if take:
        path=RUN/'snapshots'/(row['config_id']+'.npz')
        if not path.exists():np.savez_compressed(path,**{k:v for k,v in raw.items() if isinstance(v,(np.ndarray,int,float,bool,np.number))})


def load_validation(policy):
    target=RUN/'cache/MNQ_validation_15m.parquet';identity=target.with_suffix('.json')
    source=policy['partitions']['validation']['partition']
    if target.exists():
        cached=read(identity)
        if cached['source_sha256']!=source['dataset_version'] or file_hash(target)!=cached['cache_sha256']:raise ValueError('Validation cache changed')
        return pd.read_parquet(target)
    spec=importlib.util.spec_from_file_location('selection_frozen_loader',RUN/'code/evaluate_saved_50k_candidate.py');loader=importlib.util.module_from_spec(spec);spec.loader.exec_module(loader)
    loader.DIRECTORY=RUN
    # Loader expects a strategy directory; use the identical frozen code snapshot.
    if not (RUN/'strategy').exists():shutil.copytree(RUN/'code',RUN/'strategy')
    bars=loader.load_split('validation',policy)
    bars.to_parquet(target,index=False);json_write(identity,dict(source_sha256=source['dataset_version'],cache_sha256=file_hash(target),role='validation',bars=len(bars)))
    return bars


def validate():
    protocol=verify();complete=read(RUN/'training_complete.json')
    if complete['completed']!=TARGET or complete['configuration_sha256']!=protocol['configuration_sha256'] or complete['training_csv_sha256']!=file_hash(RUN/'training_results.csv'):raise ValueError('All200k TRAIN results must be sealed before validation')
    policy=read(RUN/'validation_policy.json');db=connection()
    try:
        if (RUN/'validation_complete.json').exists():return
        if db.execute("SELECT COUNT(*) FROM validation_attempts WHERE state='running'").fetchone()[0]:raise RuntimeError('Interrupted validation attempt is consumed; refuse silent replay')
        if not (RUN/'validation_reservation.json').exists():
            cohort=dict(phase='validation',target=TARGET,configuration_sha256=protocol['configuration_sha256'],training_complete_sha256=file_hash(RUN/'training_complete.json'),validation_policy_sha256=file_hash(RUN/'validation_policy.json'),dataset_version=policy['partitions']['validation']['partition']['dataset_version'],source_hashes=protocol['source_hashes'],reserved_at=now(),one_execution_per_configuration=True,failure_consumes_attempt=True,test_accessed=False)
            global_path=ROOT/'data/manifests/validation_once'/('batch_'+digest(cohort)+'.json')
            global_path.parent.mkdir(parents=True,exist_ok=True)
            with global_path.open('x',encoding='utf-8') as stream:json.dump(cohort,stream,indent=2)
            cohort['global_reservation']=str(global_path);json_write(RUN/'validation_reservation.json',cohort)
        else:
            reserved=read(RUN/'validation_reservation.json')
            if reserved['validation_policy_sha256']!=file_hash(RUN/'validation_policy.json') or reserved['training_complete_sha256']!=file_hash(RUN/'training_complete.json'):raise ValueError('Reserved validation policy/TRAIN seal changed')
        rows=configurations();version=policy['partitions']['validation']['partition']['dataset_version']
        if db.execute('SELECT COUNT(*) FROM validation_attempts').fetchone()[0]==0:
            db.executemany('INSERT INTO validation_attempts VALUES(?,?,?,?,?)',((c['config_id'],version,digest(dict(candidate_id=c['config_id'],parameters=c,dataset_version=version)),'reserved',None) for c in rows));db.commit()
        attempted={r[0] for r in db.execute("SELECT config_id FROM validation_attempts WHERE state!='reserved'")}
        training_summary={cid:(bool(q),net,dd) for cid,q,net,dd in db.execute('SELECT config_id,qualified,net,dd FROM train')}
        overall=[json.loads(r[0]) for r in db.execute('SELECT payload FROM val ORDER BY qualified DESC,net DESC,dd,config_id LIMIT 10')]
        both=[json.loads(r[0]) for r in db.execute('SELECT payload FROM val WHERE qualified=1 AND train_qualified=1 ORDER BY net DESC,dd,config_id LIMIT 10')]
        pending=[c for c in rows if c['config_id'] not in attempted]
        count=db.execute('SELECT COUNT(*) FROM val').fetchone()[0]
        progress(db,'Loading VALIDATION after full TRAIN freeze; TEST remains closed')
        bars=load_validation(policy);data=training.engine.arrays(bars);masks=training.session_masks(bars)
        for lookback,group in groupby(pending,key=lambda c:c['lookback']):
            features=training.engine.features(bars,lookback);cache={}
            for c in group:
                cid=c['config_id'];db.execute("UPDATE validation_attempts SET state='running' WHERE config_id=? AND state='reserved'",(cid,));db.commit()
                signal=training.cached_signal(c,features,masks,cache)
                try:
                    row,raw=execute_validation(c,bars,data,features,signal)
                    tq,tn,td=training_summary[cid];row.update(training_qualified=tq,training_net=tn,training_intrabar_drawdown=td,beats_baseline=bool(tq and row['qualified'] and row['net_pnl']>policy['baseline_validation_net']))
                    snapshot_if_top(row,raw,overall,both)
                    ledger=zlib.compress(json.dumps({k:raw[k].tolist() for k in TRADE_KEYS},allow_nan=False,separators=(',',':')).encode(),level=1)
                    db.execute('INSERT INTO val VALUES(?,?,?,?,?,?,?)',(cid,int(row['qualified']),row['net_pnl'],row['intrabar_drawdown'],int(tq),json.dumps(row,allow_nan=False),ledger))
                    db.execute("UPDATE validation_attempts SET state='done' WHERE config_id=?",(cid,));db.commit()
                except Exception as error:
                    db.execute("UPDATE validation_attempts SET state='failed',error=? WHERE config_id=?",(repr(error),cid));db.commit();raise
                count+=1
                if count%1000==0:progress(db,f'VALIDATION L{lookback}; fixed parameters, ranking only')
            del features,cache;gc.collect()
        count=db.execute('SELECT COUNT(*) FROM val').fetchone()[0]
        if count!=TARGET:raise RuntimeError(f'Validation incomplete: {count}/{TARGET}; no failed case is replayed')
        verify()
        reserved=read(RUN/'validation_reservation.json')
        if reserved['validation_policy_sha256']!=file_hash(RUN/'validation_policy.json') or reserved['training_complete_sha256']!=file_hash(RUN/'training_complete.json'):raise ValueError('Validation policy/TRAIN seal changed during execution')
        json_write(RUN/'validation_complete.json',dict(completed=count,configuration_sha256=protocol['configuration_sha256'],validation_policy_sha256=file_hash(RUN/'validation_policy.json'),training_complete_sha256=file_hash(RUN/'training_complete.json'),completed_at=now(),test_accessed=False,validation_used_for_model_selection=True,independent_confirmation=False))
        progress(db,'All200k TRAIN and all200k VALIDATION complete; ranking ready')
    finally:db.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=('prepare','train','validation','run'));a=p.parse_args()
    with threadpool_limits(limits=1):
        if a.phase=='prepare':prepare()
        elif a.phase=='train':train()
        elif a.phase=='validation':validate()
        else:prepare();train();validate()

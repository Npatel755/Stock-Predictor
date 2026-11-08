"""Up to200k new MNQ momentum/risk configurations; stop for verified TRAIN dominance.

No validation/test price or outcome paths are loaded. Reads only the v1 TRAIN
baseline artifact and prior configuration manifests, never its holdout archive.
"""
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import argparse
import gc
from itertools import groupby
import json
from pathlib import Path
import shutil
import sqlite3
import numpy as np
from threadpoolctl import threadpool_limits
import mass_research as engine
from training_search_100k import folds_for,session_masks,cached_signal
from training_500k_policy import aggregate as original_aggregate
from e57_refinement_parameters import DOMAINS,SCALING_CONTROLS,universe,fingerprint,execution_scope
from quant_futures.config import file_hash
from quant_futures.research import json_write,code_identity

ROOT=engine.ROOT
RUN=ROOT/'runs/e57_training_refinement_v1'
BASELINE=ROOT/'strategy_versions/mnq_momentum_e57/v1.0.0/training_baseline.json'
TARGET=200000;SEED=20270122
PRIOR=('mass_training_v2','mass_training_continuation_v1','training_search_50k_v2','training_search_100k_v1','training_search_200k_v1','training_search_500k_v1','collaborative_200k_v1')
DD_FIELDS=('realized_drawdown','max_drawdown','intrabar_drawdown')


def aggregate(c,folds,signal):
    row=original_aggregate(c,folds,signal)
    # Require every year positive and30 trades/year for a replacement, not just pooled wins.
    row['qualified']=bool(row['qualified'] and all(m['net_pnl']>0 and m['trades']>=30 for m in folds))
    row['evaluation_phase_qualified']=bool(row['qualified'] and all(m['consistency_50_pass'] for m in folds))
    return row


def dominates(row,baseline):
    return bool(row['qualified'] and row['net_pnl']>baseline['net_pnl'] and all(row[k]<=baseline[k] and row[k]<2000 for k in DD_FIELDS))


def sources():
    return [Path(__file__),*(Path(__file__).with_name(n) for n in ('e57_refinement_parameters.py','training_search_100k.py','training_100k_policy.py','training_500k_policy.py','mass_continuation_configurations.py')),*engine.sources()]


def setup():
    saved=engine.read(BASELINE);baseline=saved['training']
    if baseline['config_id']!='mass_e57ba183f302b3ba886b':raise ValueError('Baseline identity changed')
    original=saved['source_protocol']
    if code_identity()['source_hash']!=original['source_hash']:raise ValueError('Core differs from original')
    for p in engine.sources():
        if file_hash(p)!=original['source_hashes'][p.name]:raise ValueError('Original execution source changed')
    RUN.mkdir(parents=True,exist_ok=True)
    identity={p.name:file_hash(p) for p in sources()}
    if (RUN/'protocol.json').exists():
        protocol=engine.read(RUN/'protocol.json')
        if protocol['source_hashes']!=identity or file_hash(BASELINE)!=protocol['baseline_training_artifact_sha256'] or file_hash(RUN/'configurations.jsonl')!=protocol['configurations_sha256']:
            raise ValueError('Frozen refinement changed')
        rows=[json.loads(line) for line in (RUN/'configurations.jsonl').read_text(encoding='utf-8').splitlines()]
    else:
        excluded=set();prior_hashes={}
        for name in PRIOR:
            path=ROOT/'runs'/name/'configurations.jsonl';prior_hashes[str(path)]=file_hash(path)
            with path.open(encoding='utf-8') as stream:
                for line in stream:
                    key=fingerprint(json.loads(line))
                    if key in excluded:raise ValueError('Prior mass-search duplicate')
                    excluded.add(key)
        if len(excluded)!=1070000:raise ValueError('Expected1070000 prior reserved active configurations')
        rows=universe(baseline['parameters'],excluded,TARGET,SEED)
        with (RUN/'configurations.jsonl').open('x',encoding='utf-8') as stream:
            for c in rows:stream.write(json.dumps(c,sort_keys=True)+'\n')
        protocol=dict(created_at=engine.now(),parent_version='mnq_momentum_e57/v1.0.0',baseline_training=baseline,baseline_training_artifact=str(BASELINE),baseline_training_artifact_sha256=file_hash(BASELINE),source_hashes=identity,core_source_hash=original['source_hash'],configurations_sha256=file_hash(RUN/'configurations.jsonl'),prior_manifest_hashes=prior_hashes,prior_unique=1070000,target=TARGET,seed=SEED,domains=DOMAINS,scaling_controls=SCALING_CONTROLS,
            authorization='User: save versioned baseline; improve using TRAIN only; try another200000 or until something beats baseline; also try scaling for more risk/profit. No validation/test access authorized.',
            hypothesis='Preserve normalized momentum family; test bounded neighboring horizons/thresholds/exits and risk scales. Pure scaling changes only max quantity and explicit risk/daily budgets. No hypothesis or threshold chosen from holdout numbers.',
            stop_rule='Evaluate all seven pure scaling controls first at base and2x costs. Thereafter stop early at first predetermined-order challenger with higher TRAIN net and cash/closing/intrabar worst-fold DD no greater than baseline, every DD<2000, all4 years positive with>=30trades/year,PF>=1.30,totaltrades<=800,no permanent/funded breach, reproduced ledger/shared fills and same gates surviving2x costs. Otherwise complete200000. No automatic baseline promotion or holdout evaluation.',
            calendar='Only physical MNQ TRAIN before2024; four separate2020-2023 accounts reset50k. Sum annual net, worst annual DD. Original96/16 entry embargo/purge; causal features and unchanged fills.',
            risk='Scale150 per-trade/open-risk and300 daily-loss budgets by1,1.5,2,2.5,3,4; max position1,2,3,4,6 microcontracts.1800 permanentDD stop and2000 funded-floor remain fixed; costs/impact and volume limits simulated. Caps are research scenarios, not verified account permissions.',
            phase_policy=saved['phase_policy'],unknowns=original['unknowns'],inherited_selection='User chose baseline after observed validation/test outcomes; this lineage is disclosed, not erased. Only the TRAIN baseline artifact is read by this process; holdout archive is not a research input.',validation_accessed=False,test_accessed=False,protected_outcome_files_read=False,independent_confirmation=False,classification='RESEARCH_ONLY')
        json_write(RUN/'protocol.json',protocol)
        snapshot=RUN/'code';snapshot.mkdir()
        for p in sources():shutil.copyfile(p,snapshot/p.name)
        shutil.copytree(ROOT/'runs/mass_training_v2/code/quant_futures',snapshot/'quant_futures')
        (RUN/'cache').mkdir()
        for ext in ('.parquet','.json'):
            p=ROOT/'runs/training_search_100k_v1/cache'/('MNQ_15m'+ext);shutil.copyfile(p,RUN/'cache'/p.name)
    db=sqlite3.connect(RUN/'checkpoints.sqlite');db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS results(config_id TEXT PRIMARY KEY,experiment_order INTEGER UNIQUE,payload TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS checks(config_id TEXT PRIMARY KEY,payload TEXT)')
    return protocol,rows,db


def progress(db,phase):
    count=db.execute('SELECT COUNT(*) FROM results').fetchone()[0]
    r=dict(completed=count,target=TARGET,phase=phase,validation_accessed=False,test_accessed=False,protected_outcome_files_read=False,updated_at=engine.now())
    json_write(ROOT/'reports/E57_REFINEMENT_progress.json',r);print(json.dumps(r),flush=True)


def measured(c,bars,data,folds,features,signal,**kwargs):
    with execution_scope(engine):return engine.evaluate_configuration(c,bars,data,folds,features,signal,**kwargs)


def verify(c,row,bars,data,folds,features,signal,db):
    saved=db.execute('SELECT payload FROM checks WHERE config_id=?',(c['config_id'],)).fetchone()
    if saved:return json.loads(saved[0])
    base=measured(c,bars,data,folds,features,signal,save=True,folder=RUN)
    for a,b in zip(row['fold_metrics'],base):
        for k in ('net_pnl',*DD_FIELDS,'trades'):
            if a[k]!=b[k]:raise ValueError('Training candidate did not reproduce')
    stress=aggregate(c,measured(c,bars,data,folds,features,signal,factor=2,save=True,folder=RUN),signal)
    record=dict(config_id=c['config_id'],base=row,stress_2x=stress,base_reproduced=True,execution_checks=[m['execution_verification'] for m in base],stress_qualified=bool(stress['qualified']))
    json_write(RUN/('check_'+c['config_id']+'.json'),record)
    db.execute('INSERT INTO checks VALUES(?,?)',(c['config_id'],json.dumps(record,allow_nan=False)));db.commit()
    return record


def finish(protocol,rows,db,winner):
    import csv
    fields=[*engine.CSV_FIELDS,'evaluation_phase_qualified','robustness_score','dominates_baseline','pure_scaling_control']
    top=[]
    with (RUN/'ranked.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for rank,(payload,) in enumerate(db.execute("SELECT payload FROM results ORDER BY json_extract(payload,'$.qualified') DESC,json_extract(payload,'$.net_pnl') DESC,json_extract(payload,'$.intrabar_drawdown'),config_id"),1):
            row=json.loads(payload);row['rank']=rank;row['dominates_baseline']=dominates(row,protocol['baseline_training']);row['pure_scaling_control']=row['parameters'].get('pure_scaling_control',False)
            if len(top)<10:top.append(row)
            out={k:row.get(k) for k in fields}
            for k in ('parameters','monthly_pnl','regime_pnl','fold_metrics'):out[k]=json.dumps(out[k],allow_nan=False)
            writer.writerow(out)
    for path,expected in protocol['prior_manifest_hashes'].items():
        if file_hash(path)!=expected:raise ValueError('Prior reserved manifest changed')
    completed=db.execute('SELECT COUNT(*) FROM results').fetchone()[0]
    if not winner and completed!=TARGET:raise ValueError('Cannot claim exhausted budget before200000 trials')
    checks=[json.loads(r[0]) for r in db.execute('SELECT payload FROM checks')]
    scalings=[c for c in checks if c['base']['parameters'].get('pure_scaling_control')]
    assert len(scalings)==len(SCALING_CONTROLS)
    best_scaling=next(iter(sorted((c for c in scalings if c['base']['qualified'] and c['stress_qualified']),key=lambda c:-c['base']['net_pnl'])),None)
    result=dict(completed=completed,planned=TARGET,stopping_reason='verified_training_dominance' if winner else '200000_budget_completed_no_verified_dominance',winner=winner,top10=top,pure_scaling_checks=scalings,best_qualified_scaling=best_scaling,qualified_count=db.execute("SELECT COUNT(*) FROM results WHERE json_extract(payload,'$.qualified')=1").fetchone()[0],baseline_training=protocol['baseline_training'],configuration_sha256=protocol['configurations_sha256'],ranked_sha256=file_hash(RUN/'ranked.csv'),validation_accessed=False,test_accessed=False,protected_outcome_files_read=False,independent_confirmation=False,finished_at=engine.now())
    json_write(RUN/'results.json',result);json_write(ROOT/'reports/E57_REFINEMENT_result.json',result)
    progress(db,result['stopping_reason'])


def run(prepare_only=False):
    protocol,rows,db=setup()
    try:
        if prepare_only or (RUN/'results.json').exists():print(json.dumps(dict(prepared=True,already_complete=(RUN/'results.json').exists())));return
        progress(db,'Loading verified physical MNQ TRAIN')
        bars,meta=engine.load_training('MNQ',RUN);data=engine.arrays(bars);folds=folds_for(bars);masks=session_masks(bars)
        json_write(RUN/'MNQ_source.json',meta);json_write(RUN/'folds.json',folds)
        parent=protocol['baseline_training'];c=parent['parameters']
        if not (RUN/'baseline_reproduction.json').exists():
            features=engine.features(bars,c['lookback']);signal=cached_signal(c,features,masks,{})
            base=aggregate(c,measured(c,bars,data,folds,features,signal,save=True,folder=RUN),signal)
            for k in ('net_pnl',*DD_FIELDS,'trades'):
                if base[k]!=parent[k]:raise ValueError('v1 training baseline mismatch')
            stress=aggregate(c,measured(c,bars,data,folds,features,signal,factor=2,save=True,folder=RUN),signal)
            json_write(RUN/'baseline_reproduction.json',dict(base=base,stress_2x=stress,counts_as_new=False))
        done={r[0] for r in db.execute('SELECT config_id FROM results')};winner=None
        saved_checks=[json.loads(r[0]) for r in db.execute('SELECT payload FROM checks')]
        controls_done=sum(c['base']['parameters'].get('pure_scaling_control',False) for c in saved_checks)
        if controls_done==len(SCALING_CONTROLS):
            eligible=[c for c in saved_checks if c['stress_qualified'] and dominates(c['base'],parent)]
            if eligible:
                winner=min(eligible,key=lambda c:c['base']['parameters']['experiment_order'])
                finish(protocol,rows,db,winner);return
        # Revisit a committed-but-unverified dominance case after an interrupted check;
        # this verifies saved TRAIN metrics, not another unique experiment.
        for (payload,) in db.execute('SELECT payload FROM results ORDER BY experiment_order').fetchall():
            row=json.loads(payload);c=row['parameters']
            if dominates(row,parent) and not any(x['config_id']==c['config_id'] for x in saved_checks):
                f=engine.features(bars,c['lookback']);s=cached_signal(c,f,masks,{})
                checked=verify(c,row,bars,data,folds,f,s,db)
                if checked['stress_qualified'] and controls_done==len(SCALING_CONTROLS):
                    finish(protocol,rows,db,checked);return
        pending=[c for c in rows if c['config_id'] not in done]
        # Seven controls have parentlookback16; all must finish before early stop.
        for lookback,group in groupby(pending,key=lambda c:c['lookback']):
            features=engine.features(bars,lookback);cache={}
            for c in group:
                signal=cached_signal(c,features,masks,cache)
                row=aggregate(c,measured(c,bars,data,folds,features,signal),signal)
                db.execute('INSERT INTO results VALUES(?,?,?)',(c['config_id'],c['experiment_order'],json.dumps(row,allow_nan=False)));done.add(c['config_id'])
                if len(done)%100==0:db.commit();progress(db,f'TRAIN momentum L{lookback}')
                if c['pure_scaling_control'] or dominates(row,parent):
                    check=verify(c,row,bars,data,folds,features,signal,db)
                    if not c['pure_scaling_control'] and check['stress_qualified'] and dominates(row,parent):
                        winner=check;break
                    if c['pure_scaling_control'] and c['experiment_order']==len(SCALING_CONTROLS):
                        controls=[json.loads(r[0]) for r in db.execute('SELECT payload FROM checks')]
                        eligible=[x for x in controls if x['stress_qualified'] and dominates(x['base'],parent)]
                        if eligible:winner=min(eligible,key=lambda x:x['base']['parameters']['experiment_order']);break
            del features,cache;gc.collect()
            if winner:break
        db.commit();finish(protocol,rows,db,winner)
    finally:db.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    with threadpool_limits(limits=1):run(args.prepare_only)

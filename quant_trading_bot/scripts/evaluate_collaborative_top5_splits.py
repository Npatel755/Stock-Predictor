"""Freeze the displayed five TRAIN candidates; validation then test once, no tuning."""
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='1'
import argparse
import gc
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import pandas as pd
from threadpoolctl import threadpool_limits
from quant_futures.config import file_hash,digest
from quant_futures.research import json_write,code_identity
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
DIRECTORY=ROOT/'runs/collaborative_top5_splits_v1'
TRAIN=ROOT/'runs/collaborative_200k_v1'
IDS=('mass_8190d72d308b603c1725','mass_74a481aa30c484a442b6','mass_b839a1ec768d3babc0b7','mass_6dfbc230bb4d7f9f0e83','mass_3f98bb0221b65643d358')
PHASES=('validation','test')
DD_FIELDS=('realized_drawdown','max_drawdown','intrabar_drawdown')


def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def now(): return datetime.now(timezone.utc).isoformat()


def prepare():
    if (DIRECTORY/'frozen_cohort.json').exists():
        verify(); print(json.dumps({'already_frozen':True})); return
    original=read(TRAIN/'protocol.json')
    if code_identity()['source_hash']!=original['core_source_hash']:
        raise ValueError('Core changed from training')
    for name,expected in original['source_hashes'].items():
        if file_hash(TRAIN/'code'/name)!=expected:
            raise ValueError('Archived training source changed')
    with sqlite3.connect('file:'+(TRAIN/'checkpoints.sqlite').as_posix()+'?mode=ro',uri=True) as db:
        candidates=[]
        for rank,cid in enumerate(IDS,1):
            saved=db.execute('SELECT payload FROM results WHERE config_id=?',(cid,)).fetchone()
            if not saved: raise ValueError('Displayed TRAIN candidate missing')
            row=json.loads(saved[0])
            if not row['qualified'] or row['instrument']!='MNQ' or row['parameters']['config_id']!=cid:
                raise ValueError('Displayed candidate identity mismatch')
            candidates.append(dict(display_rank=rank,candidate_id=cid,parameters=row['parameters'],training=row))
    catalog=read(ROOT/'data/catalog.json'); partitions={}
    for phase in PHASES:
        partition=catalog['instruments']['MNQ']['splits'][phase]
        meta=read(Path(partition['path']).with_suffix('.manifest.json'))
        if meta.get('split_role')!=phase or meta.get('instrument')!='MNQ' or meta.get('synthetic') is not False or meta.get('raw_contract_prices') is not True:
            raise PermissionError('Actual matching physical MNQ split required')
        if partition['dataset_version']!=meta['dataset_version']:
            raise ValueError('Split version mismatch')
        partitions[phase]=dict(partition=partition,metadata=meta)
    DIRECTORY.mkdir(exist_ok=False)
    shutil.copytree(TRAIN/'code',DIRECTORY/'strategy')
    shutil.copyfile(__file__,DIRECTORY/'evaluation_runner.py')
    helper=ROOT/'scripts/evaluate_saved_50k_candidate.py'
    shutil.copyfile(helper,DIRECTORY/'split_loader.py')
    frozen=dict(created_at=now(),candidates=candidates,partitions=partitions,
        authorization='User: take all5 and evaluate on validation and test WITHOUT TUNING. All5 remain fixed; no validation-driven selection or changes before test.',
        protocol='Freeze all five configs, strategy sources, loader, runner, costs, gates and both dataset identities before prices. Evaluate all5 once on validation at basecost, then all5 once on test at identical basecost regardless of validation outcomes. One continuous50k account per candidate/split; no yearly resets. First96/last16 entrybars suppressed, causal split-local warmup. Original executions, costs and risk locks unchanged. No fitting, variants, reselection or additional cost scenarios. Saved completed results reused on restart; reservations never reset.',
        core_source_hash=original['core_source_hash'],source_hashes=original['source_hashes'],
        runner_sha256=file_hash(__file__),loader_sha256=file_hash(helper),
        phase_policy=read(ROOT/'configs/user_account_phase_policy.json'),
        preserved_training_files={str(TRAIN/name):file_hash(TRAIN/name) for name in ('protocol.json','configurations.jsonl','ranked.csv','results.json','selected_training_candidate.json')},
        selected_using_training_only=True,periods_previously_observed=True,independent_confirmation=False,operational_eligibility=False,failure_consumes_reservation=True,
        primary_pass='Positive net and cash/closing/intrabar DD each strictly<2000. Additional scenario checks:>=30 trades,no permanent lock,no funded floor breach; evaluation-account scenario also requires50% consistency. Report all outcomes without reordering from them.')
    manifest=dict(cohort=frozen,cohort_hash=digest(frozen))
    json_write(DIRECTORY/'frozen_cohort.json',manifest)
    print(json.dumps(dict(frozen_ids=list(IDS),prices_opened=False,cohort_hash=manifest['cohort_hash'])))


def verify():
    manifest=read(DIRECTORY/'frozen_cohort.json'); frozen=manifest['cohort']
    if digest(frozen)!=manifest['cohort_hash'] or tuple(c['candidate_id'] for c in frozen['candidates'])!=IDS:
        raise ValueError('Frozen cohort changed')
    if file_hash(__file__)!=frozen['runner_sha256'] or file_hash(DIRECTORY/'evaluation_runner.py')!=frozen['runner_sha256'] or file_hash(DIRECTORY/'split_loader.py')!=frozen['loader_sha256']:
        raise ValueError('Frozen evaluation code changed')
    if code_identity()['source_hash']!=frozen['core_source_hash']:
        raise ValueError('Core simulator changed')
    for name,expected in frozen['source_hashes'].items():
        if file_hash(DIRECTORY/'strategy'/name)!=expected:
            raise ValueError('Frozen strategy dependency changed')
    for path,expected in frozen['preserved_training_files'].items():
        if file_hash(path)!=expected:
            raise ValueError('Prior training artifact changed')
    return manifest,frozen


def case_path(candidate,phase):
    return DIRECTORY/(candidate['candidate_id']+'_'+phase+'_result.json')


def validation_hashes(manifest,frozen):
    completed=read(DIRECTORY/'validation_complete.json')
    if completed['cohort_hash']!=manifest['cohort_hash'] or not completed['all_five_completed']:
        raise ValueError('Validation cohort must finish before test access')
    hashes={}
    for candidate in frozen['candidates']:
        path=case_path(candidate,'validation'); result=read(path)
        if result['cohort_hash']!=manifest['cohort_hash'] or result['parameters']!=candidate['parameters']:
            raise ValueError('All5 unchanged validation results must precede any test access')
        hashes[str(path)]=file_hash(path)
    if hashes!=completed['result_hashes']:
        raise ValueError('Validation completion receipt differs from saved results')
    return hashes


def reserve_phase(phase,manifest,frozen):
    if phase not in PHASES: raise PermissionError('Unapproved evaluation phase')
    previous=validation_hashes(manifest,frozen) if phase=='test' else {}
    gate=DIRECTORY/(phase+'_reservation.json')
    reservations={}
    # Bulk reservation is exclusive and happens before resolving any market prices.
    with gate.open('x',encoding='utf-8') as stream:
        json.dump(dict(phase=phase,cohort_hash=manifest['cohort_hash'],candidate_ids=list(IDS),reserved_at=now(),validation_result_hashes=previous,failure_consumes_reservation=True),stream,indent=2)
    for candidate in frozen['candidates']:
        c=candidate['parameters']; cid=candidate['candidate_id']
        version=frozen['partitions'][phase]['partition']['dataset_version']
        key=digest(dict(candidate_id=cid,parameters=c,dataset_version=version))
        role='validation_once' if phase=='validation' else 'reused_tests'
        path=ROOT/'data/manifests'/role/(key+'.json'); path.parent.mkdir(exist_ok=True,parents=True)
        record=dict(candidate_id=cid,parameters=c,phase=phase,cohort_hash=manifest['cohort_hash'],dataset_version=version,reserved_at=now(),no_tuning=True,parameter_variants=1,cost_variants=1,period_previously_observed=True,independent_confirmation=False,failure_consumes_reservation=True,validation_result_hashes=previous)
        with path.open('x',encoding='utf-8') as stream: json.dump(record,stream,indent=2)
        reservations[cid]=str(path)
    json_write(DIRECTORY/(phase+'_reservation_index.json'),reservations)
    return reservations,previous


def load_helpers():
    spec=importlib.util.spec_from_file_location('top5_frozen_split_loader',DIRECTORY/'split_loader.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    helper.DIRECTORY=DIRECTORY  # Only the loader's local module instance; old saved runs stay intact.
    return helper,helper.archive()


def evaluate(phase):
    manifest,frozen=verify()
    completion=DIRECTORY/(phase+'_complete.json')
    if completion.exists():
        receipt=read(completion)
        if receipt['cohort_hash']!=manifest['cohort_hash']: raise ValueError('Completed cohort mismatch')
        for path,expected in receipt['result_hashes'].items():
            if file_hash(path)!=expected: raise ValueError('Saved result changed')
        print(json.dumps(dict(phase=phase,already_complete=True,no_replay=True))); return
    reservations,previous=reserve_phase(phase,manifest,frozen)
    helper,engine=load_helpers(); bars=helper.load_split(phase,frozen); data=engine.arrays(bars)
    json_write(DIRECTORY/(phase+'_loaded_data.json'),dict(role=phase,bars=len(bars),start=str(bars.timestamp_utc.iloc[0]),end=str(bars.timestamp_utc.iloc[-1]),source_coverage=frozen['partitions'][phase]['metadata']['coverage'],dataset_version=frozen['partitions'][phase]['partition']['dataset_version'],loaded_at=now()))
    result_hashes={}
    for candidate in frozen['candidates']:
        c=candidate['parameters']; cid=candidate['candidate_id']
        # Exactly one configuration and one base-cost execution; no outcome branches.
        features=engine.features(bars,c['lookback']); signal=engine.masked_signal(bars,c,features)
        fold=dict(label=phase,start=0,stop=len(bars),embargo_bars=96,purge_bars=16)
        metrics=engine.evaluate_configuration(c,bars,data,[fold],features,signal,save=True,folder=DIRECTORY)[0]
        checks=dict(positive_net=metrics['net_pnl']>0,**{k+'_under_2000':metrics[k]<2000 for k in DD_FIELDS},minimum30_trades=metrics['trades']>=30,no_permanent_lock=not metrics['killed'],no_funded_scenario_breach=not metrics['funded_failed'])
        primary=checks['positive_net'] and all(checks[k+'_under_2000'] for k in DD_FIELDS)
        result=dict(candidate_id=cid,display_rank=candidate['display_rank'],parameters=c,phase=phase,metrics=metrics,checks=checks,profit_and_dd_pass=bool(primary),post_evaluation_scenario_checks_pass=all(checks.values()),evaluation_phase_checks_pass=all(checks.values()) and metrics['consistency_50_pass'],cohort_hash=manifest['cohort_hash'],reservation=reservations[cid],no_tuning=True,parameter_variants_evaluated=1,cost_variants_evaluated=1,period_previously_observed=True,independent_confirmation=False,completed_at=now(),curve_file=cid+'_'+phase+'_equity.parquet',trade_file=cid+'_'+phase+'_trades.parquet')
        path=case_path(candidate,phase)
        if path.exists(): raise FileExistsError('Refuse to overwrite an evaluation result')
        json_write(path,result); result_hashes[str(path)]=file_hash(path)
        pd.read_parquet(DIRECTORY/result['trade_file']).to_csv(DIRECTORY/(cid+'_'+phase+'_trades.csv'),index=False)
        print(json.dumps(dict(phase=phase,candidate_id=cid,metrics={k:metrics[k] for k in ('net_pnl',*DD_FIELDS,'trades','lock')},profit_and_dd_pass=bool(primary))),flush=True)
        del features,signal; gc.collect()
    verify()
    for path,expected in previous.items():
        if file_hash(path)!=expected: raise ValueError('Validation result changed during test')
    json_write(completion,dict(phase=phase,cohort_hash=manifest['cohort_hash'],completed_at=now(),result_hashes=result_hashes,validation_result_hashes=previous,no_tuning=True,all_five_completed=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare',action='store_true');mode.add_argument('--validation',action='store_true');mode.add_argument('--test',action='store_true')
    args=parser.parse_args()
    with threadpool_limits(limits=1):
        if args.prepare: prepare()
        else: evaluate('validation' if args.validation else 'test')

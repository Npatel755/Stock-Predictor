"""Another fixed10k training-only batch with unchanged pre-test search design.

No imports or reads of validation/test results; only prior configuration IDs
are consumed to exclude duplicates. Historical result files remain immutable.
"""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'): os.environ[key]='1'
import argparse
import gc
import json
from pathlib import Path
import shutil
import sqlite3
from itertools import groupby
from threadpoolctl import threadpool_limits
import mass_research as engine
from mass_continuation_configurations import generate,SEED,semantic_key,metadata,INSTRUMENTS,TARGET
from quant_futures.config import file_hash,digest
from quant_futures.research import code_identity,json_write

ROOT=engine.ROOT
PRIOR=ROOT/'runs/mass_training_v2'
RUN=ROOT/'runs/mass_training_continuation_v1'


def sources():
    return [Path(__file__),Path(__file__).with_name('mass_continuation_configurations.py'),*engine.sources()]


def setup(folder,seed):
    prior_protocol=engine.read(PRIOR/'protocol.json')
    # Verify only code/provenance; never read prior P&L or protected outcomes.
    if code_identity()['source_hash']!=prior_protocol['source_hash']: raise ValueError('Core dependencies changed')
    for path in engine.sources():
        if file_hash(path)!=prior_protocol['source_hashes'][path.name]: raise ValueError('Original search design changed')
    excluded_manifest=PRIOR/'configurations.jsonl'
    excluded={semantic_key(json.loads(line)) for line in excluded_manifest.read_text(encoding='utf-8').splitlines() if line.strip()}
    if len(excluded)!=10000: raise ValueError('Expected the prior10k distinct active configurations')
    rows=generate(excluded,seed)
    universe=metadata(rows,seed)
    identity={p.name:file_hash(p) for p in sources()}
    folder.mkdir(parents=True,exist_ok=True)
    protocol_path=folder/'protocol.json'
    if protocol_path.exists():
        protocol=engine.read(protocol_path)
        if (protocol['source_hashes']!=identity or protocol['universe']!=universe
                or protocol['excluded_manifest_sha256']!=file_hash(excluded_manifest)):
            raise ValueError('Frozen continuation changed; cannot resume')
        for path,expected in protocol['preserved_training_files'].items():
            if file_hash(path)!=expected: raise ValueError('Prior training artifacts changed')
    else:
        protocol=dict(created_at=engine.now(),seed=seed,target=TARGET,universe=universe,source_hashes=identity,
            **code_identity(),prior_run=str(PRIOR),prior_protocol_sha256=file_hash(PRIOR/'protocol.json'),
            excluded_manifest_sha256=file_hash(excluded_manifest),excluded_unique_active=len(excluded),
            preserved_training_files={str(PRIOR/name):file_hash(PRIOR/name) for name in
                ('protocol.json','ranked.csv','frozen_top10.json','frozen_best_training.json','results.json')},
            split_policy=prior_protocol['split_policy'],execution=prior_protocol['execution'],
            fee_assumption=prior_protocol['fee_assumption'],walkforward=prior_protocol['walkforward'],
            ranking=prior_protocol['ranking'],unknowns=prior_protocol['unknowns'],
            design='Identical original family/parameter domains, execution, costs, risk, folds, qualification and composite score. Only the fixed seed advances; prior active configurations are excluded irrespective of instrument. No search choice uses validation/test results.',
            validation_accessed=False,test_accessed=False,validation_test_results_read=False,
            no_live_execution=True,status='RESEARCH_ONLY',
            stage2='After all10k finish, freeze top10. Reproduce their training runs, check ledger/shared fills, and run the original2x cost diagnostic. Do not evaluate validation or test.')
        json_write(protocol_path,protocol)
        with (folder/'configurations.jsonl').open('x',encoding='utf-8') as stream:
            for c in rows: stream.write(json.dumps(c,sort_keys=True)+'\n')
        snapshot=folder/'code';snapshot.mkdir(exist_ok=False)
        for path in sources(): shutil.copyfile(path,snapshot/path.name)
        shutil.copytree(PRIOR/'code/quant_futures',snapshot/'quant_futures')
        shutil.copyfile(PRIOR/'code/lucidflex_snapshot.yaml',snapshot/'lucidflex_snapshot.yaml')
        shutil.copyfile(PRIOR/'code/runtime_versions.json',snapshot/'runtime_versions.json')
        # Reuse immutable TRAIN-only preprocessing, verified again by loader.
        (folder/'cache').mkdir()
        for symbol in INSTRUMENTS:
            for suffix in ('.parquet','.json'):
                old=PRIOR/'cache'/(symbol+'_15m'+suffix)
                shutil.copyfile(old,folder/'cache'/old.name)
    connection=sqlite3.connect(folder/'checkpoints.sqlite')
    connection.execute('CREATE TABLE IF NOT EXISTS results (config_id TEXT PRIMARY KEY,instrument TEXT NOT NULL,payload TEXT NOT NULL)')
    return rows,protocol,connection


def progress(folder,connection,phase):
    counts=dict(connection.execute('SELECT instrument,COUNT(*) FROM results GROUP BY instrument'))
    value=dict(run_path=str(folder),target=TARGET,completed=sum(counts.values()),unique_configs=sum(counts.values()),
        prior_completed_unique=10000,phase=phase,per_market=counts,updated_at=engine.now(),
        validation_accessed=False,test_accessed=False,validation_test_results_read=False)
    json_write(ROOT/'reports/mass_continuation_progress.json',value)
    print(json.dumps(value),flush=True)


def run(folder=RUN,seed=SEED):
    rows,protocol,db=setup(folder,seed)
    completed={row[0] for row in db.execute('SELECT config_id FROM results')}
    for symbol in INSTRUMENTS:
        pending=[c for c in rows if c['instrument']==symbol and c['config_id'] not in completed]
        if not pending: continue
        progress(folder,db,'loading TRAIN '+symbol)
        bars,meta=engine.load_training(symbol,folder)
        json_write(folder/(symbol+'_source.json'),meta)
        data=engine.arrays(bars);folds=engine.fold_slices(bars,symbol)
        json_write(folder/(symbol+'_folds.json'),folds)
        for lookback,group in groupby(sorted(pending,key=lambda c:c['lookback']),key=lambda c:c['lookback']):
            features=engine.features(bars,lookback)
            for c in group:
                signal=engine.masked_signal(bars,c,features)
                measured=engine.evaluate_configuration(c,bars,data,folds,features,signal)
                row=engine.aggregate(c,measured,signal)
                db.execute('INSERT INTO results VALUES (?,?,?)',(c['config_id'],symbol,json.dumps(row,allow_nan=False)))
                completed.add(c['config_id'])
                if len(completed)%25==0: db.commit()
                if len(completed)%100==0: progress(folder,db,'training search '+symbol)
            del features;gc.collect()
        db.commit();del bars,data;gc.collect()
    all_rows=[json.loads(row[0]) for row in db.execute('SELECT payload FROM results')]
    if len(all_rows)!=TARGET or len({r['config_id'] for r in all_rows})!=TARGET: raise RuntimeError('Incomplete batch')
    progress(folder,db,'ranking complete training-only batch')
    ordered=engine.write_ranked(folder,all_rows);top10=ordered[:10]
    frozen=dict(frozen_at=engine.now(),configurations=top10,ranked_csv_sha256=file_hash(folder/'ranked.csv'),
        configuration_manifest_sha256=file_hash(folder/'configurations.jsonl'),source_hashes=protocol['source_hashes'],
        selection_basis='All10k new configurations completed; unchanged training-only composite',
        validation_accessed=False,test_accessed=False)
    if (folder/'frozen_top10.json').exists():
        if engine.read(folder/'frozen_top10.json')['ranked_csv_sha256']!=frozen['ranked_csv_sha256']: raise ValueError('Frozen ranking changed')
    else: json_write(folder/'frozen_top10.json',frozen)
    verification=[]
    for row in top10:
        c=row['parameters'];progress(folder,db,'training finalist checks '+c['config_id'])
        bars,_=engine.load_training(c['instrument'],folder)
        data=engine.arrays(bars);folds=engine.fold_slices(bars,c['instrument'])
        features=engine.features(bars,c['lookback']);signal=engine.masked_signal(bars,c,features)
        measured=engine.evaluate_configuration(c,bars,data,folds,features,signal,save=True,folder=folder)
        stress=engine.evaluate_configuration(c,bars,data,folds,features,signal,factor=2,save=True,folder=folder)
        for original,replayed in zip(row['fold_metrics'],measured):
            for key in ('net_pnl','max_drawdown','realized_drawdown','intrabar_drawdown','trades'):
                if original[key]!=replayed[key]: raise ValueError('Finalist reproduction failed')
        verification.append(dict(config_id=c['config_id'],base_reproduced=True,stress_2x=engine.aggregate(c,stress,signal),
            execution_parity=[m['execution_verification'] for m in measured],operational_eligibility=False))
        json_write(folder/'finalist_training_checks.json',verification)
        del bars,data,features,signal,measured,stress;gc.collect()
    result=dict(run_path=str(folder),target=TARGET,completed=TARGET,unique_configs=TARGET,
        prior_unique_configs=10000,cumulative_unique_active_configs=20000,qualified_count=sum(r['qualified'] for r in ordered),
        top10=top10,seed=seed,source_hashes=protocol['source_hashes'],split_policy=protocol['split_policy'],
        execution_verification=verification,validation_accessed=False,test_accessed=False,validation_test_results_read=False,
        fresh_holdout_available=False,validation_status='blocked_previously_observed',test_status='blocked_previously_observed',
        profitability_status='TRAINING_ONLY; independent performance unconfirmed',
        funded_status='UNVERIFIED contractual rules/actual charges; scenario diagnostics only',
        prior_training_artifacts_preserved=True,finished_at=engine.now())
    for path,expected in protocol['preserved_training_files'].items():
        if file_hash(path)!=expected: raise ValueError('Prior training artifacts changed')
    json_write(folder/'results.json',result)
    json_write(ROOT/'reports/mass_continuation_result.json',result)
    progress(folder,db,'training complete; no validation/test evaluation')
    db.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,default=RUN);parser.add_argument('--seed',type=int,default=SEED)
    args=parser.parse_args()
    with threadpool_limits(limits=1): run(args.run.resolve(),args.seed)

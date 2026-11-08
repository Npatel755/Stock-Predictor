"""Archive the user-selected existing strategy/results; never run prices."""
import json
from pathlib import Path
import shutil
import sqlite3
from quant_futures.config import file_hash,digest
from quant_futures.research import json_write
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
ID='mass_e57ba183f302b3ba886b'
DEST=ROOT/'strategy_versions/mnq_momentum_e57/v1.0.0'


def main():
    if (DEST/'manifest.json').exists():
        manifest=json.loads((DEST/'manifest.json').read_text(encoding='utf-8'))
        for rel,expected in manifest['files'].items():
            if file_hash(DEST/rel)!=expected: raise ValueError('Immutable v1 archive changed')
        print(json.dumps(dict(already_saved=True,version='1.0.0',path=str(DEST))));return
    source=ROOT/'runs/top15_500k_val_test_v1'
    cohort=json.loads((source/'frozen_candidates.json').read_text(encoding='utf-8'))
    candidate=next(c for c in cohort['candidates'] if c['config_id']==ID)
    train=ROOT/'runs/training_search_500k_v1'
    with sqlite3.connect('file:'+(train/'checkpoints.sqlite').as_posix()+'?mode=ro',uri=True) as db:
        row=json.loads(db.execute('SELECT payload FROM results WHERE config_id=?',(ID,)).fetchone()[0])
    if candidate['parameters']!=row['parameters'] or row['net_pnl']!=4935.5 or row['intrabar_drawdown']!=533.25:
        raise ValueError('Screenshot baseline identity changed')
    DEST.mkdir(parents=True,exist_ok=False)
    json_write(DEST/'training_baseline.json',dict(version='1.0.0',strategy_id=ID,parent_id=None,parameters=row['parameters'],training=row,training_source_run=str(train),source_protocol=json.loads((train/'protocol.json').read_text(encoding='utf-8')),selection_provenance='User selected this baseline after observing historical validation/test results. New refinements may use TRAIN only, but inherited selection cannot be made independent. Validation/test archive is not a tuning input.',phase_policy=json.loads((ROOT/'configs/user_account_phase_policy.json').read_text(encoding='utf-8'))))
    shutil.copytree(source/'strategy',DEST/'strategy')
    shutil.copyfile(source/'frozen_candidates.json',DEST/'original_frozen_cohort.json')
    shutil.copyfile(source/'runner.py',DEST/'original_evaluation_runner.py')
    snapshots={}
    for phase in ('validation','test'):
        rows=json.loads((source/(phase+'_results.json')).read_text(encoding='utf-8'))
        saved=next(r for r in rows if r['config_id']==ID)
        if saved['parameters']!=row['parameters']: raise ValueError('Saved split configuration differs')
        json_write(DEST/(phase+'_existing_result.json'),saved)
        snapshots[phase]={k:saved[k] for k in ('net_pnl','intrabar_drawdown','trades','lock')}
        for directory,suffix in (('curves','equity'),('trades','trades')):
            p=source/directory/(ID+'_'+phase+'_'+suffix+'.parquet')
            shutil.copyfile(p,DEST/p.name)
    files={str(p.relative_to(DEST)):file_hash(p) for p in DEST.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    manifest=dict(version='1.0.0',strategy_id=ID,created_at=datetime.now(timezone.utc).isoformat(),immutable=True,parent_id=None,parameter_hash=digest(row['parameters']),files=files,existing_split_results=snapshots,new_evaluations=0,independent_confirmation=False)
    json_write(DEST/'manifest.json',manifest)
    (DEST/'README.md').write_text('# MNQ momentum baseline v1.0.0\n\nImmutable user-selected strategy `'+ID+'`. Training: +$4,935.50 net; $533.25 worst annual intrabar drawdown; 202 trades. Existing validation/test results, source, parameters, trade logs and curves are archived without replay. The baseline was selected after those outcomes were observed. Further development uses TRAIN only; old holdouts remain consumed. Nothing is promoted to live trading.\n',encoding='utf-8')
    registry=ROOT/'research/strategy_memory';registry.mkdir(parents=True,exist_ok=True)
    with (registry/'events.jsonl').open('a',encoding='utf-8') as stream:
        for kind in ('hypothesis','implementation','run','result','lesson'):
            stream.write(json.dumps(dict(schema_version=1,record_type=kind,strategy_id=ID,version='1.0.0',parent_id=None,hypothesis='Past-only normalized momentum, ATR exits and session control',market='MNQ',family='momentum',timeframe_minutes=15,artifact=str(DEST/'manifest.json'),new_evaluations=0,decision='PRESERVED_BASELINE_RESEARCH_ONLY',lesson='User-selected after observed holdouts; archive results only, do not use them to tune. Training metrics are four annual reset accounts.',recorded_at=manifest['created_at']))+'\n')
    (registry/'lessons.md').write_text('# Strategy memory\n\n- e57 baseline v1.0.0 preserves the user-selected momentum strategy and consumed holdout history. New challengers must be compared on training only; future independent confirmation needs fresh forward observations.\n',encoding='utf-8')
    print(json.dumps(dict(saved=True,version='1.0.0',path=str(DEST),new_evaluations=0)))


if __name__=='__main__': main()

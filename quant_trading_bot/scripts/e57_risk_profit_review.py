"""Frozen supplemental TRAIN-only profit-first review under the user's2k risk cap."""
import gc
import json
from pathlib import Path
import shutil
import sqlite3
import sys
from threadpoolctl import threadpool_limits
import e57_training_refinement as study
from quant_futures.config import file_hash
from quant_futures.research import json_write,code_identity

FOLDER=study.ROOT/'runs/e57_risk_profit_review_v1'


def register():
    FOLDER.mkdir(exist_ok=True)
    path=FOLDER/'pre_registered_rule.json'
    rule=dict(created_at=study.engine.now(),authorization='User additionally authorizes larger position/risk budgets to increase net while retaining<2000DD. This supplements, not changes, the frozen no-extra-DD early-stop search.',selection='After parent search stops, take up to20 completed quality-qualified configurations with net above v1 baseline, ranked TRAIN net descending,intrabarDD ascending,ID. Freeze this exact shortlist and source/result identities BEFORE this stage loads prices. Reproduce base and2x costs in fixed order; first survivor of the same TRAIN gates wins. No new configs, optimization or holdout access.',maximum_candidate_verifications=20,validation_accessed=False,test_accessed=False,protected_outcome_files_read=False,source_sha256=file_hash(__file__),parent_run=str(study.RUN),classification='RESEARCH_ONLY')
    if path.exists():
        old=study.engine.read(path)
        if old['source_sha256']!=rule['source_sha256']:raise ValueError('Frozen supplemental code changed')
    else:
        json_write(path,rule);shutil.copyfile(__file__,FOLDER/'review_runner.py')


def run():
    register()
    if (FOLDER/'results.json').exists():print(json.dumps(dict(already_complete=True)));return
    protocol=study.engine.read(study.RUN/'protocol.json');parent=study.engine.read(study.RUN/'results.json')
    if protocol['source_hashes']!={p.name:file_hash(p) for p in study.sources()} or code_identity()['source_hash']!=protocol['core_source_hash']:
        raise ValueError('Parent simulator or adapter changed')
    plan=FOLDER/'frozen_shortlist.json'
    if plan.exists():
        frozen=study.engine.read(plan)
        if frozen['parent_result_sha256']!=file_hash(study.RUN/'results.json'):raise ValueError('Parent result changed')
    else:
        with sqlite3.connect('file:'+(study.RUN/'checkpoints.sqlite').as_posix()+'?mode=ro',uri=True) as db:
            rows=[json.loads(r[0]) for r in db.execute("SELECT payload FROM results WHERE json_extract(payload,'$.qualified')=1 AND json_extract(payload,'$.net_pnl')>? ORDER BY json_extract(payload,'$.net_pnl') DESC,json_extract(payload,'$.intrabar_drawdown'),config_id LIMIT20".replace('LIMIT20','LIMIT 20'),(protocol['baseline_training']['net_pnl'],))]
        frozen=dict(created_at=study.engine.now(),shortlist=rows,parent_result_sha256=file_hash(study.RUN/'results.json'),parent_protocol_sha256=file_hash(study.RUN/'protocol.json'),source_sha256=file_hash(__file__),parameter_variants=0,validation_accessed=False,test_accessed=False)
        json_write(plan,frozen)
    if frozen['source_sha256']!=file_hash(__file__) or file_hash(FOLDER/'review_runner.py')!=file_hash(__file__):raise ValueError('Review runner changed')
    bars,meta=study.engine.load_training('MNQ',study.RUN);data=study.engine.arrays(bars);folds=study.folds_for(bars);masks=study.session_masks(bars)
    db=sqlite3.connect(FOLDER/'verification.sqlite');db.execute('CREATE TABLE IF NOT EXISTS checks(config_id TEXT PRIMARY KEY,payload TEXT)')
    winner=None;checked=[]
    try:
        for row in frozen['shortlist']:
            c=row['parameters'];f=study.engine.features(bars,c['lookback']);signal=study.cached_signal(c,f,masks,{})
            # Same frozen trading/source code; artifacts reside in parent run for consistent names.
            check=study.verify(c,row,bars,data,folds,f,signal,db)
            checked.append(check);del f,signal;gc.collect()
            if check['stress_qualified']:
                winner=check;break
        result=dict(winner=winner,checked=checked,shortlisted=len(frozen['shortlist']),unique_new_configurations=0,selection='Highest TRAIN profit among the frozen top20 completed quality-qualified cases surviving unchanged2x costs. Larger DD than baseline is allowed, strictly<2000.',parent_completed=parent['completed'],validation_accessed=False,test_accessed=False,protected_outcome_files_read=False,independent_confirmation=False,finished_at=study.engine.now())
        json_write(FOLDER/'results.json',result)
        print(json.dumps(dict(checked=len(checked),winner_id=winner['config_id'] if winner else None,net=winner['base']['net_pnl'] if winner else None)))
    finally:db.close()


if __name__=='__main__':
    with threadpool_limits(limits=1):
        if '--register-only' in sys.argv:register()
        else:run()

"""Fixed selected versions on one continuous TRAIN account, no parameter changes."""
import json
import numpy as np
from threadpoolctl import threadpool_limits
import e57_training_refinement as study
from quant_futures.config import file_hash
from quant_futures.research import json_write

FOLDER=study.ROOT/'runs/e57_continuous_training_v1'


def main():
    FOLDER.mkdir(exist_ok=True)
    if (FOLDER/'results.json').exists():print(json.dumps(dict(already_complete=True)));return
    parent=study.engine.read(study.RUN/'results.json')
    review=study.engine.read(study.ROOT/'runs/e57_risk_profit_review_v1/results.json')
    protocol=study.engine.read(study.RUN/'protocol.json')
    if protocol['source_hashes']!={p.name:file_hash(p) for p in study.sources()}:raise ValueError('Frozen trading code changed')
    candidates={'baseline':parent['baseline_training']['parameters']}
    for label,c in (('scaling',parent['best_qualified_scaling']),('challenger',parent['winner']),('profit_with_risk_cap',review['winner'])):
        if c:candidates[label]=c['base']['parameters']
    plan=dict(created_at=study.engine.now(),candidates=candidates,selection='One diagnostic per unique already-selected configuration, at base and2x costs, on continuous2020-2023 TRAIN account. No recalibration, replacement search, validation/test access, or unique new configurations.',parent_result_sha256=file_hash(study.RUN/'results.json'),review_result_sha256=file_hash(study.ROOT/'runs/e57_risk_profit_review_v1/results.json'),source_sha256=file_hash(__file__),trading_source_hashes=protocol['source_hashes'],unique_new_configurations=0,validation_accessed=False,test_accessed=False)
    if (FOLDER/'protocol.json').exists():
        saved=study.engine.read(FOLDER/'protocol.json')
        for k in ('candidates','parent_result_sha256','review_result_sha256','source_sha256','trading_source_hashes'):
            if saved[k]!=plan[k]:raise ValueError('Frozen continuous check changed')
    else:json_write(FOLDER/'protocol.json',plan)
    bars,_=study.engine.load_training('MNQ',study.RUN);data=study.engine.arrays(bars);masks=study.session_masks(bars)
    import pandas as pd
    ids=np.flatnonzero((bars.timestamp_utc>=pd.Timestamp('2020-01-01T00:00Z'))&(bars.timestamp_utc<pd.Timestamp('2024-01-01T00:00Z')))
    fold=dict(label='continuous_train',start=int(ids[0]),stop=int(ids[-1])+1,embargo_bars=96,purge_bars=16)
    results={}
    for c in {c['config_id']:c for c in candidates.values()}.values():
        path=FOLDER/(c['config_id']+'_result.json')
        if path.exists():
            r=study.engine.read(path)
            if r['parameters']!=c:raise ValueError('Saved continuous configuration changed')
        else:
            f=study.engine.features(bars,c['lookback']);s=study.cached_signal(c,f,masks,{})
            base=study.measured(c,bars,data,[fold],f,s,save=True,folder=FOLDER)[0]
            stress=study.measured(c,bars,data,[fold],f,s,factor=2,save=True,folder=FOLDER)[0]
            def passes(m):return bool(m['net_pnl']>0 and all(m[k]<2000 for k in study.DD_FIELDS) and not m['killed'] and not m['funded_failed'])
            r=dict(parameters=c,base=base,stress_2x=stress,base_profit_dd_no_lock_pass=passes(base),stress_profit_dd_no_lock_pass=passes(stress),unique_new_configurations=0,validation_accessed=False,test_accessed=False)
            json_write(path,r)
        results[c['config_id']]=r
    record=dict(candidates=candidates,results=results,unique_new_configurations=0,validation_accessed=False,test_accessed=False,independent_confirmation=False,finished_at=study.engine.now())
    json_write(FOLDER/'results.json',record)
    print(json.dumps({label:{k:results[c['config_id']]['base'][k] for k in ('net_pnl','intrabar_drawdown','trades','lock')} for label,c in candidates.items()}))


if __name__=='__main__':
    with threadpool_limits(limits=1):main()

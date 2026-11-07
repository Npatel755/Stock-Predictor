"""User-provided account-phase classification; trading execution is unchanged."""
import csv
import json
from pathlib import Path
import mass_research as engine
from mass_configurations import semantic_key
from quant_futures.config import file_hash

BENCHMARK_ID='mass_ca28dbb9316d2d9ced10'


def aggregate(configuration,folds,signal):
    row=engine.aggregate(configuration,folds,signal)
    row['evaluation_phase_qualified']=row['qualified']
    row['qualified']=bool(all(m['net_pnl']>0 and m['trades']>=30 and not m['killed'] and not m['funded_failed'] for m in folds)
        and all(row[k]<2000 for k in ('realized_drawdown','max_drawdown','intrabar_drawdown')))
    return row


def prior_training(root,names):
    excluded=set();preserved={};benchmark=None
    for name in names:
        folder=Path(root)/'runs'/name
        for filename in ('protocol.json','ranked.csv','configurations.jsonl','results.json'):
            preserved[str(folder/filename)]=file_hash(folder/filename)
        for line in (folder/'configurations.jsonl').read_text(encoding='utf-8').splitlines():
            excluded.add(semantic_key(json.loads(line)))
        with (folder/'ranked.csv').open(encoding='utf-8',newline='') as stream:
            for row in csv.DictReader(stream):
                if row['config_id']==BENCHMARK_ID:
                    benchmark=dict(config_id=row['config_id'],parameters=json.loads(row['parameters']),
                        net_pnl=float(row['net_pnl']),max_drawdown=float(row['max_drawdown']),
                        realized_drawdown=float(row['realized_drawdown']),intrabar_drawdown=float(row['intrabar_drawdown']),
                        fold_metrics=json.loads(row['fold_metrics']))
    if len(excluded)!=70000 or benchmark is None: raise ValueError('Expected70k prior configurations and saved TRAIN benchmark')
    if benchmark['net_pnl']!=9972.5: raise ValueError('Saved training benchmark changed')
    return excluded,benchmark,preserved

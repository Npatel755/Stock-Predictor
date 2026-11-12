"""Reproduce Gemini's stack research and cache TRAIN-only raw sleeve books.

Legacy mode preserves the original data-hole/router assumptions for audit.
Causal mode fills the known2019 TRAIN splice hole and routes by signal entry
availability. No validation/test/paper price or outcome files are loaded.
"""
import os
for n in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='1'
import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/gemini_stack_continuation_v1'
EXTRAS=[('AG_BRK30_1c','ag_all_weather',16),('AG_MORN30_1c','ag_quad',17),
        ('AG_TRD30PM_1c_v52','ag_arch_d_plus_v2_1c_v52',18),('AG_TRD60Q_1c','ag_quad',19),
        ('AG_MES_TRD30_1c','ag_quad',20),('MNQ_E57_1c','ensemble_epsilon',20),('MES_MOM_1c','ensemble_epsilon',20)]


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def route_causal(df):
    kept=[];until=None;last=None
    for r in df.sort_values(['tin','prio'],kind='stable').itertuples():
        if until is not None and (r.tin<until or r.tin==last):continue
        until=r.tout if until is None else max(until,r.tout);last=r.tin;kept.append(r.Index)
    return df.loc[kept]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['legacy','causal'],required=True);args=parser.parse_args()
    mode=args.mode;folder=RUN/mode;folder.mkdir(parents=True,exist_ok=True)
    if not (RUN/'protocol.json').exists():raise RuntimeError('Freeze protocol before price access')
    if (folder/'complete.json').exists():print(mode,'already prepared;preserved',flush=True);return
    os.environ['TRAIN_MINI_UNTIL']='2019-01-01' if mode=='legacy' else '2019-05-06'
    sys.path.insert(0,str(ROOT/'src'))
    import mass_1m_search as m1
    old=m1.load_bars;loads=[]
    def guarded(product,res,start,end,split):
        if split!='train' or pd.Timestamp(end)>pd.Timestamp('2024-01-01'):raise PermissionError('TRAIN-only boundary')
        b=old(product,res,start,end,split)
        if len(b) and not b.timestamp_utc.lt(pd.Timestamp('2024-01-01T00:00Z')).all():raise PermissionError('Observation beyond TRAIN')
        loads.append(dict(product=product,res=res,start=start,end=end,role=split,rows=len(b)))
        print(mode,'TRAIN',product,res,len(b),flush=True);return b
    m1.load_bars=guarded
    source=ROOT/'scripts/research_uncapped_and_sleeves.py';text=source.read_text(encoding='utf-8')
    prefix=text.split('print("Building tables')[0]
    V=dict(__name__='stack_train_prepare',__file__=str(source));exec(prefix,V)
    base=V['df_base'];cols=base.columns;pl=V['pl'];P10=V['P10'];ep,bars_for,START=P10['ep'],P10['bars_for'],P10['START']
    books={k:V[name] for k,name in [('base','df_base'),('both','df_both')]}
    triple=pd.concat([V['df_vol']],ignore_index=True)
    optional={}
    for index,(name,key,prio) in enumerate(EXTRAS):
        if mode=='legacy' and index>=3:continue
        sl=next(s for s in ep.CANDIDATES[key]['sleeves'] if s['name']==name)
        x=pl.price_normalize(pl.sleeve_trades(ep,bars_for,START,dict(sl),prio,False))
        x['n_contracts']=1.;x['mae_per_micro']=0.
        x=x[cols];optional[name]=x
        print(mode,'rawsleeve',name,len(x),flush=True)
        if index<3:triple=pd.concat([triple,x],ignore_index=True)
    books['triple']=triple
    if mode=='causal':
        for name,x in list(optional.items())[3:]:books['triple+'+name]=pd.concat([triple,x],ignore_index=True)
    for name,b in books.items():b.to_parquet(folder/('raw_'+name.replace('+','_')+'.parquet'),index=False)
    V['N0'].to_parquet(folder/'overnight_training.parquet',index=False)
    # Preserve old entry-label router ONLY in legacy reproduction. A candidate
    # cannot receive a new improvement label using that router.
    if mode=='causal':pl.route=route_causal
    table={};risk={}
    for name,b in books.items():
        table[name],risk[name]=V['build_tables'](b)
        print(mode,'tablescomplete',name,flush=True)
    days=sorted(set().union(*(set(d) for name in table for d in table[name].values())))
    names=list(books);scenarios=['S0','S3','S4'];axis=pd.DatetimeIndex(days).as_unit('ns').asi8//86400000000000
    nets=np.zeros((len(names),3,4,2,len(days)));risks=np.zeros((len(names),3,4,len(days)))
    for bi,name in enumerate(names):
        for si,scenario in enumerate(scenarios):
            for mi,m in enumerate((1,2,3,4)):
                risks[bi,si,mi]=[risk[name][(scenario,m)].get(d,0.) for d in days]
                for ni,night in enumerate((False,True)):nets[bi,si,mi,ni]=[table[name][(scenario,m,night)].get(d,0.) for d in days]
    np.savez_compressed(folder/'tables.npz',net=nets,risk=risks,dates=axis)
    meta=dict(mode=mode,books=names,scenarios=scenarios,rows=len(days),training_loads=loads,mini_until=m1.MINI_UNTIL,normalization=pl.TODAY,night_risk=V['NIGHT_RISK'],tables_sha256=sha(folder/'tables.npz'),validation_accessed=False,test_accessed=False)
    (folder/'complete.json').write_text(json.dumps(meta,indent=2,default=str)+'\n')
    if mode=='legacy':
        fn=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='simulate_advanced')
        V['SER_BASE'],V['RISK_BASE']=table['base'],risk['base'];V['SER_BOTH'],V['RISK_BOTH']=table['both'],risk['both']
        exec(compile(ast.Module(body=[fn],type_ignores=[]),str(source),'exec'),V)
        result={s:V['simulate_advanced'](s,((0,1),(4000,2),(4600,3),(5400,4)),table['triple'],risk['triple'],8600.,8700.,8700.,1500.) for s in scenarios}
        (folder/'original_gemini_reproduction.json').write_text(json.dumps(result,indent=2)+'\n')
        print('GEMINI LEGACY REPRODUCTION',json.dumps(result),flush=True)
    print(mode,'COMPLETE',json.dumps({k:v for k,v in meta.items() if k!='training_loads'}),flush=True)


if __name__=='__main__':main()

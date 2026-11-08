"""Bounded 2,000-case mechanism-diverse futures experiment. Never loads TEST.

TRAIN: four 2020--2023 internal annual forward folds. Models fit before each
fold, with an eight-day gap. Freeze everything before the all-case validation
selection pass, following the user's established workflow. No refitting on V.
"""
import os
for _n in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[_n]='1'
import argparse
import ast
import csv
import io
import json
from pathlib import Path
import shutil
import sqlite3
import zlib
import numpy as np
import pandas as pd
import mass_research as engine
from training_search_100k import folds_for
from novel_futures_signals import FAMILIES,FITTED,SEED,universe,key,primitives,fit_model,value
from quant_futures.config import file_hash,digest
from quant_futures.data import canonical,validate as audit_bars
from quant_futures.dataset_catalog import resolve_dataset

ROOT=engine.ROOT
RUN=ROOT/'runs/novel_futures_2k_v1'
SYMBOLS=('MNQ','MES')
DD=('max_drawdown','realized_drawdown','intrabar_drawdown')


def write(path,obj):engine.json_write(path,obj)
def read(path):return engine.read(path)
def sources():return [Path(__file__),Path(__file__).with_name('novel_futures_signals.py'),*engine.sources(),Path(__file__).with_name('training_search_100k.py')]
def pack(raw):
    out=io.BytesIO();np.savez_compressed(out,**{k:v for k,v in raw.items() if k.startswith('trade_')});return out.getvalue()


def setup():
    rows=universe();RUN.mkdir(parents=True,exist_ok=True)
    identity={p.name:file_hash(p) for p in sources()}
    common=ROOT/'runs/mass_training_v2'
    dependencies={str(p.relative_to(ROOT)):file_hash(p) for p in (ROOT/'src/quant_futures').glob('*.py')}
    protocol=dict(target=2000,seed=SEED,families=FAMILIES,markets=list(SYMBOLS),source_hashes=identity,
      dependency_hashes=dependencies,configuration_hash=digest(rows),
      authorization='User requests another2000 RADICALLY DIFFERENT FUTURES strategies, continuing the established TRAIN-then-all-frozen-VALIDATION selection workflow; no TEST access.',
      novelty='Eight entry mechanisms absent from the ten-family mass-search library.250 configurations per mechanism,125 per market. Active configurations unique even ignoring instrument. These are2000 correlated configurations,not2000 independent economic discoveries.',
      origin='Original researcher hypotheses,derived from available OHLCV/training inputs;no external profitability claims.',
      data='Same actual15m raw-contract bars and existing physical splits. MNQ/MES trained2020-2023; earlier TRAIN supplies causal warmup/fit. No crypto.',
      training='Separate50k annual accounts2020/21/22/23. First96 and last16 decision bars suppressed. Five forecast models fit only before each calendar year minus8days; fitted lookback=last L*92 observations (approximately Lsessions). Three descriptive signals use Lbars. Account execution unchanged.',
      qualification='All4 annual nets positive;>=30trades/year;<=800total;PF>=1.30;all cash,closing,intrabarDD strictly<2000;no permanent lock/funded breach.50%consistency is separate evaluation-account-only diagnostic.',
      rank='TRAIN qualify first,net descending,intrabarDD ascending,ID. VALIDATION scenario-pass first,net descending,intrabarDD ascending,ID. Report best both-qualified separately. No outcome-driven reruns or revised parameters.',
      validation='Evaluate every frozen configuration once on2024-25,one continuous50kaccount,base costs only;all learned models fit before2024-01-01 minus8days and remain fixed. Previous periods already observed;validation is selection,not independent confirmation. No automatic new batch after failure.',
      execution=read(common/'protocol.json')['execution'],
      cost_stress='Frozen TRAIN top5 only,2x cost factor,diagnostic;not validation variants.',
      model_fit_controls='No evaluated labels enter a fold fit. Histograms/regressions serialized before execution; validation parameters/models frozen before V prices loaded.',
      unknowns=read(common/'protocol.json')['unknowns'],test_accessed=False,no_live_execution=True)
    if (RUN/'protocol.json').exists():
        if read(RUN/'protocol.json')!=protocol:raise ValueError('Frozen protocol changed')
    else:
        write(RUN/'protocol.json',protocol)
        with (RUN/'configurations.jsonl').open('x',encoding='utf-8') as f:
            for c in rows:f.write(json.dumps(c,sort_keys=True)+'\n')
        code=RUN/'code';code.mkdir()
        for p in sources():shutil.copyfile(p,code/p.name)
        shutil.copytree(ROOT/'src/quant_futures',code/'quant_futures',ignore=shutil.ignore_patterns('__pycache__'))
        cache=RUN/'cache';cache.mkdir()
        for symbol in SYMBOLS:
            for ext in ('.parquet','.json'):
                source=common/'cache'/(symbol+'_15m'+ext);shutil.copyfile(source,cache/source.name)
    db=sqlite3.connect(RUN/'checkpoints.sqlite')
    db.execute('CREATE TABLE IF NOT EXISTS results(phase TEXT,id TEXT,payload TEXT,PRIMARY KEY(phase,id))')
    db.execute('CREATE TABLE IF NOT EXISTS ledgers(phase TEXT,id TEXT,fold TEXT,payload BLOB,PRIMARY KEY(phase,id,fold))')
    db.execute('CREATE TABLE IF NOT EXISTS attempts(id TEXT PRIMARY KEY,state TEXT)')
    db.commit();return rows,protocol,db


def load_train():
    frames={};metadata={}
    for symbol in SYMBOLS:frames[symbol],metadata[symbol]=engine.load_training(symbol,RUN)
    return frames,metadata


class SignalCache:
    def __init__(self,frames,training_frames,validation=False):
        self.frames=frames;self.validation=validation;self.p={};self.fitp={};self.models={};self.scores={}
        for s in SYMBOLS:
            peer=SYMBOLS[1-SYMBOLS.index(s)]
            self.p[s]=primitives(frames[s],frames[peer])
            self.fitp[s]=primitives(training_frames[s],training_frames[peer])

    def model(self,s,family,L,year):
        k=(s,family,L,year)
        if k not in self.models:
            cutoff=pd.Timestamp(f'{year}-01-01T00:00Z')-pd.Timedelta(days=8)
            self.models[k]=fit_model(self.fitp[s],family,L,cutoff)
        return self.models[k]

    def signal(self,c):
        s,family,L=c['instrument'],c['family'],c['lookback'];k=(s,family,L)
        if k not in self.scores:
            p=self.p[s]
            if family in FITTED:
                out=np.full(len(p['r']),np.nan)
                years=(2024,) if self.validation else range(2020,2024)
                ts=frames_years(self.frames[s])
                for year in years:
                    m=self.model(s,family,L,year)
                    v=value(p,family,L,m)
                    mask=(ts>=2024) if self.validation else (ts==year)
                    out[mask]=v[mask]
            else:out=value(p,family,L)
            self.scores[k]=out
        v=self.scores[k];minute=self.p[s]['clock']+15
        weekday=self.frames[s].timestamp_utc.dt.tz_convert('America/New_York').dt.weekday.to_numpy()
        valid=np.isfinite(v)&(np.abs(v)>=c['threshold'])&(minute>=c['session_start'])&(minute<c['session_end'])&(weekday<5)
        return np.where(valid,np.sign(v),0).astype(np.int8)


def frames_years(b):return b.timestamp_utc.dt.year.to_numpy()


def summarize(c,metrics,signal):
    r=engine.aggregate(c,metrics,signal)
    r['evaluation_phase_qualified']=r['qualified']
    r['qualified']=bool(all(m['net_pnl']>0 and m['trades']>=30 and not m['killed'] and not m['funded_failed'] for m in metrics)
        and all(r[k]<2000 for k in DD) and r['trades']<=800 and (r['profit_factor'] or 0)>=1.3)
    r['profit_dd_pass']=bool(r['net_pnl']>0 and all(r[k]<2000 for k in DD))
    return r


def execute(c,bars,features,data,folds,signal,db,phase,factor=1,save=False):
    metrics=[];art=RUN/'selected_artifacts';art.mkdir(exist_ok=True)
    for fold in folds:
        left,right=fold['start'],fold['stop'];d={k:v[left:right] for k,v in data.items()}
        sig=signal[left:right].copy();sig[:96]=0;sig[-16:]=0
        raw=engine.execute(d,sig,features['atr'][left:right],engine.execution_cfg(c,factor))
        d['regime']=engine.entry_regimes(features['trend'])[left:right]
        m=engine.summarize_execution(raw,d);m['label']=fold['label'];m.pop('daily_pnl')
        # Metrics independently reconcile the entire closed ledger and account.
        if db is not None:db.execute('INSERT INTO ledgers VALUES(?,?,?,?)',(phase,c['config_id'],fold['label'],pack(raw)))
        if save:
            name=c['config_id']+'_'+phase+'_'+fold['label']
            np.savez_compressed(art/(name+'.npz'),**raw)
            pd.DataFrame(dict(timestamp_utc=pd.to_datetime(d['timestamp'],utc=True),equity=raw['equity'],cash=raw['cash'],intrabar_worst_bound=raw['worst'])).to_parquet(art/(name+'_equity.parquet'),index=False)
            pd.DataFrame(dict(entry_time=pd.to_datetime(d['timestamp'][raw['trade_entry']],utc=True),exit_time=pd.to_datetime(d['timestamp'][raw['trade_exit']],utc=True),side=raw['trade_side'],quantity=raw['trade_qty'],entry_price=raw['trade_entryprice'],exit_price=raw['trade_exitprice'],net_pnl=raw['trade_net'],fees=raw['trade_fees'],reason=raw['trade_reason'])).to_csv(art/(name+'_trades.csv'),index=False)
            if factor==1:m['execution_verification']=engine.verify_execution(bars.iloc[left:right].reset_index(drop=True),d,sig,features['atr'][left:right],c,engine.execution_cfg(c),raw)
        metrics.append(m)
    return summarize(c,metrics,signal)


def rank(r):return (-int(r['qualified']),-r['net_pnl'],r['intrabar_drawdown'],r['config_id'])
def all_results(db,phase):return [json.loads(r[0]) for r in db.execute('SELECT payload FROM results WHERE phase=?',(phase,))]
def csv_results(path,rows):
    fields=['rank','config_id','instrument','family','qualified','profit_dd_pass','net_pnl','intrabar_drawdown','max_drawdown','realized_drawdown','profit_factor','trades','positive_folds','locks','funded_breaches','maximum_consistency_ratio','training_qualified','parameters','fold_metrics']
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader()
        for i,r in enumerate(rows,1):w.writerow({k:json.dumps(v,sort_keys=True) if isinstance(v,(dict,list)) else v for k,v in dict(r,rank=i).items() if k in fields})


def progress(db,phase):
    counts=dict(db.execute('SELECT phase,COUNT(*) FROM results GROUP BY phase'))
    out=dict(phase=phase,target=2000,counts=counts,test_accessed=False,updated_at=engine.now())
    write(ROOT/'reports/NOVEL_FUTURES_2K_progress.json',out);print(json.dumps(out),flush=True)


def train(rows,db,frames,cache):
    done={r[0] for r in db.execute("SELECT id FROM results WHERE phase='TRAIN'")}
    arrays={s:engine.arrays(frames[s]) for s in SYMBOLS};feats={s:engine.features(frames[s],32) for s in SYMBOLS}
    for c in rows:
        if c['config_id'] in done:continue
        s=c['instrument'];r=execute(c,frames[s],feats[s],arrays[s],folds_for(frames[s]),cache.signal(c),db,'TRAIN')
        db.execute('INSERT INTO results VALUES(?,?,?)',('TRAIN',c['config_id'],json.dumps(r)))
        if (c['experiment_order']+1)%50==0:db.commit();progress(db,'TRAIN')
    db.commit();ranked=sorted(all_results(db,'TRAIN'),key=rank)
    assert len(ranked)==2000
    csv_results(RUN/'training_ranked.csv',ranked)
    # Freeze every fitted V model using TRAIN only, before any V prices loaded.
    for c in rows:
        if c['family'] in FITTED:cache.model(c['instrument'],c['family'],c['lookback'],2024)
    models={'|'.join(map(str,k)):v for k,v in cache.models.items()}
    if not (RUN/'frozen_models.json').exists():write(RUN/'frozen_models.json',models)
    elif read(RUN/'frozen_models.json')!=models:raise ValueError('Frozen models changed')
    write(RUN/'training_complete.json',dict(completed=2000,training_csv_sha256=file_hash(RUN/'training_ranked.csv'),models_sha256=file_hash(RUN/'frozen_models.json'),test_accessed=False))
    # Top5 frozen training choices, not adjusted using validation.
    if not (RUN/'training_stress.json').exists():
        checks=[]
        for r in ranked[:5]:
            c=r['parameters'];s=c['instrument'];sig=cache.signal(c)
            base=execute(c,frames[s],feats[s],arrays[s],folds_for(frames[s]),sig,None,'TRAIN_selected',save=True)
            if base['net_pnl']!=r['net_pnl'] or base['intrabar_drawdown']!=r['intrabar_drawdown']:raise ValueError('TRAIN replay disagrees')
            stress=execute(c,frames[s],feats[s],arrays[s],folds_for(frames[s]),sig,None,'TRAIN_cost2',factor=2,save=True)
            checks.append(dict(config_id=c['config_id'],base=base,stress=stress))
        write(RUN/'training_stress.json',checks)
    return ranked


def load_validation():
    """Resolve only validation roles; never resolve or load TEST."""
    import duckdb
    tree=ast.parse(Path(engine.__file__).read_text())
    query=[n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value.startswith('SELECT time_bucket')][0]
    frames={};identities={}
    for symbol in SYMBOLS:
        path=resolve_dataset(symbol+':validation');meta=read(path.with_suffix('.manifest.json'))
        if meta['split_role']!='validation' or not meta['raw_contract_prices'] or meta['synthetic']:raise ValueError('Invalid V source')
        if file_hash(path)!=meta['dataset_version']:raise ValueError('V source changed')
        db=duckdb.connect()
        try:
            db.execute('SET threads=1');db.execute("SET memory_limit='256MB'")
            b=canonical(db.execute(query,[str(path)]).fetch_df())
        finally:db.close()
        _,qa=audit_bars(b,minutes=15)
        if qa['fatal'] or not b.instrument.eq(symbol).all() or not b.timestamp_utc.ge(pd.Timestamp('2024-01-01T00:00Z')).all() or not b.timestamp_utc.lt(pd.Timestamp('2026-01-01T00:00Z')).all():raise ValueError('V data audit failed')
        b.to_parquet(RUN/'cache'/(symbol+'_validation_15m.parquet'),index=False)
        frames[symbol]=b;identities[symbol]=meta
    write(RUN/'validation_data_identity.json',identities);return frames


def validation(rows,db,training_frames,trained):
    if (RUN/'validation_complete.json').exists():return sorted(all_results(db,'VALIDATION'),key=rank)
    if db.execute("SELECT COUNT(*) FROM attempts WHERE state='running'").fetchone()[0]:raise RuntimeError('Interrupted V attempts consumed; no automatic replay')
    if not (RUN/'validation_reservation.json').exists():
        reservation=dict(run=str(RUN),configurations_sha256=file_hash(RUN/'configurations.jsonl'),training_seal_sha256=file_hash(RUN/'training_complete.json'),models_sha256=file_hash(RUN/'frozen_models.json'),reserved_at=engine.now(),target=2000,test_accessed=False)
        global_path=ROOT/'data/manifests/validation_once'/('novel_2k_'+digest(reservation)+'.json')
        global_path.parent.mkdir(parents=True,exist_ok=True)
        with global_path.open('x',encoding='utf-8') as f:json.dump(reservation,f,indent=2)
        write(RUN/'validation_reservation.json',dict(reservation,global_reservation=str(global_path)))
        db.executemany('INSERT INTO attempts VALUES(?,?)',[(c['config_id'],'reserved') for c in rows]);db.commit()
    reserved=read(RUN/'validation_reservation.json')
    if reserved['models_sha256']!=file_hash(RUN/'frozen_models.json') or reserved['training_seal_sha256']!=file_hash(RUN/'training_complete.json'):raise ValueError('V freeze changed')
    frames=load_validation();cache=SignalCache(frames,training_frames,validation=True)
    frozen=read(RUN/'frozen_models.json');cache.models={tuple([s,f,int(L),int(y)]):m for k,m in frozen.items() for s,f,L,y in [k.split('|')]}
    arrays={s:engine.arrays(frames[s]) for s in SYMBOLS};feats={s:engine.features(frames[s],32) for s in SYMBOLS}
    trainmap={r['config_id']:r for r in trained};top=[];both=[]
    # On resume build running leaders from completed metrics; their curves were captured at execution.
    for r in all_results(db,'VALIDATION'):
        top.append(r)
        if r['training_qualified'] and r['qualified']:both.append(r)
    top=sorted(top,key=rank)[:5];both=sorted(both,key=rank)[:5]
    done={r[0] for r in db.execute("SELECT id FROM attempts WHERE state='done'")}
    for c in rows:
        if c['config_id'] in done:continue
        db.execute("UPDATE attempts SET state='running' WHERE id=?",(c['config_id'],));db.commit()
        s=c['instrument'];b=frames[s];d=arrays[s];sig=cache.signal(c);sig[:96]=0;sig[-16:]=0
        raw=engine.execute(d,sig,feats[s]['atr'],engine.execution_cfg(c))
        enriched=dict(d,regime=engine.entry_regimes(feats[s]['trend']))
        m=engine.summarize_execution(raw,enriched);m['label']='validation';m.pop('daily_pnl')
        r=summarize(c,[m],sig)
        r['qualified']=bool(r['profit_dd_pass'] and r['trades']>=30 and r['locks']==0 and r['funded_breaches']==0)
        r['training_qualified']=trainmap[c['config_id']]['qualified']
        r['evaluation_phase_qualified']=bool(r['qualified'] and m['consistency_50_pass'])
        db.execute('INSERT INTO results VALUES(?,?,?)',('VALIDATION',c['config_id'],json.dumps(r)))
        db.execute('INSERT INTO ledgers VALUES(?,?,?,?)',('VALIDATION',c['config_id'],'validation',pack(raw)))
        # Capture candidates while running; no V backtest replay to obtain curves.
        take=False
        for leaders,eligible in ((top,True),(both,r['training_qualified'] and r['qualified'])):
            if eligible and (len(leaders)<5 or rank(r)<rank(leaders[-1])):
                leaders.append(r);leaders.sort(key=rank);del leaders[5:];take=True
        if take:
            art=RUN/'validation_snapshots';art.mkdir(exist_ok=True)
            np.savez_compressed(art/(c['config_id']+'.npz'),**raw)
        db.execute("UPDATE attempts SET state='done' WHERE id=?",(c['config_id'],));db.commit()
        if (c['experiment_order']+1)%50==0:progress(db,'VALIDATION; model selection,not independent confirmation')
    ranked=sorted(all_results(db,'VALIDATION'),key=rank)
    assert len(ranked)==2000 and db.execute("SELECT COUNT(*) FROM attempts WHERE state='done'").fetchone()[0]==2000
    csv_results(RUN/'validation_ranked.csv',ranked)
    write(RUN/'validation_complete.json',dict(completed=2000,ranked_sha256=file_hash(RUN/'validation_ranked.csv'),test_accessed=False))
    return ranked


def publish(trained,validated,protocol,db):
    both=[r for r in validated if r['qualified'] and r['training_qualified']]
    counts=dict(evaluated=2000,train_positive_dd=sum(r['profit_dd_pass'] for r in trained),train_qualified=sum(r['qualified'] for r in trained),validation_positive_dd=sum(r['profit_dd_pass'] for r in validated),validation_qualified=sum(r['qualified'] for r in validated),both_qualified=len(both))
    family=[]
    for f in FAMILIES:
        tr=[r for r in trained if r['family']==f];vr=[r for r in validated if r['family']==f]
        family.append(dict(family=f,configurations=len(tr),train_positive_dd=sum(r['profit_dd_pass'] for r in tr),train_qualified=sum(r['qualified'] for r in tr),validation_positive_dd=sum(r['profit_dd_pass'] for r in vr),validation_qualified=sum(r['qualified'] for r in vr),both=sum(r['qualified'] and r['training_qualified'] for r in vr)))
    chosen=both[0] if both else None
    result=dict(counts=counts,by_family=family,best_both=chosen,top5_both=both[:5],top5_training=trained[:5],top5_validation=validated[:5],test_accessed=False,classification='VALIDATION_SELECTED_RESEARCH_ONLY' if chosen else 'NO_BOTH_QUALIFIED_MODEL',independent_confirmation=False)
    write(ROOT/'reports/NOVEL_FUTURES_2K.json',result)
    if chosen and not (RUN/'frozen_selected_candidate.json').exists():write(RUN/'frozen_selected_candidate.json',dict(result=chosen,protocol_sha256=file_hash(RUN/'protocol.json'),models_sha256=file_hash(RUN/'frozen_models.json'),classification=result['classification'],test_accessed=False))
    # Audit all compressed ledgers independently of metric summarization.
    trade_count=0;config_map={c['config_id']:c for c in universe()}
    for phase,cid,fold,blob in db.execute('SELECT phase,id,fold,payload FROM ledgers'):
        z=np.load(io.BytesIO(blob));c=config_map[cid]
        expected=z['trade_side']*z['trade_qty']*(z['trade_exitprice']-z['trade_entryprice'])*engine.SPECS[c['instrument']].multiplier-z['trade_fees']
        np.testing.assert_allclose(expected,z['trade_net'],atol=1e-7,rtol=0);trade_count+=len(expected)
    verification=dict(passed=True,training=2000,validation=2000,unique_active_configs=2000,ledgers=db.execute('SELECT COUNT(*) FROM ledgers').fetchone()[0],trades_audited=trade_count,source_hashes_unchanged=all(file_hash(p)==protocol['source_hashes'][p.name] for p in sources()),test_accessed=False)
    assert verification['source_hashes_unchanged']
    write(ROOT/'reports/NOVEL_FUTURES_2K_verification.json',verification)
    lines=['# 2,000 new futures configurations','',f"Completed all2,000 TRAIN and2,000 frozen VALIDATION evaluations. TEST was not accessed.",'','Eight statistical mechanisms differ from the previous ten-family indicator/momentum library. These are correlated configurations, not2,000 independent discoveries.','',f"Counts: {json.dumps(counts)}",'', 'TRAIN=2020-2023, four reset annual accounts. VALIDATION=2024-2025, one continuous account. Fitted forecasting coefficients never learn from evaluated years or validation. Prior validation is consumed and used here for model selection; this is not unseen confirmation.','', '## Mechanisms and results','', '| Family | Trials | TRAIN profit/DD | TRAIN qualified | VAL profit/DD | VAL qualified | Both |','|---|---:|---:|---:|---:|---:|---:|']
    for r in family:lines.append(f"| {r['family']} | {r['configurations']} | {r['train_positive_dd']} | {r['train_qualified']} | {r['validation_positive_dd']} | {r['validation_qualified']} | {r['both']} |")
    for title,rows in [('Top5 passing both, ranked on validation',both[:5]),('Top5 validation only; TRAIN flags matter',validated[:5]),('Top5 training',trained[:5])]:
        lines+=['','## '+title,'','| ID | Market / mechanism | Net P&L | Intrabar DD | Trades | TRAIN qualified |','|---|---|---:|---:|---:|---|']
        for r in rows:lines.append(f"| {r['config_id']} | {r['instrument']} / {r['family']} | ${r['net_pnl']:,.2f} | ${r['intrabar_drawdown']:,.2f} | {r['trades']} | {r.get('training_qualified',r['qualified'])} |")
    lines+=['','## Limitations','', 'The unchanged15m engine uses next-open execution, actual contract economics, fees, spread, slippage, conservative OHLC handling, volume participation and risk locks. Intrabar DD is an OHLC adverse bound, not observed tick-order equity. Funded rules are provisional scenarios, not verified account certification.50%consistency remains evaluation-account-phase-only. Annual reset profits/DD are not a continuous four-year account path. TRAIN top5 have independent fill samples and2x cost diagnostics in training_stress.json; all-case ledgers reconcile. No strategy is promoted, deployed, or claimed independently profitable.','', '## Entry hypotheses','']
    lines += [f'- **{f}**: {thesis}' for f,thesis in FAMILIES.items()]
    (ROOT/'reports/NOVEL_FUTURES_2K.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    try:
        import matplotlib;matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        selected=both[:5] or validated[:5]
        fig,axes=plt.subplots(2,1,figsize=(13,8),sharex=True)
        for i,r in enumerate(selected,1):
            z=np.load(RUN/'validation_snapshots'/(r['config_id']+'.npz'))
            bars=pd.read_parquet(RUN/'cache'/(r['instrument']+'_validation_15m.parquet'))
            t=bars.timestamp_utc
            axes[0].plot(t,z['equity']-50000,label=f"{i} {r['instrument']} {r['family']}",lw=1)
            peak=np.maximum.accumulate(np.r_[50000,z['equity']])[1:]
            axes[1].plot(t,z['worst']-peak,lw=1)
        axes[1].axhline(-2000,color='red',ls='--');axes[0].legend(fontsize=8)
        axes[0].set(ylabel='Net equity ($)',title='Frozen validation selection: '+('top passing both' if both else 'no both-qualified candidates; validation-only display'))
        axes[1].set(ylabel='Intrabar DD bound ($)')
        for ax in axes:ax.grid(alpha=.2)
        fig.tight_layout();fig.savefig(ROOT/'reports/NOVEL_FUTURES_2K.png',dpi=150);plt.close(fig)
    except ImportError:pass
    progress(db,'COMPLETE');print(json.dumps(dict(counts=counts,best_both=None if not chosen else {k:chosen[k] for k in ('config_id','instrument','family','net_pnl','intrabar_drawdown','trades')})),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--train-only',action='store_true');args=parser.parse_args()
    rows,protocol,db=setup()
    try:
        frames,metadata=load_train();write(RUN/'training_data_identity.json',metadata)
        cache=SignalCache(frames,frames)
        trained=train(rows,db,frames,cache)
        if not args.train_only:
            validated=validation(rows,db,frames,trained);publish(trained,validated,protocol,db)
    finally:db.close()


if __name__=='__main__':main()

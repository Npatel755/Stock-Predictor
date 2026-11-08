"""Checkpointed Portfolio B challengers: TRAIN only, no holdout loader/stage.

Combines actual cash/equity and adverse OHLC bounds on a common event clock.
Accepts only paths where joint controls never bind; it never pretends to apply
a risk overlay by clipping a precomputed return series. Unquoted open exposure
is rejected. No confirmation outside TRAIN is claimed.
"""
import os
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[_key]='1'
import argparse
import hashlib
import html
import json
from pathlib import Path
import random
import shutil
import sqlite3
import numpy as np
import pandas as pd
import mass_research as e
from training_5m_policy import execution_cfg_5m
from quant_futures.config import file_hash,digest

ROOT=e.ROOT
RUN=ROOT/'runs/portfolio_b_train_refinement_v1'
ARCHIVE=ROOT/'strategy_versions/portfolio_b/v1.0.0'
PARENT=ROOT/'runs/saved_portfolio_B_mes_mom_mnq_brk'
JOINT=dict(initial_balance=50000.,drawdown=2000.,daily_loss=1600.,max_contracts=6,max_initial_stop_risk=900.,funded_cap=50100.)
SEED=20261120


def read(p):return e.read(p)
def write(p,x):e.json_write(p,x)
ACTIVE=('instrument','family','lookback','threshold','stop_atr','target_r','hold_bars','session_start','session_end','max_contracts','trailing_atr')
def fingerprint(c):return digest({k:c[k] for k in ACTIVE})
def portfolio_id(legs):return 'pb_'+digest([fingerprint(c) for c in legs])[:20]


def source_files():
    return [Path(__file__),Path(__file__).with_name('training_5m_policy.py'),*e.sources()]


def setup():
    parent=read(PARENT/'portfolio_config.json');legs=[parent['leg1_config'],parent['leg2_config']]
    assert legs[0]['instrument']=='MES' and legs[1]['instrument']=='MNQ'
    legs=[dict(legs[0],max_contracts=3),dict(legs[1],max_contracts=1)]
    hashes={p.name:file_hash(p) for p in source_files()}
    archive=dict(name='Portfolio B',version='v1.0.0',user_designated_champion=True,legs=legs,
      source_parameters=str(PARENT/'portfolio_config.json'),source_parameters_sha256=file_hash(PARENT/'portfolio_config.json'),
      source_training_csv_sha256=file_hash(PARENT/'equity_train_2020_2023.csv'),source_hashes=hashes,
      provenance='User selected after observed historical outcomes; no fresh holdout claim. Screenshot values are not research objectives. Only TRAIN is used for challenger selection.',
      actual_bars='15minute bars despite5m/2m strategy names',actual_saved_train_window='2019-05-05 through2023-12-29,despite2020-2023 filename',
      execution_configs=[execution_cfg_5m(c) for c in legs],no_new_validation_or_test_evaluation=True)
    if not ARCHIVE.exists():
        ARCHIVE.mkdir(parents=True);write(ARCHIVE/'baseline.json',archive)
        shutil.copyfile(PARENT/'portfolio_config.json',ARCHIVE/'portfolio_config.json')
        shutil.copyfile(PARENT/'equity_train_2020_2023.csv',ARCHIVE/'source_training_equity.csv')
        code=ARCHIVE/'code';code.mkdir()
        for p in source_files():shutil.copyfile(p,code/p.name)
        shutil.copytree(ROOT/'src/quant_futures',code/'quant_futures',ignore=shutil.ignore_patterns('__pycache__'))
    elif read(ARCHIVE/'baseline.json')!=archive:raise ValueError('Immutable baseline identity changed')
    protocol=dict(seed=SEED,baseline=archive,source_hashes=hashes,shared_scenario=JOINT,
      allowed_data='Physical TRAIN only; every observation timestamp strictly before2024-01-01. No validation/test prices,rankings,or outcome files may supply selection data.',
      periods='Exact saved continuous2019May-2023TRAIN;four reset2020/21/22/23 internal forward folds with96bar entry embargo and40bar terminal entry purge. Indicators use causal earlierTRAIN warmup.',
      improvement='Higher continuous TRAIN net than reproduced champion;cash/closing/intrabarDD strictly<2000;no sleeve locks/funded failure;no missing quoted open exposure;no joint daily/contract/initialrisk/floor breach. Annual folds positive,>=30combinedtrades each,aggregatePF>=1.30. Both base and2xcost paths must pass risk/stability;2xcostcontinuousnet must also beat champion2xcostnet. All selection is TRAIN-only.',
      search='First sizing grid MES1..5/MNQ1..3,total<=6,ordered distance from champion. Then seeded new one-leg changes,alternating MES/MNQ;families momentum/breakout fixed. Continue until verified improvement;checkpoint every result.',
      domains=dict(lookbacks=[8,12,16,20,24,32,40,48,64],thresholds=[.25,.5,.75,1.,1.25,1.5,1.75,2.],stops=[.75,1.,1.25,1.5,1.75,2.,2.5],targets=[1.5,2.,2.5,3.,4.,5.,6.],holds=[4,8,12,16,24,32,40],trails=[0.,.5,1.,1.5,2.,2.5,3.],sessions=[[585,690],[600,720],[720,870],[840,945],[585,945]]),
      economic_assumptions='Original fee/tick/slippage/participation/risk-per-contract rules unchanged. Joint scenario is configurable research assumption,not verified account rules. Summing sleeve adverse bounds is conservative;actual intrabar order unknown.',
      validation_accessed=False,test_accessed=False,automatic_holdout_stage=False,classification='TRAIN_ONLY_RESEARCH',no_live_execution=True)
    RUN.mkdir(parents=True,exist_ok=True)
    if (RUN/'protocol.json').exists():
        if read(RUN/'protocol.json')!=protocol:raise ValueError('Frozen research protocol changed')
    else:
        write(RUN/'protocol.json',protocol);code=RUN/'code';code.mkdir()
        for p in source_files():shutil.copyfile(p,code/p.name)
        shutil.copytree(ROOT/'src/quant_futures',code/'quant_futures',ignore=shutil.ignore_patterns('__pycache__'))
    db=sqlite3.connect(RUN/'checkpoints.sqlite')
    db.execute('CREATE TABLE IF NOT EXISTS candidates(id TEXT PRIMARY KEY, sequence INTEGER,config TEXT,result TEXT)');db.commit()
    return legs,protocol,db


def periods(bars):
    out={'continuous':(0,len(bars))}
    for year in range(2020,2024):
        ids=np.flatnonzero((bars.timestamp_utc>=pd.Timestamp(f'{year}-01-01T00:00Z'))&(bars.timestamp_utc<pd.Timestamp(f'{year+1}-01-01T00:00Z')))
        if len(ids)<200:raise ValueError('Missing TRAIN fold')
        out[str(year)]=(int(ids[0]),int(ids[-1])+1)
    return out


def align(ts1,ts2):
    clock=np.union1d(ts1,ts2);out=[]
    for ts in (ts1,ts2):
        idx=np.searchsorted(ts,clock,side='right')-1;ready=idx>=0;safe=np.maximum(idx,0)
        actual=ready&(ts[safe]==clock);out.append((idx,ready,actual))
    dates=(pd.to_datetime(clock,utc=True).tz_convert('America/New_York').tz_localize(None)+pd.Timedelta(hours=6)).normalize()
    session=pd.factorize(dates,sort=False)[0]
    return clock,out,session


def combine(raws,datas,cfgs,layout=None,paths=False):
    clock,indices,session=layout or align(datas[0]['timestamp'],datas[1]['timestamp'])
    n=len(clock);cash=np.full(n,50000.);equity=cash.copy();worst=cash.copy();qty=np.zeros(n);initial_risk=np.zeros(n);missing=0
    for raw,data,cfg,(idx,ready,actual) in zip(raws,datas,cfgs,indices):
        safe=np.maximum(idx,0)
        cash+=np.where(ready,raw['cash'][safe]-50000.,0.)
        equity+=np.where(ready,raw['equity'][safe]-50000.,0.)
        # Carry last CLOSE mark on an absent bar, never a stale adverse extreme.
        worst+=np.where(ready,np.where(actual,raw['worst'][safe],raw['equity'][safe])-50000.,0.)
        missing+=int(np.count_nonzero(ready&~actual&(raw['quantity'][safe]!=0)))
        # Include intrabar entries/exits, including trades that close within a bar.
        delta=np.zeros(len(data['timestamp'])+1)
        np.add.at(delta,raw['trade_entry'],raw['trade_qty']);np.add.at(delta,raw['trade_exit']+1,-raw['trade_qty'])
        active=np.cumsum(delta[:-1]);q=np.where(ready,active[safe],0.)
        qty+=q
        # Conservative allocation upper bound per active sleeve, including its
        # entry/exit cost reserve. Gap risk is assessed by the actual worst path.
        initial_risk+=np.where(q>0,cfg['max_open_risk'],0.)
    pe=np.maximum.accumulate(np.r_[50000.,equity])[1:];pc=np.maximum.accumulate(np.r_[50000.,cash])[1:]
    ends=np.r_[np.flatnonzero(np.diff(session)!=0),n-1];starts=np.r_[0,ends[:-1]+1]
    day_start=np.repeat(np.r_[50000.,cash[ends[:-1]]],ends-starts+1)
    daily=np.diff(np.r_[50000.,equity[ends]])
    eod_prior=np.repeat(np.r_[50000.,cash[ends[:-1]]],ends-starts+1)
    floor=np.maximum(48000.,np.minimum(np.maximum.accumulate(eod_prior)-2000.,JOINT['funded_cap']))
    net=float(cash[-1]-50000.)
    trade_net=np.concatenate([r['trade_net'] for r in raws]);wins=trade_net[trade_net>0].sum();loss=-trade_net[trade_net<0].sum()
    result=dict(net_pnl=net,cash_drawdown=float(np.max(pc-cash)),closing_drawdown=float(np.max(pe-equity)),intrabar_drawdown=float(np.max(pe-worst)),
      maximum_daily_loss_bound=float(np.max(day_start-worst)),maximum_simultaneous_contracts=int(np.max(qty)),maximum_allocated_initial_risk=float(np.max(initial_risk)),
      missing_quote_exposure=missing,joint_floor_breaches=int(np.count_nonzero(worst<=floor+1e-8)),sleeve_locks=sum(int(r['lock']!=0) for r in raws),
      sleeve_funded_breaches=sum(int(r['funded_failed']) for r in raws),trades=len(trade_net),profit_factor=float(wins/loss) if loss else None,
      consistency=float(max(0.,daily.max())/net) if net>0 else None,positive_sessions=int(np.count_nonzero(daily>0)),total_sessions=len(daily))
    result['risk_pass']=bool(all(result[k]<2000 for k in ('cash_drawdown','closing_drawdown','intrabar_drawdown'))
      and result['maximum_daily_loss_bound']<JOINT['daily_loss'] and result['maximum_simultaneous_contracts']<=JOINT['max_contracts']
      and result['maximum_allocated_initial_risk']<=JOINT['max_initial_stop_risk'] and result['missing_quote_exposure']==result['joint_floor_breaches']==result['sleeve_locks']==result['sleeve_funded_breaches']==0)
    # Reconcile all fees/entries, not only the combined terminal cash.
    np.testing.assert_allclose(net,trade_net.sum(),atol=1e-7,rtol=0)
    if paths:return result,pd.DataFrame(dict(timestamp_utc=pd.to_datetime(clock,utc=True),cash=cash,equity=equity,worst_bound=worst,funded_floor=floor,contracts=qty,allocated_initial_risk=initial_risk))
    return result


class Research:
    def __init__(self):
        self.bars={};self.data={};self.period={};self.feature={};self.signals={};self.rawcache={};self.layouts={};meta={}
        for s in ('MES','MNQ'):
            b,m=e.load_training(s,ROOT/'runs/mass_training_v2')
            if not b.timestamp_utc.lt(pd.Timestamp('2024-01-01T00:00Z')).all():raise PermissionError('TRAIN boundary crossed')
            self.bars[s]=b;self.period[s]=periods(b);self.data[s]=e.arrays(b);meta[s]=m
        write(RUN/'training_data_identity.json',meta)
        for name in ('continuous','2020','2021','2022','2023'):
            self.layouts[name]=align(*[self.data[s]['timestamp'][slice(*self.period[s][name])] for s in ('MES','MNQ')])

    def inputs(self,c,name):
        s=c['instrument'];k=(s,c['lookback'])
        if k not in self.feature:self.feature[k]=e.features(self.bars[s],c['lookback'])
        f=self.feature[k];signal_key=(s,c['family'],c['lookback'],c['threshold'],c['session_start'],c['session_end'])
        if signal_key not in self.signals:self.signals[signal_key]=e.masked_signal(self.bars[s],c,f)
        a,b=self.period[s][name];data={k:v[a:b] for k,v in self.data[s].items()};sig=self.signals[signal_key][a:b].copy()
        if name!='continuous':sig[:96]=0;sig[-40:]=0
        return data,sig,f['atr'][a:b]

    def execute(self,c,name,factor=1,retain=True):
        k=(fingerprint(c),name,factor)
        if k in self.rawcache:return self.rawcache[k]
        d,sig,atr=self.inputs(c,name);raw=e.execute(d,sig,atr,execution_cfg_5m(c,factor))
        # Every execution reconciles independent cash/trade metrics.
        e.summarize_execution(raw,d)
        if retain:self.rawcache[k]=raw
        return raw

    def pair(self,legs,name,factor=1,paths=False,retain=True):
        raw=[self.execute(c,name,factor,retain) for c in legs]
        data=[self.inputs(c,name)[0] for c in legs]
        return combine(raw,data,[execution_cfg_5m(c,factor) for c in legs],self.layouts[name],paths)

    def full(self,legs,factor=1,retain=False):
        result={name:self.pair(legs,name,factor,retain=retain) for name in ('continuous','2020','2021','2022','2023')}
        result['qualified']=bool(result['continuous']['risk_pass'] and result['continuous']['net_pnl']>0
            and all(result[str(y)]['risk_pass'] and result[str(y)]['net_pnl']>0 and result[str(y)]['trades']>=30 for y in range(2020,2024))
            and (result['continuous']['profit_factor'] or 0)>=1.3)
        return result


def generate(parent):
    seen={portfolio_id(parent)};sequence=0
    sizes=sorted([(m,n) for m in range(1,6) for n in range(1,4) if m+n<=6 and (m,n)!=(3,1)],key=lambda x:(abs(x[0]-3)+abs(x[1]-1),x))
    for m,n in sizes:
        legs=[dict(parent[0],max_contracts=m),dict(parent[1],max_contracts=n)]
        for old,c in zip(parent,legs):
            if fingerprint(old)!=fingerprint(c):
                c['parent_config_id']=old.get('config_id');c['config_id']='leg_'+fingerprint(c)[:20]
        cid=portfolio_id(legs);seen.add(cid)
        yield sequence,cid,legs,'sizing';sequence+=1
    rng=random.Random(SEED)
    while True:
        legs=[dict(c) for c in parent];which=sequence%2;c=legs[which]
        start,end=rng.choice(((585,690),(600,720),(720,870),(840,945),(585,945)))
        c.update(lookback=rng.choice((8,12,16,20,24,32,40,48,64)),threshold=rng.choice((.25,.5,.75,1.,1.25,1.5,1.75,2.)),
          stop_atr=rng.choice((.75,1.,1.25,1.5,1.75,2.,2.5)),target_r=rng.choice((1.5,2.,2.5,3.,4.,5.,6.)),
          hold_bars=rng.choice((4,8,12,16,24,32,40)),trailing_atr=rng.choice((0.,.5,1.,1.5,2.,2.5,3.)),session_start=start,session_end=end)
        c['parent_config_id']=parent[which].get('config_id');c['config_id']='leg_'+fingerprint(c)[:20];cid=portfolio_id(legs)
        if cid in seen:continue
        seen.add(cid);yield sequence,cid,legs,'one_leg_train_refinement';sequence+=1


def save_case(cid,legs,research,base,stress):
    out=RUN/'selected'/cid;out.mkdir(parents=True,exist_ok=True);checks=[]
    for factor,label in ((1,'base'),(2,'cost2')):
        for name in ('continuous','2020','2021','2022','2023'):
            metrics,curve=research.pair(legs,name,factor,paths=True,retain=False)
            reference=(base if factor==1 else stress)[name]
            if metrics!=reference:raise ValueError('Selected account-path reproduction failed')
            curve.to_parquet(out/(label+'_'+name+'_equity.parquet'),index=False)
            for c in legs:
                s=c['instrument'];raw=research.execute(c,name,factor,retain=False);data,sig,atr=research.inputs(c,name)
                np.savez_compressed(out/(label+'_'+name+'_'+s+'.npz'),**{k:v for k,v in raw.items() if k!='lock_reason'})
                trades=pd.DataFrame(dict(entry_time=pd.to_datetime(data['timestamp'][raw['trade_entry']],utc=True),exit_time=pd.to_datetime(data['timestamp'][raw['trade_exit']],utc=True),side=raw['trade_side'],quantity=raw['trade_qty'],entry_price=raw['trade_entryprice'],exit_price=raw['trade_exitprice'],net_pnl=raw['trade_net'],fees=raw['trade_fees'],reason=raw['trade_reason']))
                trades.to_csv(out/(label+'_'+name+'_'+s+'_trades.csv'),index=False)
                if factor==1:
                    a,b=research.period[s][name]
                    check=e.verify_execution(research.bars[s].iloc[a:b].reset_index(drop=True),data,sig,atr,c,execution_cfg_5m(c),raw)
                    checks.append(dict(period=name,instrument=s,check=check))
    frozen=dict(candidate_id=cid,legs=legs,base=base,cost2=stress,source_hashes={p.name:file_hash(p) for p in source_files()},protocol_sha256=file_hash(RUN/'protocol.json'),checks=checks,
      classification='TRAIN_ONLY_CHALLENGER',validation_evaluated=False,test_evaluated=False,promoted_to_live=False)
    write(out/'frozen_candidate.json',frozen);return frozen


def publish(baseline,baseline_stress,chosen,trials):
    report=dict(baseline=baseline,baseline_cost2=baseline_stress,challenger=chosen,trials=trials,validation_accessed=False,test_accessed=False,
      conclusion='VERIFIED_TRAIN_ONLY_IMPROVEMENT',limitations='Parent was user-selected after prior holdout observations. New selection uses TRAIN only; this does not establish fresh unseen performance or verified account compliance.')
    write(ROOT/'reports/PORTFOLIO_B_TRAIN_REFINEMENT.json',report)
    version=ROOT/'strategy_versions/portfolio_b/v1.1.0-train-challenger'
    if not version.exists():
        version.mkdir(parents=True)
        write(version/'frozen_candidate.json',chosen)
        shutil.copyfile(RUN/'protocol.json',version/'protocol.json')
        shutil.copytree(RUN/'code',version/'code')
    rows=[]
    con=sqlite3.connect(RUN/'checkpoints.sqlite')
    for cid,sequence,config,payload in con.execute('SELECT id,sequence,config,result FROM candidates ORDER BY sequence'):
        if payload is None:continue
        r=json.loads(payload);m=r['continuous']
        rows.append(dict(candidate_id=cid,sequence=sequence,qualified=r['qualified'],stage=r['stage'],net_pnl=m['net_pnl'],intrabar_drawdown=m['intrabar_drawdown'],risk_pass=m['risk_pass'],parameters=config))
    con.close();pd.DataFrame(rows).to_csv(RUN/'all_training_trials.csv',index=False)
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    cid=chosen['candidate_id'];a=pd.read_parquet(RUN/'selected/baseline/base_continuous_equity.parquet');b=pd.read_parquet(RUN/'selected'/cid/'base_continuous_equity.parquet')
    fig,axes=plt.subplots(2,1,figsize=(13,8),sharex=True)
    for curve,label in ((a,'User baseline3MES+1MNQ'),(b,'TRAIN-only challenger')):
        axes[0].plot(curve.timestamp_utc,curve.equity-50000,label=label,lw=1)
        peak=np.maximum.accumulate(np.r_[50000.,curve.equity])[1:]
        axes[1].plot(curve.timestamp_utc,curve.worst_bound-peak,label=label,lw=1)
    axes[0].set(title='Portfolio B: matched TRAIN comparison only',ylabel='Net equity($)');axes[0].legend()
    axes[1].axhline(-2000,color='red',ls='--');axes[1].set(ylabel='Conservative intrabarDD($)')
    for ax in axes:ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(ROOT/'reports/PORTFOLIO_B_TRAIN_REFINEMENT.png',dpi=150);plt.close(fig)
    rows=[]
    for name in ('continuous','2020','2021','2022','2023'):
        for factor,left,right in (('Base',baseline,chosen['base']),('2x costs',baseline_stress,chosen['cost2'])):
            rows.append(dict(Period=name,Costs=factor,Baseline_net=left[name]['net_pnl'],Challenger_net=right[name]['net_pnl'],Baseline_DD=left[name]['intrabar_drawdown'],Challenger_DD=right[name]['intrabar_drawdown'],Challenger_risk_pass=right[name]['risk_pass']))
    table=pd.DataFrame(rows).to_html(index=False,border=0,float_format=lambda x:f'${x:,.2f}')
    text='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Portfolio B TRAIN improvement</title><style>body{font:16px/1.6 system-ui;max-width:1250px;padding:32px;margin:auto;background:#111820;color:#e8edf2}a{color:#92d6ff}table{border-collapse:collapse;font-size:14px}td,th{padding:10px;border-bottom:1px solid #465260;white-space:nowrap}img{width:100%}.scroll{overflow:auto}pre{white-space:pre-wrap}</style><h1>Portfolio B: verified TRAIN-only improvement</h1><p>Validation and test stayed closed. This is a research challenger, not unseen confirmation or live promotion.</p><p>The original portfolio is archived as portfolio_b/v1.0.0. Actual bars are15minutes. The saved TRAIN window startsMay2019 and endsDecember2023; file names previously described it as2020–2023. Four internal annual folds are evaluated separately with96/40 entry suppression.</p><div class="scroll">'+table+'</div><img src="PORTFOLIO_B_TRAIN_REFINEMENT.png" alt="TRAIN baseline and challenger equity/drawdown"><h2>Exact challenger legs</h2><pre>'+html.escape(json.dumps(chosen['legs'],indent=2))+'</pre><h2>Risk and evidence</h2><p>Combined cash and mark-to-market equity share a50k initial balance. Candidate paths must never trigger combined daily,drawdown,contract,initial stop-risk,or EOD-floor controls. Candidates are rejected if joint controls would bind; no clipped-return overlay is treated as executable. Missing quotes while holding exposure are rejected. Sleeve adverse bounds are summed conservatively; precise intrabar order is unknown. Scenario rules are provisional,not verified contractual terms.50%consistency is account-evaluation-only and remains a diagnostic. Parent selection after historical holdout observations is retained as an inherited limitation.</p><p><a href="../runs/portfolio_b_train_refinement_v1/protocol.json">Frozen protocol</a> · <a href="PORTFOLIO_B_TRAIN_REFINEMENT.json">Full metrics and checks</a> · <a href="../runs/portfolio_b_train_refinement_v1/selected/'+cid+'/frozen_candidate.json">Frozen challenger</a></p></html>'
    (ROOT/'reports/PORTFOLIO_B_TRAIN_REFINEMENT.html').write_text(text,encoding='utf-8')


def progress(count,phase):
    value=dict(completed=count,phase=phase,updated_at=e.now(),validation_accessed=False,test_accessed=False)
    write(ROOT/'reports/PORTFOLIO_B_TRAIN_REFINEMENT_progress.json',value);print(json.dumps(value),flush=True)


def main():
    parent,protocol,db=setup();research=Research()
    baseline=research.full(parent,retain=True);baseline_stress=research.full(parent,2,retain=True)
    stored=pd.read_csv(PARENT/'equity_train_2020_2023.csv',usecols=['pnl'])
    if abs(baseline['continuous']['net_pnl']-float(stored.pnl.iloc[-1]))>1e-7:raise ValueError('Original baseline does not reproduce')
    baseline_path=RUN/'baseline_training.json'
    if not baseline_path.exists():write(baseline_path,dict(base=baseline,cost2=baseline_stress))
    elif read(baseline_path)!=dict(base=baseline,cost2=baseline_stress):raise ValueError('Baseline TRAIN changed')
    print(json.dumps(dict(baseline_train=baseline['continuous'],baseline_cost2=baseline_stress['continuous'],annual_train_nets={year:baseline[year]['net_pnl'] for year in ('2020','2021','2022','2023')})),flush=True)
    if (RUN/'verified_improvement.json').exists():print('Verified TRAIN improvement already saved;no rerun or holdout access.');return
    # Baseline and its stress curve are preserved with the same independent audit.
    if not (RUN/'selected/baseline/frozen_candidate.json').exists():save_case('baseline',parent,research,baseline,baseline_stress)
    done={r[0] for r in db.execute('SELECT id FROM candidates')};count=db.execute('SELECT COUNT(*) FROM candidates WHERE result IS NOT NULL').fetchone()[0]
    for sequence,cid,legs,stage in generate(parent):
        if cid in done:continue
        # Persist the candidate before observing its execution result.
        db.execute('INSERT INTO candidates VALUES(?,?,?,NULL)',(cid,sequence,json.dumps(legs)));db.commit()
        cont=research.pair(legs,'continuous',retain=False)
        result=dict(stage=stage,continuous=cont,qualified=False)
        if cont['risk_pass'] and cont['net_pnl']>baseline['continuous']['net_pnl']:
            base=research.full(legs)
            if base['qualified']:
                stress=research.full(legs,2)
                result.update(base=base,cost2=stress)
                if stress['qualified'] and stress['continuous']['net_pnl']>baseline_stress['continuous']['net_pnl']:
                    chosen=save_case(cid,legs,research,base,stress);result['qualified']=True
                    write(RUN/'verified_improvement.json',chosen)
                    db.execute('UPDATE candidates SET result=? WHERE id=?',(json.dumps(result),cid));db.commit();count+=1
                    publish(baseline,baseline_stress,chosen,count);progress(count,'VERIFIED_TRAIN_ONLY_IMPROVEMENT')
                    print(json.dumps(dict(id=cid,legs=legs,continuous=base['continuous'],cost2=stress['continuous'])),flush=True)
                    break
        db.execute('UPDATE candidates SET result=? WHERE id=?',(json.dumps(result),cid));db.commit();count+=1
        if count%25==0:progress(count,'TRAIN-only search; no validated improvement yet')
        # Only immutable champion legs are cached. Avoid unbounded path storage.
        if len(research.rawcache)>30:
            parents={fingerprint(c) for c in parent};research.rawcache={k:v for k,v in research.rawcache.items() if k[0] in parents}
    db.close()


if __name__=='__main__':main()

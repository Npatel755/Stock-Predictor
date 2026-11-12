"""Pre-registered TRAIN-only PLAN sizing experiment, with one later-TRAIN check.

Discovery selects exactly once; subsequent TRAIN confirmation cannot choose a
different candidate. No validation/test loaders or deployment operations exist.
"""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import hashlib
import html
import json
from pathlib import Path
import shutil
import numpy as np
import pandas as pd
from eval_plan_risk_core import configurations,evaluate

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/eval_plan_risk_refinement_v1'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,default=str)+'\n',encoding='utf-8')


def packed(book):
    f=book.copy().sort_values(['tin','tout','per_micro'],kind='stable').reset_index(drop=True)
    if not f.tout.lt(pd.Timestamp('2024-01-01',tz='America/New_York')).all():raise PermissionError('Only TRAIN allowed')
    f['day']=f.tout.dt.normalize().dt.tz_localize(None).astype('datetime64[ns]')
    # Chronological day ownership matches incumbent's overnight accounting.
    f=f.sort_values(['day','tin','tout'],kind='stable').reset_index(drop=True)
    dates=pd.DatetimeIndex(f.day.drop_duplicates()).as_unit('ns').asi8//86400000000000
    offsets=np.r_[0,np.flatnonzero(f.day.ne(f.day.shift()).to_numpy())[1:],len(f)].astype(np.int64)
    assert len(offsets)==len(dates)+1
    assert f.risk_today.gt(0).all() and np.isfinite(f[['per_micro','mae_per_micro','n_contracts','risk_today']]).all().all()
    # All rows,including overnight,must be nonoverlapping under the fixed PLAN.
    for _,g in f.groupby('day'):
        assert all(g.tin.iloc[i]>=g.tout.iloc[i-1] for i in range(1,len(g)))
    arrays=(offsets,f.per_micro.to_numpy(float),f.mae_per_micro.to_numpy(float),f.n_contracts.to_numpy(float),
       f.risk_today.to_numpy(float),pd.DatetimeIndex(f.tin).as_unit('ns').asi8,pd.DatetimeIndex(f.tout).as_unit('ns').asi8,dates)
    extra=np.where(f.sleeve.str.contains('MES'),5.,2.)
    return f,arrays,extra


def policy_vector(c):return np.array([c[k] for k in ('fraction','cap','lock','top','late','late_day')],float)


def metrics(result):
    status,days,end,low=result
    success=status==1;fail=status==2
    return dict(n=len(status),pass_rate=100*float(success.mean()),failure_rate=100*float(fail.mean()),timeout_rate=100*float((status==0).mean()),
       median_pass_days=float(np.median(days[success])) if success.any() else None,
       minimum_attempt_balance_bound=float(low.min()),worst_success_balance_bound=float(low[success].min()) if success.any() else None)


def reference_day(per,mae,n,risk,a,b,k):
    """Independent deployed PLAN day reference for baseline parity checks."""
    accepted=[];worst=0.;dll=False;stop=400. if k==1 else 700.
    q=np.minimum(k*n,np.floor(900./risk));q=np.minimum(q,50)
    for j in range(len(per)):
        if q[j]<1:continue
        closed=[i for i in accepted if b[i]<a[j] or (b[i]==a[j] and a[i]<a[j])]
        realised=sum(per[i]*q[i] for i in closed)
        if realised<=-stop or realised<=-1000:break
        opn=sum(min(mae[i],per[i],0)*q[i] for i in accepted if i not in closed)
        w=realised+opn+min(mae[j],per[j])*q[j];worst=min(worst,w)
        if w<=-1000:dll=True;break
        accepted.append(j)
    pnl=-1000. if dll else max(-1000.,sum(per[i]*q[i] for i in accepted))
    return pnl,min(worst,pnl)


def parity(arrays):
    from eval_plan_risk_core import day
    offsets,per,mae,n,risk,a,b,dates=arrays;checks=0
    for i in range(len(dates)):
        l,r=offsets[i],offsets[i+1]
        for k in (1,2,3,5):
            expected=reference_day(per[l:r],mae[l:r],n[l:r],risk[l:r],a[l:r],b[l:r],k)
            actual=day(per[l:r],mae[l:r],n[l:r],risk[l:r],a[l:r],b[l:r],k,0.,0.,0.,900.,False,np.zeros(r-l))
            np.testing.assert_allclose(actual,expected,atol=1e-8,rtol=0);checks+=1
    return checks


def paired_year_bootstrap(start_days,inc_status,chosen_status):
    years=pd.to_datetime(start_days*86400000000000,utc=True).year.to_numpy()
    unique=np.unique(years);rng=np.random.default_rng(20261111);diff=(chosen_status==1).astype(float)-(inc_status==1).astype(float)
    estimates=[]
    for _ in range(1999):
        picked=rng.choice(unique,len(unique),replace=True)
        sample=np.concatenate([np.flatnonzero(years==y) for y in picked])
        estimates.append(100*float(diff[sample].mean()))
    return dict(block='start-calendar-year',blocks=len(unique),replicates=1999,mean_lift_pp=float(100*diff.mean()),
        percentile95_lift_pp=np.quantile(estimates,[.025,.975]).tolist(),limitation='Overlapping90-daystarts are dependent;onlysevenlaterTRAINyearblocks,so uncertainty is coarse andnotexternalconfirmation.')


def main():
    protocol=json.loads((RUN/'protocol.json').read_text());identity=json.loads((RUN/'training_data_identity.json').read_text())
    for name,expected in protocol['code_hashes'].items():
        if sha(ROOT/'scripts'/name)!=expected:raise ValueError('Frozen dependency changed:'+name)
    if sha(RUN/'training_book.parquet')!=identity['book_sha256'] or sha(RUN/'training_starts.csv')!=identity['starts_sha256']:raise ValueError('Frozen TRAIN input changed')
    if (RUN/'results.json').exists():print('Existing results preserved;no rescore.');return
    code=RUN/'code';code.mkdir(exist_ok=True)
    for name in protocol['code_hashes']:shutil.copyfile(ROOT/'scripts'/name,code/name)
    shutil.copyfile(Path(__file__),code/Path(__file__).name)
    baseline_dir=ROOT/'strategy_versions/evaluation_plan/v1.0.0-strict-causal'
    baseline_dir.mkdir(parents=True,exist_ok=True)
    baseline=dict(name='PLAN evaluation passer',routing='strict causal tin then fixedpriority;globaloneposition',
       policy=configurations()[0],account_scenario=identity['floor_model'],source_book_sha256=identity['book_sha256'],
       source_protocol_sha256=sha(RUN/'protocol.json'),inherited_limitations='Existingbookandincumbentpreviouslyselectedonhistoricaloutcomes;newresearchusesTRAINonly.')
    if not (baseline_dir/'baseline.json').exists():write(baseline_dir/'baseline.json',baseline)
    book=pd.read_parquet(RUN/'training_book.parquet');f,arrays,extra=packed(book)
    checks=parity(arrays);print('Independent baseline day checks:',checks,flush=True)
    dates=pd.to_datetime(pd.read_csv(RUN/'training_starts.csv').start)
    starts=(pd.DatetimeIndex(dates).as_unit('ns').asi8//86400000000000).astype(np.int64)
    boundary=int(pd.Timestamp('2017-01-01').value//86400000000000)
    discovery=starts[starts+90<=boundary];confirmation=starts[starts>=boundary]
    assert len(discovery)>100 and len(confirmation)>100
    cells=configurations();zeros=np.zeros_like(extra)
    inc=cells[0];discovery_rows=[]
    for c in cells:
        result=evaluate(*arrays,discovery,policy_vector(c),zeros);m=metrics(result)
        discovery_rows.append(dict(c,**m));print('DISCOVERY',c['name'],json.dumps(m),flush=True)
    pd.DataFrame(discovery_rows).to_csv(RUN/'all_discovery_policies.csv',index=False)
    ranked=sorted(enumerate(discovery_rows),key=lambda pair:(-pair[1]['pass_rate'],pair[1]['failure_rate'],pair[1]['median_pass_days'] or 999,pair[0]))
    selected_index=ranked[0][0];chosen=cells[selected_index]
    # Required seal: confirmation results do not exist when the winner is fixed.
    seal=dict(selected=chosen,selection_data='2010-2016purgedTRAINonly',discovery=discovery_rows[selected_index],
       discovery_csv_sha256=sha(RUN/'all_discovery_policies.csv'),protocol_sha256=sha(RUN/'protocol.json'),confirmation_accessed=False)
    with (RUN/'frozen_discovery_winner.json').open('x',encoding='utf-8') as stream:json.dump(seal,stream,indent=2)
    print('FROZEN BEFORE LATER TRAIN',chosen['name'],flush=True)
    I=evaluate(*arrays,confirmation,policy_vector(inc),zeros);C=evaluate(*arrays,confirmation,policy_vector(chosen),zeros)
    IS=evaluate(*arrays,confirmation,policy_vector(inc),extra);CS=evaluate(*arrays,confirmation,policy_vector(chosen),extra)
    im,cm=metrics(I),metrics(C);idm,cdm=discovery_rows[0],discovery_rows[selected_index]
    discovery_pass=bool(cdm['pass_rate']>=idm['pass_rate']+1. and cdm['failure_rate']<=idm['failure_rate'])
    confirmation_pass=bool(cm['pass_rate']>=im['pass_rate']+1. and cm['failure_rate']<=im['failure_rate'])
    accepted=bool(discovery_pass and confirmation_pass and selected_index!=0)
    bootstrap=paired_year_bootstrap(confirmation,I[0],C[0])
    outcomes=pd.DataFrame(dict(start=pd.to_datetime(confirmation*86400000000000),baseline_status=I[0],candidate_status=C[0],baseline_days=I[1],candidate_days=C[1],baseline_balance=I[2],candidate_balance=C[2],baseline_worst=I[3],candidate_worst=C[3]))
    outcomes.to_csv(RUN/'later_train_paired_attempts.csv',index=False)
    whole=metrics(evaluate(*arrays,starts,policy_vector(inc),zeros))
    result=dict(baseline=baseline,configuration_count=len(cells),baseline_all_training=whole,
       discovery=dict(period='2010June-2016,90daywindowsendingbefore2017',starts=len(discovery),baseline=idm,selected=cdm,gate=discovery_pass),
       frozen_candidate=chosen,confirmation=dict(period='2017-2023SeptemberTRAINstarts',baseline=im,candidate=cm,gate=confirmation_pass,
           extra_1point_cost_baseline=metrics(IS),extra_1point_cost_candidate=metrics(CS),paired_year_bootstrap=bootstrap),
       accepted_training_improvement=accepted,classification='TRAIN_ONLY_CHALLENGER' if accepted else 'NO_QUALIFIED_IMPROVEMENT',
       independent_day_parity_checks=checks,validation_accessed=False,test_accessed=False,paper_results_used_for_selection=False,
       limitations='Trade-levelMAE/DLLscenarioisnotexactintrabarfillreplay.Originaltradesareprice-normalizedtofrozenreferenceprices;notactualhistoricalUSDreturns.Overlappingstartsand44trialselectionlimitstatisticalconfidence.Nolive/paperchanges.')
    write(RUN/'results.json',result);write(ROOT/'reports/EVAL_PLAN_RISK_REFINEMENT_TRAIN.json',result)
    if accepted:
        version=ROOT/'strategy_versions/evaluation_plan/v1.1.0-train-challenger';version.mkdir(parents=True,exist_ok=True)
        write(version/'frozen_candidate.json',dict(candidate=chosen,results=result,discovery_seal_sha256=sha(RUN/'frozen_discovery_winner.json'),deployed=False))
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(12,4.8))
    for ax,section in zip(axes,('discovery','confirmation')):
        d=result[section];candidate=d['selected'] if section=='discovery' else d['candidate']
        values=[d['baseline']['pass_rate'],candidate['pass_rate']]
        rects=ax.bar(['PLANbaseline','FrozenTRAINchoice'],values,color=['#4c8ed4','#e9a23b']);ax.bar_label(rects,fmt='%.2f%%')
        ax.set(title='Earlier TRAIN discovery' if section=='discovery' else 'Later TRAIN confirmation',ylabel='90-day pass share(%)',ylim=(0,100));ax.grid(axis='y',alpha=.2)
    fig.suptitle('TRAIN-only risk-budget study: '+('gate passed' if accepted else 'no qualified improvement'))
    fig.tight_layout();fig.savefig(ROOT/'reports/EVAL_PLAN_RISK_REFINEMENT_TRAIN.png',dpi=150);plt.close(fig)
    rows=[]
    for section in ('discovery','confirmation'):
        d=result[section]
        for label,m in [('Baseline',d['baseline']),('Frozenchoice',d['selected'] if section=='discovery' else d['candidate'])]:
            rows.append(dict(Period=section,Policy=label,Starts=m['n'],Pass_pct=m['pass_rate'],Fail_pct=m['failure_rate'],Timeout_pct=m['timeout_rate'],Median_calendar_days=m['median_pass_days']))
    table=pd.DataFrame(rows).to_html(index=False,border=0,float_format=lambda v:f'{v:.2f}')
    title='TRAIN-only evaluation passer: '+('candidate clears frozen gates' if accepted else 'no qualifying improvement')
    page='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title><style>body{font:16px/1.65 system-ui;background:#101820;color:#edf2f7;max-width:1200px;padding:32px;margin:auto}a{color:#91d7ff}table{border-collapse:collapse}td,th{padding:12px;border-bottom:1px solid #445566}img{width:100%}pre{white-space:pre-wrap}.scroll{overflow:auto}</style><h1>'+title+'</h1><p>Fixed causal one-position PLAN book;45predeclaredpolicies including baseline. Discovery is earlierTRAIN;one winner is frozen before laterTRAINconfirmation. Validation,test,andforwardpaperoutcomes were not used. No live or paper configuration was changed.</p><div class="scroll">'+table+'</div><img src="EVAL_PLAN_RISK_REFINEMENT_TRAIN.png" alt="EarlierTRAINdiscoveryandlaterTRAINconfirmationpassshares"><h2>Frozen sizing policy</h2><pre>'+html.escape(json.dumps(chosen,indent=2))+'</pre><p>Risk budget per entry = min(cap,fraction × remaining static-floor cushion),if fraction is positive. Otherwise use the incumbent cap. Sizes are also limited by the defensive/endgame ladder and50micros. Position quantity is determined before observing its outcome or MAE. Positivefraction policies reduce risk as the account approaches the fixedfloor. Lock skips later entries only after already-realized profit meets target and consistency.</p><h2>Limits of the evidence</h2><p>Account scenario remains target$4,000,staticfloor−$2,000,DLL$1,000,55%best-dayconsistency,and90calendardays. These are the frozen incumbent research assumptions,not independently verified current account rules. DLL accounting uses a conservative whole-trade adverse bound,not an exact path/stopfill simulation. The book uses fixed reference-price normalization; results are historical scenarios,not actual normalized-dollar trades. Overlapping rolling attempts are dependent;44 alternatives create selection bias. No fresh unseen confirmation is available.</p><h2>LaterTRAIN uncertainty and execution stress</h2><pre>'+html.escape(json.dumps(result['confirmation'],indent=2))+'</pre><p><a href="../runs/eval_plan_risk_refinement_v1/protocol.json">Frozen protocol</a> · <a href="../runs/eval_plan_risk_refinement_v1/frozen_discovery_winner.json">Winner freeze before laterTRAIN</a> · <a href="../runs/eval_plan_risk_refinement_v1/all_discovery_policies.csv">All discovery cells</a> · <a href="EVAL_PLAN_RISK_REFINEMENT_TRAIN.json">Full result</a></p></html>'
    (ROOT/'reports/EVAL_PLAN_RISK_REFINEMENT_TRAIN.html').write_text(page,encoding='utf-8')
    print('FINAL',json.dumps(result),flush=True)


if __name__=='__main__':main()

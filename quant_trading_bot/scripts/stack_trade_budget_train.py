"""Predeclared TRAIN-only trade-allocation search using frozen stack signals.

This is a realized-drawdown research study, not a payout-account simulation.
Unknown intratrade equity/eligibility prevents funded-account certification.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil
import numpy as np
import pandas as pd
from stack_trade_budget_core import allocate,reference

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'runs/gemini_stack_continuation_v1/causal'
RUN=ROOT/'runs/stack_trade_budget_v1'
BOOKS=['base','both','triple','triple_AG_TRD60Q_1c','triple_AG_MES_TRD30_1c','triple_MNQ_E57_1c','triple_MES_MOM_1c']
FIELDS=['net_pnl','maximum_realized_cash_drawdown','trades','profit_factor','positive_years','minimum_annual_trades','maximum_inactive_calendar_days','risk_budget_skips','drawdown_breach']
NS_DAY=86400000000000


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,indent=2,default=str)+'\n',encoding='utf-8')
def timestamp(x):return int(pd.Timestamp(x,tz='UTC').value)


def freeze():
    RUN.mkdir(parents=True,exist_ok=True)
    if (RUN/'protocol.json').exists():raise RuntimeError('Frozen protocol exists')
    cells=[]
    for book in BOOKS:
        for night in (False,True):
            for cap in (1.,2.,3.):
                for risk_cap in (150.,225.,300.,450.):
                    for fraction in (.25,.5,1.):
                        cells.append(dict(name=f'{book}_N{int(night)}_C{int(cap)}_R{int(risk_cap)}_F{fraction:g}',
                            book=book,night=night,cap=cap,risk_cap=risk_cap,fraction=fraction))
    controls=[dict(name='CONTROL_STATIC_1',book='triple',night=True,cap=1.,risk_cap=450.,fraction=0.),
              dict(name='CONTROL_STATIC_2',book='triple',night=True,cap=2.,risk_cap=900.,fraction=0.)]
    files=[CACHE/('raw_'+b+'.parquet') for b in BOOKS]+[CACHE/'overnight_training.parquet',CACHE/'complete.json']
    code=RUN/'code';code.mkdir(exist_ok=True);sources={}
    for path in [Path(__file__),Path(__file__).with_name('stack_trade_budget_core.py'),ROOT/'tests/test_stack_trade_budget_core.py']:
        shutil.copyfile(path,code/path.name);sources[str(path.relative_to(ROOT))]=sha(path)
    write(RUN/'protocol.json',dict(run_id='stack_trade_budget_v1',frozen_at=str(pd.Timestamp.now(tz='UTC')),
        hypotheses=['Finite remaining drawdown budget may control closed-equity drawdown better than capital-only leverage.',
                    'Fixed dollar stop-risk allocation and integer contract caps may avoid scaling fragile trades.',
                    'Previously generated TRAIN signal books provide bounded ablations, not new validation-driven entries.'],
        candidates=cells,controls=controls,input_sha256={str(x.relative_to(ROOT)):sha(x) for x in files},source_sha256=sources,
        objective='Maximize earlier TRAIN net P&L after doubled costs among realized-DD/stability qualifiers. Compare with static1x and2x controls on identical books/clocks/costs.',
        periods=dict(earlier=['2010-07-01','2017-01-01'],later=['2017-01-01','2024-01-01'],boundary_entry_embargo_and_purge_days=8),
        selection='Rank candidates on EARLIER TRAIN only: cost2 net descending, base net descending, base DD ascending, name. Freeze one before later TRAIN. No alternate from later results. All blocks are previously reused TRAIN.',
        qualification='For both base and doubled costs: net>0; maximum transaction/closed-cash DD strictly<2000; >=150 trades; >=5 positive calendar years outof7; >=10 trades each year; no inactive stretch>180calendar days; zero observed DD breach. Original initial peak included; no loss clipping.',
        improvement='If static1x qualifies, frozen candidate must beat its base AND cost2 net by>=5%, in both earlier and later TRAIN. If static1x fails, a passing constrained candidate is a feasibility improvement, not a claim of higher unconstrained profit. Null diagnostic must pass. No funded/live promotion.',
        mechanics='Risk budget=min(configured cap,fraction*(1800-current realized DD)); qty=min(cap*source base size,6,floor(budget/(entry stop risk+stress cost))). No fractional contracts. Night only after500 completed profit. No cash withdrawals or balance-compounding ladder in this allocation study.',
        execution='Same frozen historical signal entries/exits and normalized returns; costs are1 dollar RT fee plus1point RT slippage in cache. Doubled costs subtract another1+instrument multiplier per contract. Half fee debited at entry. Single position reserved through exit-bar confirmation (tout+signal bar interval;1minute night). Skip overlapping entries, do not reorder priorities from returns. No new entry/exit tuning.',
        null_control='20 predetermined synthetic null paths. Blockwise sign reversal of gross trade returns in20calendar-day blocks, same signs across books, preserving costs/times/risks. Repeat complete504cell earlier search per seed. Compare selected cost2 net to95th percentile of null maximum qualifying net. Synthetic accounting diagnostic, not valid tradable signals or confirmatory p-value.',
        null_seeds=list(range(2026111100,2026111120)),
        caveats='Realized cash drawdown only: missing intratrade OHLC/MAE for extra sleeves. No intrabar funded compliance or payout estimate. Historical percent returns at inherited fixed MNQ27981.5/MES7584 reference levels, not actual historical dollar returns. Source strategies and earlier/later TRAIN repeatedly selected in past; unknown total historical multiplicity. No independent holdout claim.',
        history_inventory_sha256=sha(ROOT/'reports/TRAIN_HISTORY_INVENTORY_20261111.json'),
        skill_install_manifest_sha256=sha(ROOT/'reports/SKILL_ARCHIVE_INSTALL_20261111.json'),
        validation_accessed=False,test_accessed=False,forward_paper_accessed=False,automatic_holdout_stage=False))
    print('FROZEN',len(cells),'allocations +',len(controls),'controls',flush=True)


def qualify(m):
    return bool(m['net_pnl']>0 and m['maximum_realized_cash_drawdown']<2000 and m['trades']>=150 and
                m['positive_years']>=5 and m['minimum_annual_trades']>=10 and
                m['maximum_inactive_calendar_days']<=180 and m['drawdown_breach']==0)


def pack(a):
    m={k:float(v) for k,v in zip(FIELDS,a[0])};m['annual_net']=a[1].tolist();m['annual_trades']=a[2].astype(int).tolist();m['qualified']=qualify(m)
    return m


def load_books(protocol):
    for rel,h in protocol['input_sha256'].items():
        if sha(ROOT/rel)!=h:raise ValueError('Frozen TRAIN input changed: '+rel)
    meta=json.loads((CACHE/'complete.json').read_text())
    assert meta['mode']=='causal' and all(x['role']=='train' and pd.Timestamp(x['end'])<=pd.Timestamp('2024-01-01') for x in meta['training_loads'])
    nights=pd.read_parquet(CACHE/'overnight_training.parquet').copy()
    nights['per']=nights.net_today;nights['risk_today']=meta['night_risk'];nights['n_contracts']=1.;nights['prio']=100
    nights['sleeve']='NIGHT';nights['delay']=pd.Timedelta(minutes=1)
    books={};qa={}
    for name in BOOKS:
        df=pd.read_parquet(CACHE/('raw_'+name+'.parquet')).copy()
        df['per']=df.net_today/df.n_contracts;df['delay']=df.tin-df.dec
        assert df.delay.gt(pd.Timedelta(0)).all() and df.delay.le(pd.Timedelta(hours=2)).all()
        df=pd.concat([df,nights],ignore_index=True).sort_values(['tin','prio'],kind='stable').reset_index(drop=True)
        df['available_exit']=df.tout+df.delay
        assert df.tin.ge(pd.Timestamp('2010-01-01',tz='UTC')).all()
        assert df.available_exit.lt(pd.Timestamp('2024-01-01',tz='UTC')).all()
        assert df.available_exit.gt(df.tin).all() and df.risk_today.gt(0).all() and df.n_contracts.gt(0).all()
        assert np.isfinite(df[['per','risk_today','n_contracts']]).all().all()
        assert set(df.inst)<=set(('MES','MNQ'))
        books[name]=df
        qa[name]=dict(rows=len(df),first=str(df.tin.min()),last=str(df.available_exit.max()),
            calendar='UTC execution timestamps; realized annual return assigned to exit-confirmation year',
            exit_confirmation='exit timestamp + completed signal-bar interval, night+1minute; conservative occupancy',
            unknown_extra_sleeve_intratrade_MAE=True)
    write(RUN/'training_input_qa.json',dict(books=qa,metadata_sha256=sha(CACHE/'complete.json'),
        no_new_market_data_loaded=True,validation_accessed=False,test_accessed=False))
    return books


def inputs(df,period,night_on):
    start,end=timestamp(period[0]),timestamp(period[1]);clock=df.tin.dt.as_unit('ns').astype('int64')
    mask=(clock>=start+8*NS_DAY)&(clock<end-8*NS_DAY)
    if not night_on:mask&=df.sleeve!='NIGHT'
    d=df.loc[mask].reset_index(drop=True)
    years=(d.available_exit.dt.year-int(period[0][:4])).to_numpy(np.int64)
    assert ((years>=0)&(years<7)).all()
    args=(d.tin.dt.as_unit('ns').astype('int64').to_numpy(),d.available_exit.dt.as_unit('ns').astype('int64').to_numpy(),
          d.per.to_numpy(float),d.risk_today.to_numpy(float),d.n_contracts.to_numpy(float),
          d.inst.map({'MNQ':2.,'MES':5.}).to_numpy(float),(d.sleeve=='NIGHT').to_numpy(),years,start,end)
    return args,d


def evaluate(args,c,cost,verify=False):
    tail=(c['cap'],c['risk_cap'],c['fraction'],float(cost));a=allocate(*args,*tail)
    np.testing.assert_allclose(a[0][0],a[1].sum(),atol=1e-7,rtol=0)
    if verify:
        b=reference(*args,*tail)
        for x,y in zip(a,b):np.testing.assert_allclose(x,y,atol=1e-7,rtol=0)
    return pack(a),a


def passes_improvement(m,control):
    if not (m['base']['qualified'] and m['cost2']['qualified']):return False
    if control['base']['qualified'] and control['cost2']['qualified']:
        return all(m[k]['net_pnl']>=1.05*control[k]['net_pnl'] for k in ('base','cost2'))
    return True


def main():
    if (RUN/'results.json').exists():print('Completed frozen results preserved');return
    protocol=json.loads((RUN/'protocol.json').read_text())
    for rel,h in protocol['source_sha256'].items():assert sha(ROOT/rel)==h
    books=load_books(protocol);early={};paths={};rows=[]
    args_cache={(b,n):inputs(books[b],protocol['periods']['earlier'],n) for b in BOOKS for n in (False,True)}
    for i,c in enumerate(protocol['controls']+protocol['candidates']):
        path=RUN/'checkpoints'/f"{c['name']}.json";path.parent.mkdir(exist_ok=True)
        if path.exists():m=json.loads(path.read_text())
        else:
            args,_=args_cache[(c['book'],c['night'])];m={}
            for cost,label in ((1,'base'),(2,'cost2')):m[label],_=evaluate(args,c,cost)
            write(path,m)
        early[c['name']]=m
        rows.append(dict(**c,qualified=bool(m['base']['qualified'] and m['cost2']['qualified']),
            net=m['base']['net_pnl'],cost2_net=m['cost2']['net_pnl'],drawdown=m['base']['maximum_realized_cash_drawdown'],
            cost2_drawdown=m['cost2']['maximum_realized_cash_drawdown'],trades=m['base']['trades'],
            positive_years=m['base']['positive_years'],cost2_positive_years=m['cost2']['positive_years'],
            maximum_inactive_days=m['base']['maximum_inactive_calendar_days']))
        if (i+1)%50==0:print('EARLIER TRAIN',i+1,'/',len(protocol['candidates'])+2,flush=True)
    frame=pd.DataFrame(rows).sort_values(['qualified','cost2_net','net','drawdown','name'],ascending=[False,False,False,True,True])
    frame.to_csv(RUN/'all_earlier_training_allocations.csv',index=False)
    eligible=frame[frame.qualified & ~frame.name.str.startswith('CONTROL_')]
    control_early=early['CONTROL_STATIC_1']
    names={c['name']:c for c in protocol['candidates']}
    choice=names[eligible.iloc[0]['name']] if len(eligible) else None
    freeze=RUN/'frozen_earlier_train_choice.json'
    payload=dict(configuration=choice,earlier_metrics=early[choice['name']] if choice else None,
        earlier_qualifying_allocations=len(eligible),protocol_sha256=sha(RUN/'protocol.json'),
        ranked_csv_sha256=sha(RUN/'all_earlier_training_allocations.csv'),later_train_used_for_choice=False,
        previous_research_used_later_train=True)
    if freeze.exists():assert json.loads(freeze.read_text())==payload
    else:write(freeze,payload)
    print('FROZEN CHOICE',json.dumps(choice),'qualifiers',len(eligible),flush=True)
    # Whole-grid null diagnostics use only earlier TRAIN. No adaptation to them.
    null_rows=[]
    for seed in protocol['null_seeds']:
        cp=RUN/'null_checkpoints'/f'{seed}.json';cp.parent.mkdir(exist_ok=True)
        if cp.exists():record=json.loads(cp.read_text());null_rows.append(record);continue
        rng=np.random.default_rng(seed);lo=timestamp('2010-01-01')//NS_DAY;hi=timestamp('2017-01-01')//NS_DAY
        signs=rng.choice(np.array([-1.,1.]),size=int((hi-lo)//20+3));best=0.;nq=0
        null_args={}
        for key,(args,_) in args_cache.items():
            a=list(args);block=((a[0]//NS_DAY-lo)//20).astype(int)
            # Reverse gross returns; fees/slippage are still subtracted.
            costs=1.+a[5];a[2]=(a[2]+costs)*signs[block]-costs;null_args[key]=tuple(a)
        for c in protocol['candidates']:
            m,_=evaluate(null_args[(c['book'],c['night'])],c,2)
            if m['qualified']:best=max(best,m['net_pnl']);nq+=1
        record=dict(seed=seed,maximum_qualified_cost2_net=best,qualified_cells=nq);write(cp,record);null_rows.append(record)
    pd.DataFrame(null_rows).to_csv(RUN/'synthetic_null_full_search.csv',index=False)
    threshold=float(np.percentile([r['maximum_qualified_cost2_net'] for r in null_rows],95))
    null_pass=bool(choice and early[choice['name']]['cost2']['net_pnl']>threshold)
    later_results={};independent_checks=0
    selected=[*protocol['controls']]+([choice] if choice else [])
    for phase,period in protocol['periods'].items():
        for c in selected:
            args,df=inputs(books[c['book']],period,c['night']);m={}
            for cost,label in ((1,'base'),(2,'cost2')):
                m[label],a=evaluate(args,c,cost,verify=True);independent_checks+=1
                folder=RUN/'selected'/phase/c['name'];folder.mkdir(parents=True,exist_ok=True)
                live=a[3]>0;ledger=df.loc[live,['sleeve','inst','tin','available_exit','per','risk_today']].copy()
                ledger['quantity']=a[3][live];ledger['net_pnl']=(args[2][live]-(cost-1)*(1+args[5][live]))*a[3][live]
                ledger['cash_pnl']=a[4][live];ledger.to_csv(folder/(label+'_trades.csv'),index=False)
                np.testing.assert_allclose(ledger.net_pnl.sum(),m[label]['net_pnl'],atol=1e-7,rtol=0)
                curve=pd.DataFrame(dict(timestamp_utc=pd.to_datetime(args[1][live],utc=True),cash_pnl=a[4][live]))
                curve.to_csv(folder/(label+'_closed_equity.csv'),index=False)
                if phase=='earlier':
                    for k in m[label]:
                        if k in ('annual_net','annual_trades'):np.testing.assert_allclose(m[label][k],early[c['name']][label][k],atol=1e-7,rtol=0)
                        else:assert m[label][k]==early[c['name']][label][k]
            if phase=='later':later_results[c['name']]=m
    accepted=bool(choice and null_pass and passes_improvement(early[choice['name']],control_early) and
        passes_improvement(later_results[choice['name']],later_results['CONTROL_STATIC_1']))
    result=dict(status='REALIZED_DRAWDOWN_TRAIN_RESEARCH_CANDIDATE' if accepted else 'NO_QUALIFIED_IMPROVEMENT',
        accepted_training_feasibility_improvement=accepted,candidates=len(protocol['candidates']),controls=2,
        earlier_qualified=len(eligible),configuration=choice,earlier=early[choice['name']] if choice else None,
        earlier_controls={c['name']:early[c['name']] for c in protocol['controls']},
        later_reused_train=later_results,synthetic_null=dict(repeats=20,whole_grid_cells=20*len(protocol['candidates']),
            cost2_maximum_net_95th_percentile=threshold,passed=null_pass,not_confirmatory=True),
        comparison_to_Gemini='Different execution-clock/size/risk objective. No withdrawals simulated. Cannot compare these trading profits directly to prior mean24month withdrawals or claim a funded-payout replacement.',
        caveats=protocol['caveats'],intrabar_drawdown_verified=False,funded_account_certified=False,
        independent_unseen_confirmation=False,validation_accessed=False,test_accessed=False,forward_paper_accessed=False,deployment_changed=False,
        protocol_sha256=sha(RUN/'protocol.json'),frozen_choice_sha256=sha(freeze))
    verify=dict(passed=True,independent_reference_cases=independent_checks,cash_trade_annual_conservation=True,
        source_and_input_hashes_match=True,chronology_guards=True,no_clipped_loss_fills=True,
        validation_accessed=False,test_accessed=False,maximum_intrabar_drawdown_known=False)
    write(RUN/'results.json',result);write(RUN/'verification.json',verify)
    if accepted:
        version=ROOT/'strategy_versions/gemini_triple_stack/v1.2.0-trade-budget-research';version.mkdir(parents=True,exist_ok=True)
        write(version/'frozen_candidate.json',dict(result=result,deployed=False,payout_replacement=False))
        shutil.copyfile(RUN/'protocol.json',version/'protocol.json');shutil.copytree(RUN/'code',version/'code',dirs_exist_ok=True)
    publish(result,verify,frame)
    print('FINAL',json.dumps(dict(status=result['status'],choice=choice,earlier_qualified=len(eligible),null_pass=null_pass,reference_checks=independent_checks)),flush=True)


def publish(r,v,frame):
    stem='STACK_TRADE_BUDGET_TRAIN';write(ROOT/'reports'/f'{stem}.json',r);write(ROOT/'reports'/f'{stem}_verification.json',v)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(12,4.5))
    for ax,phase in zip(axes,('earlier','later')):
        for c in ['CONTROL_STATIC_1','CONTROL_STATIC_2']+([r['configuration']['name']] if r['configuration'] else []):
            p=RUN/'selected'/phase/c/'base_closed_equity.csv'
            if p.exists():
                d=pd.read_csv(p,parse_dates=['timestamp_utc']);ax.plot(d.timestamp_utc,d.cash_pnl,label=c if c.startswith('CONTROL') else 'Frozen choice')
        ax.set(title=phase+' TRAIN (reused)',ylabel='Trading P&L at closed trades ($)');ax.legend();ax.grid(alpha=.2);ax.tick_params(axis='x',rotation=25)
    fig.tight_layout();fig.savefig(ROOT/'reports'/f'{stem}.png',dpi=150);plt.close(fig)
    comparisons=[]
    if r['configuration']:
        for period,models in [('Earlier',dict(**r['earlier_controls'],CHOICE=r['earlier'])),('Later reused',r['later_reused_train'])]:
            for name,m in models.items():
                for cost in ('base','cost2'):
                    x=m[cost];comparisons.append(dict(Period=period,Policy=name if name.startswith('CONTROL') else 'CHOICE',Costs=cost,
                        Net_PnL=x['net_pnl'],Realized_cash_DD=x['maximum_realized_cash_drawdown'],Trades=x['trades'],Positive_years=x['positive_years'],Qualified=x['qualified']))
    title='Trade-budget TRAIN research: '+('realized-drawdown candidate' if r['accepted_training_feasibility_improvement'] else 'no qualifying improvement')
    page='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title><style>body{font:16px/1.65 system-ui;max-width:1400px;margin:32px auto;padding:0 24px;background:#111820;color:#e8edf2}a{color:#90d5ff}pre{white-space:pre-wrap}table{border-collapse:collapse;font-size:14px}th,td{padding:9px;border-bottom:1px solid #456}.scroll{overflow:auto}img{width:100%}.note{padding:18px;background:#382c20}</style><h1>'+title+'</h1><p>504 predeclared allocations plus2 matched controls; TRAIN-only ranking and20 whole-grid synthetic null diagnostics. One choice frozen before later TRAIN. Validation/test/forward-paper outcomes excluded; no deployment.</p><p class="note">Realized cash drawdown only. Intratrade marked equity is unknown for additional sleeves; this is NOT a verified sub-$2,000 intrabar funded strategy. No withdrawals modeled: these profits cannot be compared to prior payout totals. Both TRAIN blocks have been used before.</p><div class="scroll">'+pd.DataFrame(comparisons).to_html(index=False,border=0,float_format=lambda x:f'{x:,.2f}')+'</div><img src="'+stem+'.png" alt="Closed trading equity on earlier and later TRAIN"><h2>Frozen allocation</h2><pre>'+html.escape(json.dumps(r['configuration'],indent=2))+'</pre><p>Before each entry, integer quantity is limited by the configured contract multiplier and dollar stop-risk cap, and by a fraction of the remaining $1,800 drawdown budget. Completed prior P&amp;L is the only return information used in allocation. Night positions need $500 accumulated profit. Signal entries/exits, fixed priorities and per-contract economics remain inherited. Exit-bar confirmation delays prevent early reuse of realized P&amp;L. Losses are debited in full, never clipped.</p><h2>Limits and null diagnostics</h2><p>'+html.escape(r['caveats'])+'</p><pre>'+html.escape(json.dumps(r['synthetic_null'],indent=2))+'</pre><h2>Earlier TRAIN top20</h2><div class="scroll">'+frame.head(20).to_html(index=False,border=0,float_format=lambda x:f'{x:,.2f}')+'</div><p><a href="../runs/stack_trade_budget_v1/protocol.json">Frozen protocol</a> · <a href="../runs/stack_trade_budget_v1/all_earlier_training_allocations.csv">All506 rows</a> · <a href="TRAIN_HISTORY_INVENTORY_20261111.json">Training-history inventory</a> · <a href="SKILL_ARCHIVE_INSTALL_20261111.json">Skill installation manifest</a> · <a href="'+stem+'.json">Full results</a></p></html>'
    (ROOT/'reports'/f'{stem}.html').write_text(page,encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true');parser.add_argument('--run',action='store_true');args=parser.parse_args()
    if args.freeze:freeze()
    elif args.run:main()
    else:parser.error('Choose --freeze or --run')

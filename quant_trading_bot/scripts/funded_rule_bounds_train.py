"""Rule-aware bounded TRAIN research after explicit user criterion change.

Intraday-only causal one-position prototype; NOT the deployed Fortress card.
No forced-fill profit claims on paths where program controls could bind.
"""
import argparse
import json
from pathlib import Path
import shutil
import numpy as np
import pandas as pd
import stack_continuous_train as data
import stack_continuous_exposure_fix_train as fix
from funded_nonbinding_core import replay,reference

ROOT=data.ROOT;RUN=ROOT/'runs/funded_rule_bounds_v1'
RULES=ROOT/'research/prop_firms/topstep_daily_static_verified_20261111.json'
POLICY=ROOT/'research/FUNDED_RESEARCH_POLICY.json'
PARENT=ROOT/'runs/stack_continuous_exposure_fixed_v1'
BASE=dict(name='F4X_LADDER_INTRADAY_CAUSAL_BENCHMARK',keep=8500.,max_m=4.,initial_m=1.,cap=900.,fraction=0.)
COLUMNS=['gross_withdrawn','trader_cash','ending_balance','known_trading_pnl','economic_book_value','payouts','trades','possible_floor_touch','possible_DLL_touch','trading_OHLC_DD_bound','maximum_quantity','minimum_floor_bound_room','minimum_DLL_bound_room','maximum_inactive_days']


def freeze():
    RUN.mkdir(parents=True,exist_ok=True)
    if (RUN/'protocol.json').exists():raise RuntimeError('Frozen protocol preserved')
    policy=json.loads(POLICY.read_text());assert policy['strict_global_drawdown_required'] is False
    parent=json.loads((PARENT/'protocol.json').read_text());cases=[]
    for keep in (2000.,3500.,5000.,8500.):
        for maximum in (2.,3.,4.):
            for initial in (1.,2.):
                for cap in (300.,600.,900.):
                    for fraction in (.25,.5):
                        cases.append(dict(name=f'K{keep:g}_M{maximum:g}_I{initial:g}_C{cap:g}_F{fraction:g}',keep=keep,max_m=maximum,initial_m=initial,cap=cap,fraction=fraction))
    code=RUN/'code';code.mkdir(exist_ok=True);hashes={}
    for path in (Path(__file__),Path(__file__).with_name('funded_nonbinding_core.py'),Path(__file__).with_name('stack_continuous_train.py'),
                 Path(__file__).with_name('stack_continuous_exposure_fix_train.py'),ROOT/'tests/test_funded_nonbinding_core.py',
                 ROOT/'scripts/mass_execution.py',ROOT/'src/quant_futures/ensemble_paper.py'):
        hashes[str(path.relative_to(ROOT))]=data.sha(path);shutil.copyfile(path,code/path.name)
    p=dict(run_id='funded_rule_bounds_v1',frozen_at=str(pd.Timestamp.now(tz='UTC')),candidates=cases,benchmark=BASE,
        source_hashes=hashes,rules_sha256=data.sha(RULES),user_policy_sha256=data.sha(POLICY),
        training_sources=parent['training_sources'],base_book_sha256=parent['base_book_sha256'],catalog_sha256=parent['catalog_sha256'],
        authorization='User explicitly replaces blanket2000peakdrawdown limit with verified account floor/DLL. V/T still prohibited. Unrun strict entry-filter draft superseded, no scores generated.',
        rule_scope='Published Drop011DailyPayouts+Static XFA. Balance0,floor-2000untilfirstpayout then0;DLL1000. No globalpeakdrawdown gate. Other operational/news/broker/discretion rules and individual dashboard not certified.',
        hypothesis='Floor/DLLremaining-room entry allocation may preserve feasible cashflows while capital grows; retain profits against verified floor, not an arbitrary trading-equity peak.',
        mechanics='Fixed3source sleeves, intraday-only causal1position. Day-start Fortress-style ladder1x/2x4000/3x4800/4x6500, capped per config with optional2xinitial. Personalrealizedstop400at1xelse700. Integerqty<=m*baseweights and20global. Riskcap additionallyfraction*floorroom andfraction*DLLroom. No outcome-dependent entry sizing.',
        payout_policy='Daily path only, once per completed traded day, keep>=official2000buffer,request250..1500,90%trader. Trader additionally limits each withdrawal to netnewprofits since prior request. Fivewinningdays path not simulated;8000neverusedasdailycap. Payout timing assumes day settled before request.',
        metric='Economic book value=traderreceived+0.9*max(0,remainingbalance-2000). Retained term is not guaranteed future payout. Report cashreceived separately. No ownership/fee/networth claim.',
        safety='After exante qty is fixed, full-trade conservative OHLC adverse bounds check daystart loss and account floor. A possible touch is UNRESOLVED_INTERVENTION, not a confirmed violation/closure. No clippedloss or madeup liquidationfill. Only zero-touch paths support unchanged-fill value claims. Inactivity>30days also unresolved per XFA mayclose rule.',
        data='TRAIN2010-2023 only, historical rawfills/microeconomics. Reconstruct all1808source opportunities, restore prior research-only entryembargo rows; external splits unchanged. E-mini proxyquotes before2019. All scheduled-open exposure intervals use sourceengine verified open-exit handling.',
        source_transform='Reuse frozen prepare with date-mask bounds expanded withinTRAIN solely to retain every cached base signal: start2009Dec1,end2024Jan9,internalcut2030. Underlying source queries and asserts still reject observations>=2024. Separate raw/corrected caches/hashes preserved.',
        selection='55earlier TRAIN24monthwindows start2010Jul..2015Jan,end<=2017. Choose largest mean economicbookvalue among all-zero-touch/inactivity paths with positive value. Ties larger tradercash then smaller possible DLLcount then name. Freeze one before61later TRAIN starts2017Jan..2022Jan. No alternate from laterresults; repeatedTRAIN not fresh confirmation.',
        acceptance='Research-feasibility only: zero possiblefloor/DLL/inactivity cases and positive meanvalue both internalblocks. If benchmark alsofullyresolved, require>=5%higher economicvalue bothblocks; otherwise no demonstrated profit-superiority claim. No deployment, exactforcedfills,fullpayout/livecompliance claimed.',
        cost_stress='Base and extra1dollar+1point percontract; same entry risk/MAE reserves stressed. Both must pass bounds/inactivity, positive value; primary rank uses lower economicvalue of two costs.',
        validation_accessed=False,test_accessed=False,paper_outcomes_accessed=False,automatic_holdout_stage=False)
    data.write(RUN/'protocol.json',p);print('FROZEN',len(cases),'account policies; globalDDgateOFF',flush=True)


def prepare(p):
    final=RUN/'complete_training_book.parquet'
    if final.exists():
        identity=json.loads((RUN/'input_identity.json').read_text());assert data.sha(final)==identity['sha256'];return pd.read_parquet(final)
    raw=RUN/'raw_bounds';raw.mkdir(exist_ok=True);corrected=RUN/'corrected_bounds';corrected.mkdir(exist_ok=True)
    saved=(data.RUN,data.START,data.END,data.CUT,fix.ORIGINAL,fix.RUN)
    try:
        data.RUN=raw;data.START=int(pd.Timestamp('2009-12-01T00:00Z').value);data.END=int(pd.Timestamp('2024-01-09T00:00Z').value);data.CUT=int(pd.Timestamp('2030-01-01T00:00Z').value)
        data.prepare(p)
        amended=dict(p,data_integrity_repair=dict(original_bound_table_sha256=data.sha(raw/'training_trade_bounds.parquet'),
            source_engine_sha256=data.sha(ROOT/'scripts/mass_execution.py'),source_sleeve_wrapper_sha256=data.sha(ROOT/'src/quant_futures/ensemble_paper.py')))
        data.write(RUN/'pre_score_data_repair_seal.json',amended['data_integrity_repair'])
        fix.ORIGINAL=raw;fix.RUN=corrected;d=fix.corrected_prepare(amended)
    finally:data.RUN,data.START,data.END,data.CUT,fix.ORIGINAL,fix.RUN=saved
    assert d.path_valid.all() and d.available_exit.lt(pd.Timestamp('2024-01-01T00:00Z')).all()
    d.to_parquet(final,index=False)
    data.write(RUN/'input_identity.json',dict(sha256=data.sha(final),rows=len(d),all_paths_quote_verified=True,
        earliest=str(d.tin.min()),latest=str(d.available_exit.max()),rawhash=data.sha(raw/'training_trade_bounds.parquet'),
        correctedhash=data.sha(corrected/'training_trade_bounds.parquet'),validation_accessed=False,test_accessed=False))
    return d


def windows():
    t=pd.date_range('2010-07-01','2022-01-01',freq='MS');start=t.as_unit('ns').asi8;end=np.array([int((v+pd.DateOffset(months=24)).value) for v in t],np.int64)
    return t,start,end


def arrays(d,cost):
    day=d.tin.dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize().dt.as_unit('ns').astype('int64').to_numpy()
    days,first=np.unique(day,return_index=True);offset=np.r_[first,len(d)].astype(np.int64)
    extra=(cost-1)*(1+d.multiplier.to_numpy(float))
    return (days,offset,d.tin.dt.as_unit('ns').astype('int64').to_numpy(),d.available_exit.dt.as_unit('ns').astype('int64').to_numpy(),
        d.per.to_numpy(float)-extra,d.entry_risk.to_numpy(float)+extra,d.n_contracts.to_numpy(float),
        d.adverse.to_numpy(float)-extra,d.favorable.to_numpy(float)-.5*(cost-1))


def summarize(a):
    return dict(mean_trader_cash=float(a[:,1].mean()),mean_economic_book_value=float(a[:,4].mean()),
        mean_gross_withdrawals=float(a[:,0].mean()),mean_ending_balance=float(a[:,2].mean()),mean_known_trading_pnl=float(a[:,3].mean()),
        mean_payouts=float(a[:,5].mean()),mean_trades=float(a[:,6].mean()),possible_floor_cases=int(a[:,7].sum()),possible_DLL_cases=int(a[:,8].sum()),
        inactivity_cases=int(((a[:,13]>30)&(a[:,7]==0)&(a[:,8]==0)).sum()),maximum_trading_OHLC_DD_bound=float(a[:,9].max()),windows=len(a),
        resolved=bool(not np.any(a[:,7:9]) and not np.any(a[:,13]>30)))


def score(inputs,c,idx,check=False):
    t,start,end=windows();out={};raw={};references=0
    for cost,label in ((1,'base'),(2,'cost2')):
        a=[]
        for i in idx:
            args=(*inputs[cost],start[i],end[i],c['keep'],c['max_m'],c['initial_m'],c['cap'],c['fraction'])
            row=replay(*args);np.testing.assert_allclose(row[0]+row[2],row[3],atol=1e-7,rtol=0)
            if check:np.testing.assert_allclose(row,reference(*args),atol=1e-7,rtol=0);references+=1
            a.append(row)
        raw[label]=np.asarray(a);out[label]=summarize(raw[label])
    out['reference_checks']=references;return out,raw


def qualify(m):return bool(all(m[k]['resolved'] and m[k]['mean_economic_book_value']>0 for k in ('base','cost2')))


def main():
    if (RUN/'results.json').exists():print('Completed run retained');return
    p=json.loads((RUN/'protocol.json').read_text())
    for rel,h in p['source_hashes'].items():assert data.sha(ROOT/rel)==h
    assert data.sha(RULES)==p['rules_sha256'] and data.sha(POLICY)==p['user_policy_sha256']
    d=prepare(p);inp={k:arrays(d,k) for k in (1,2)};t,start,end=windows()
    early=np.flatnonzero(end<=int(pd.Timestamp('2017-01-01').value));later=np.flatnonzero(start>=int(pd.Timestamp('2017-01-01').value))
    rows=[];metrics={}
    for i,c in enumerate([BASE]+p['candidates']):
        path=RUN/'checkpoints'/f"{c['name']}.json";path.parent.mkdir(exist_ok=True)
        if path.exists():m=json.loads(path.read_text())
        else:m,_=score(inp,c,early);data.write(path,m)
        metrics[c['name']]=m
        rows.append(dict(**c,qualified=qualify(m),worst_cost_value=min(m[k]['mean_economic_book_value'] for k in ('base','cost2')),
            trader_cash=m['base']['mean_trader_cash'],base_value=m['base']['mean_economic_book_value'],stress_value=m['cost2']['mean_economic_book_value'],
            base_floor=m['base']['possible_floor_cases'],base_DLL=m['base']['possible_DLL_cases'],stress_DLL=m['cost2']['possible_DLL_cases'],
            base_inactivity=m['base']['inactivity_cases'],stress_inactivity=m['cost2']['inactivity_cases'],
            trading_DD_bound=m['base']['maximum_trading_OHLC_DD_bound']))
        if (i+1)%30==0:print('EARLIER TRAIN',i+1,'/145',flush=True)
    frame=pd.DataFrame(rows).sort_values(['qualified','worst_cost_value','trader_cash','base_DLL','name'],ascending=[False,False,False,True,True]);frame.to_csv(RUN/'all_earlier_account_policies.csv',index=False)
    viable=frame[frame.qualified & (frame.name!=BASE['name'])];lookup={c['name']:c for c in p['candidates']};choice=lookup[viable.iloc[0]['name']] if len(viable) else None
    seal=dict(configuration=choice,earlier=metrics[choice['name']] if choice else None,qualifiers=len(viable),
        protocol_sha256=data.sha(RUN/'protocol.json'),ranking_sha256=data.sha(RUN/'all_earlier_account_policies.csv'),later_used_for_choice=False)
    frozen=RUN/'frozen_earlier_choice.json'
    if frozen.exists():assert json.loads(frozen.read_text())==seal
    else:data.write(frozen,seal)
    print('FROZEN CHOICE',json.dumps(choice),'qualifiers',len(viable),flush=True)
    later_metrics={};references=0
    for c in [BASE]+([choice] if choice else []):
        for idx,label in ((early,'earlier'),(later,'later')):
            m,raw=score(inp,c,idx,True);references+=m['reference_checks']
            if label=='later':later_metrics[c['name']]=m
            folder=RUN/'selected'/label/c['name'];folder.mkdir(parents=True,exist_ok=True)
            for k,a in raw.items():
                f=pd.DataFrame(a,columns=COLUMNS);f.insert(0,'start',t[idx]);f.to_csv(folder/(k+'_account_paths.csv'),index=False)
    accepted=bool(choice and qualify(later_metrics[choice['name']]))
    benchmark_resolved=qualify(metrics[BASE['name']]) and qualify(later_metrics[BASE['name']])
    superiority=bool(accepted and benchmark_resolved and all(
        cm[k]['mean_economic_book_value']>=1.05*bm[k]['mean_economic_book_value']
        for cm,bm in ((metrics[choice['name']],metrics[BASE['name']]),(later_metrics[choice['name']],later_metrics[BASE['name']])) for k in ('base','cost2')))
    result=dict(status='RULE_BOUND_FEASIBILITY_CANDIDATE' if accepted else 'NO_QUALIFIED_ACCOUNT_POLICY',accepted_feasibility=accepted,
        demonstrated_matched_profit_improvement=superiority,benchmark_fully_resolved=benchmark_resolved,configuration=choice,candidates=len(p['candidates']),
        earlier_choice=metrics[choice['name']] if choice else None,earlier_benchmark=metrics[BASE['name']],later=later_metrics,
        global_drawdown_filter_used=False,scope='Intraday-only causal1position prototype, not exact deployed Fortress4X, no overnight/5daypath. Paths with possible program interventions are unresolved,not confirmed account failures.',
        metric_limits='Book value includes hypothetical residual profit,not guaranteed payout. Cases with rule-bound touches cannot validate forced-fill cashflows. Zero-touch conservative bounds avoid this unresolved fill branch.',
        validation_accessed=False,test_accessed=False,paper_outcomes_accessed=False,deployment_changed=False,independent_confirmation=False,
        protocol_sha256=data.sha(RUN/'protocol.json'),rules_sha256=data.sha(RULES),frozen_choice_sha256=data.sha(frozen))
    verify=dict(passed=True,independent_account_reference_cases=references,all_computed_cash_conserved=True,global_DD_gate_removed=True,
        floor_and_DLL_separate=True,no_loss_clipping_or_fake_liquidations=True,source_hashes_match=True,validation_accessed=False,test_accessed=False)
    data.write(RUN/'results.json',result);data.write(RUN/'verification.json',verify)
    if accepted:
        archive=ROOT/'strategy_versions/gemini_triple_stack/v2.0.0-rule-bound-research';archive.mkdir(parents=True,exist_ok=True)
        data.write(archive/'frozen_candidate.json',dict(result=result,deployed=False));shutil.copyfile(RUN/'protocol.json',archive/'protocol.json');shutil.copytree(RUN/'code',archive/'code',dirs_exist_ok=True);shutil.copyfile(RULES,archive/RULES.name)
    publish(result,verify,frame)
    print('FINAL',json.dumps(dict(accepted=accepted,profit_improvement=superiority,choice=choice,qualifiers=len(viable),earlier=result['earlier_choice'],later=later_metrics)),flush=True)


def publish(r,v,frame):
    import html
    stem='FUNDED_RULE_BOUNDS_TRAIN';data.write(ROOT/'reports'/f'{stem}.json',r);data.write(ROOT/'reports'/f'{stem}_verification.json',v)
    comparisons=[]
    for phase,models in [('Earlier',dict(BENCHMARK=r['earlier_benchmark'],**({'CHOICE':r['earlier_choice']} if r['earlier_choice'] else {}))),('Later',r['later'])]:
        for name,m in models.items():
            for cost in ('base','cost2'):
                x=m[cost];comparisons.append(dict(Period=phase,Policy=name,Costs=cost,Mean_trader_cash=x['mean_trader_cash'],Mean_book_value=x['mean_economic_book_value'],Floor_bound_touches=x['possible_floor_cases'],DLL_bound_touches=x['possible_DLL_cases'],Inactivity_cases=x['inactivity_cases'],Trading_DD_bound=x['maximum_trading_OHLC_DD_bound']))
    title='Funded TRAIN rule-bound screen: '+('feasibility candidate' if r['accepted_feasibility'] else 'no qualified policy')
    page='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title><style>body{font:16px/1.6 system-ui;max-width:1400px;margin:32px auto;padding:0 24px;background:#111820;color:#e9edf2}a{color:#94d6ff}table{border-collapse:collapse;font-size:14px}th,td{padding:9px;border-bottom:1px solid #456}.scroll{overflow:auto}pre{white-space:pre-wrap}.note{background:#382d22;padding:18px}</style><h1>'+title+'</h1><p>144frozen account policies plus matched intraday control;TRAIN only. User explicitly replaced blanket$2000peakdrawdown gate with account-floor/DLL rules. Earlier55monthly24monthwindows choose one;later61windows check only the frozen choice. No V/T/paper outcomes, no deployment.</p><p class="note">'+html.escape(r['scope'])+' '+html.escape(r['metric_limits'])+' Large trading drawdown alone is not a rule failure. No overnight sleeve or five-winning-days payout path is modeled, so this is not a full Fortress4X parity claim.</p><div class="scroll">'+pd.DataFrame(comparisons).to_html(index=False,border=0,float_format=lambda x:f'{x:,.2f}')+'</div><h2>Frozen choice</h2><pre>'+html.escape(json.dumps(r['configuration'],indent=2))+'</pre><h2>EarlierTRAIN top20</h2><div class="scroll">'+frame.head(20).to_html(index=False,border=0,float_format=lambda x:f'{x:,.3f}')+'</div><p><a href="../runs/funded_rule_bounds_v1/protocol.json">Frozen protocol</a> · <a href="../runs/funded_rule_bounds_v1/all_earlier_account_policies.csv">All145 policies</a> · <a href="../research/prop_firms/topstep_daily_static_verified_20261111.json">Verified published rules and sources</a> · <a href="'+stem+'.json">Full results</a></p></html>'
    (ROOT/'reports'/f'{stem}.html').write_text(page,encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true');parser.add_argument('--run',action='store_true');args=parser.parse_args()
    if args.freeze:freeze()
    elif args.run:main()
    else:parser.error('Choose --freeze or --run')

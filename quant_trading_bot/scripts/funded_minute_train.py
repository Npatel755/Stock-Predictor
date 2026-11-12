"""Frozen48-policy TRAIN-only joint minute/overnight research study."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil
import numpy as np
import pandas as pd
import stack_continuous_train as util
import funded_minute_prepare as prep
from funded_minute_core import replay

ROOT=util.ROOT;RUN=ROOT/'runs/funded_minute_research_v2'
RULES=ROOT/'research/prop_firms/topstep_daily_static_verified_20261111.json'
PARENT=ROOT/'runs/funded_rule_bounds_v1'
BENCH=dict(name='FORTRESS_STYLE_MINUTE_REFERENCE',keep=8500.,equal_risk=False,fraction=0.,night_always=False,payout_mode=0)
FIELDS=['trader_cash','gross_withdrawals','ending_cash','known_trading_pnl','economic_book_value','payouts','entries','floor_closed','DLL_sessions','inactivity_terminated','data_fault','trading_mark_drawdown','max_gross_micros','minimum_floor_room','open_entry_fees']


def freeze():
    RUN.mkdir(parents=True,exist_ok=True)
    if (RUN/'protocol.json').exists():raise RuntimeError('Frozen research exists')
    policy=json.loads((ROOT/'research/FUNDED_RESEARCH_POLICY.json').read_text());assert policy['strict_global_drawdown_required'] is False
    parent=json.loads((PARENT/'protocol.json').read_text());cells=[]
    for keep in (2000.,5000.,8500.):
        for equal in (False,True):
            for fraction in (.25,.5):
                for always in (False,True):
                    for mode in (0,1):
                        cells.append(dict(name=f'K{keep:g}_E{int(equal)}_F{fraction:g}_N{int(always)}_P{mode}',keep=keep,equal_risk=equal,fraction=fraction,night_always=always,payout_mode=mode))
    assert len(cells)==48
    files=[Path(__file__),Path(__file__).with_name('funded_minute_core.py'),Path(__file__).with_name('funded_minute_prepare.py'),
           ROOT/'tests/test_funded_minute_core.py',ROOT/'src/quant_futures/session_calendar.py',ROOT/'scripts/stack_continuous_train.py']
    code=RUN/'code';code.mkdir(exist_ok=True);hashes={}
    for f in files:hashes[str(f.relative_to(ROOT))]=util.sha(f);shutil.copyfile(f,code/f.name)
    datahash={str(p.relative_to(ROOT)):util.sha(p) for p in (prep.BASE,prep.NIGHT,prep.EVENTS,RULES,ROOT/'research/FUNDED_RESEARCH_POLICY.json')}
    spec=dict(run_id='funded_minute_research_v2',frozen_at=str(pd.Timestamp.now(tz='UTC')),candidates=cells,benchmark=BENCH,
        prescore_repair='v1 source metadata assertion failed before quote cache or any candidate score. Cached NIGHT tout contains safety exits; v2 uses uniform nextdate09:45 and full cashholidaycalendar guard for all entries. Same48policies, not48additionaltrials. v1 protocol/code retained.',
        cash_holiday_policy='No entries on known full UScashmarket holidays including GoodFriday, announced Sandy2012Oct29/30 and Bushfuneral2018Dec5. Conservative research guard, not futures hours. Exact specialclosure publication timestamps not archived; date-level prior announcement assumed.',
        source_hashes=hashes,data_hashes=datahash,training_sources=parent['training_sources'],
        hypothesis='Overnight opportunities and equal-stop-dollar allocation may address intraday-only inactivity and under-scaled early prices; proper intraday floor/DLL liquidation must precede any payout comparison.',
        signal_slots='Frozen1808base and539overnight virtual signal opportunities, unchanged source indicator generation. Reexecute no-trailing fixed ATRbrackets, fixedhold and early-close calendar at actual minute prices. Different exits change allocations/timing; not exact deployedFortress parity.',
        simulation='Joint same-direction sleeve positions; opposite-side same-instrument entries rejected. Historical signal-start occupancy filter uses only accepted positions known at entry; no6positionlookbacktruncation.20grossmicrocap,1%prior-minutevolumecap, miniproxy10:1. FixedATRstops/targets, night0.55% stop and09:45exit. Slotcash/multipliers/fees tracked at eventtime.',
        account='InitialXFAcash0,staticfloor-2000beforefirstpayout then0. DLL1000 liquidates and pauses only session. Intraday conservative joint worst-minute prices used when order unknown, plus market costs; gap triggers at actualopens. No loss clipping or globalpeakDDgate. Inactivity>30days treated as conservative termination assumption because publishedterms saymayclose; not guaranteed broker behavior.',
        source_limits='WholeminuteOHLC and simultaneous adverse crossasset ordering remain conservative approximations; exacttick/queue/latency and temporary risk changes unknown. Individualdashboard not inspected. Pre2019E-miniquotes are hypotheticalmicroeconomics, not actualmicromarketfills. Rawsourcecontractchangeswhileholding or quote gap>5minutes invalidates path.',
        calendars='CT17/NY18sessionroll via local calendar dates and UTCevents. No new orders in conservative14daypre-thirdFridayquarterlyrollblackout. Use known early-close rule dates; exclude entries afterflat. TRAIN-only highimpact scheduledcalendar caps newmicros at3 within+/-5minutes; existingpositions grandfathered. Calendar publicationlags notverified; no releasevalues used.',
        payouts='Each completed session may request daily250..1500 above max(keep,2000),or hybrid5winningday>=150priority up to min(8000,half_balance) before dailyfallback. Any request resetsbothwineligibility. Trader90%. Additionaltraderrestriction never withdrawmorethannetnewprofit since priorrequest. Retainedbookvalue isnotguaranteedpayout.',
        selection='Same55earlierTRAINmonthly24monthwindows withend<=2017; eachcandidatebase/stress. Require0floorclosed/datafaultcases, no more inactivityterminations than benchmark, positive economicvalue and>=5%highermeanvalue and >=benchmarkcash at BOTH costs. Rank lower ofbase/stress meanvalue, thenstresscash, thenname. Freezeonebeforecontrols/later; no alternate afterfailure.',
        controls='For sole frozen choice,20predetermined randomdirection vectors plusalways-long acrossallslots, reexecuting brackets and costs on earlierTRAIN. Require cost2choicebookvalue>95thpercentilerandom and>alwayslong. This is not selection-adjusted or an independent significance test. Failure rejectschoice; no substitute.',
        random_seeds=list(range(2026111100,2026111120)),
        confirmation='Only ifearlierchoice passesfixedcontrols, evaluate it unchanged on61laterTRAIN24monthwindows starting2017..2022. Samequalifyinggates vs benchmark. AllTRAINpreviouslyreused; no fresh unseen inference.',
        cost_stress='Fee0.50/side and marketadverse0.50point atbase; doubleboth forstress; targetlimits quartertick exact with1tickpenetration. Reexecution may alter fills/guards; full cashloss debited.',
        risk_sources=['https://help.topstep.com/en/articles/15520357-topstep-labs','https://help.topstep.com/en/articles/10490293-daily-loss-limit-in-the-trading-combine-and-express-funded-account','https://help.topstep.com/en/articles/13613539-risk-adjustments-high-risk-high-volatility','https://www.cmegroup.com/trading/equity-index/rolldates.html'],
        validation_accessed=False,test_accessed=False,forward_paper_accessed=False,automatic_holdout_stage=False,deployment_authorized=False)
    util.write(RUN/'protocol.json',spec);print('FROZEN48minuteaccountpolicies +reference;noV/T',flush=True)


def windows():
    t=pd.date_range('2010-07-01','2022-01-01',freq='MS');end=np.array([int((x+pd.DateOffset(months=24)).value) for x in t],np.int64)
    return t,t.as_unit('ns').asi8,end


def summary(a):
    m={f:float(a[:,i].mean()) for i,f in enumerate(FIELDS)}
    for f in ('floor_closed','inactivity_terminated','data_fault'):m[f+'_cases']=int(a[:,FIELDS.index(f)].sum())
    m['maximum_gross_micros']=int(a[:,12].max());m['worst_trading_mark_drawdown']=float(a[:,11].max());m['windows']=len(a)
    return m


def acceptable(m,b):
    return bool(all(m[k]['floor_closed_cases']==0 and m[k]['data_fault_cases']==0 and
        m[k]['inactivity_terminated_cases']<=b[k]['inactivity_terminated_cases'] and m[k]['economic_book_value']>0 and
        m[k]['economic_book_value']>=1.05*b[k]['economic_book_value'] and m[k]['trader_cash']>=b[k]['trader_cash'] for k in ('base','cost2')))


def score(market,c,indices,directions=None,save=None):
    t,start,end=windows();metrics={};raw={}
    sig=market['signals'].copy()
    if directions is not None:sig[:,3]=directions
    args=[market[k] for k in ('ts','trade_day','ohlc','contracts','capacity','news_limit','entry_allowed')]+[sig]
    for cost,label in ((1,'base'),(2,'cost2')):
        rows=[];ledgers=[]
        for wi in indices:
            row,logs=replay(*args,start[wi],end[wi],c['keep'],c['equal_risk'],c['fraction'],c['night_always'],c['payout_mode'],float(cost))
            expected=logs[:,7].sum()-row[14];np.testing.assert_allclose(row[3],expected,atol=1e-6,rtol=0)
            # Independent fill-price accounting, different from engine cash.
            if len(logs):
                inst=sig[logs[:,0].astype(int),2];mult=np.where(inst==0,2.,5.)
                net=logs[:,3]*logs[:,4]*(logs[:,6]-logs[:,5])*mult-logs[:,8]
                np.testing.assert_allclose(net,logs[:,7],atol=1e-7,rtol=0)
            rows.append(row)
            if save is not None:
                f=pd.DataFrame(logs,columns=['signal_id','entry_quote_index','exit_quote_index','side','quantity','entry_price','exit_price','net_pnl','fees','reason','cash_after_close'])
                f.insert(0,'window_start',str(t[wi].date()))
                if len(f):
                    f['entry_utc']=pd.to_datetime(market['ts'][f.entry_quote_index.astype(int)],utc=True)
                    f['exit_utc']=pd.to_datetime(market['ts'][f.exit_quote_index.astype(int)],utc=True)
                ledgers.append(f)
        a=np.asarray(rows);raw[label]=a;metrics[label]=summary(a)
        if save is not None:
            save.mkdir(parents=True,exist_ok=True);pd.concat(ledgers,ignore_index=True).to_csv(save/(label+'_trades.csv.gz'),index=False,compression='gzip')
            f=pd.DataFrame(a,columns=FIELDS);f.insert(0,'window_start',t[indices]);f.to_csv(save/(label+'_account_windows.csv'),index=False)
    return metrics,raw


def main():
    if (RUN/'results.json').exists():print('Completed frozen study preserved');return
    p=json.loads((RUN/'protocol.json').read_text())
    for rel,h in p['source_hashes'].items():assert util.sha(ROOT/rel)==h
    cache,slots=prep.prepare(RUN,p,util.sha,util.write);market={k:cache[k] for k in cache.files};cache.close()
    t,start,end=windows();earlier=np.flatnonzero(end<=int(pd.Timestamp('2017-01-01').value));later=np.flatnonzero(start>=int(pd.Timestamp('2017-01-01').value))
    bm,_=score(market,BENCH,earlier,save=RUN/'benchmark_earlier')
    results={};rows=[]
    for i,c in enumerate(p['candidates']):
        path=RUN/'checkpoints'/f"{c['name']}.json";path.parent.mkdir(exist_ok=True)
        if path.exists():m=json.loads(path.read_text())
        else:
            m,a=score(market,c,earlier);util.write(path,m);np.savez_compressed(path.with_suffix('.npz'),**a)
        results[c['name']]=m
        rows.append(dict(**c,qualified=acceptable(m,bm),base_cash=m['base']['trader_cash'],stress_cash=m['cost2']['trader_cash'],
            worst_cost_value=min(m[k]['economic_book_value'] for k in ('base','cost2')),base_value=m['base']['economic_book_value'],stress_value=m['cost2']['economic_book_value'],
            base_floor=m['base']['floor_closed_cases'],stress_floor=m['cost2']['floor_closed_cases'],base_data_fault=m['base']['data_fault_cases'],stress_data_fault=m['cost2']['data_fault_cases'],
            base_inactivity=m['base']['inactivity_terminated_cases'],stress_inactivity=m['cost2']['inactivity_terminated_cases']))
        print('EARLIER',i+1,'/48',c['name'],'qualified',rows[-1]['qualified'],flush=True)
    frame=pd.DataFrame(rows).sort_values(['qualified','worst_cost_value','stress_cash','name'],ascending=[False,False,False,True]);frame.to_csv(RUN/'all_earlier_minute_policies.csv',index=False)
    eligible=frame[frame.qualified];lookup={c['name']:c for c in p['candidates']};choice=lookup[eligible.iloc[0]['name']] if len(eligible) else None
    frozen=RUN/'frozen_earlier_choice.json';payload=dict(configuration=choice,earlier=results[choice['name']] if choice else None,eligible=len(eligible),
        protocol_sha256=util.sha(RUN/'protocol.json'),ranking_sha256=util.sha(RUN/'all_earlier_minute_policies.csv'),later_TRAIN_used_for_choice=False)
    if frozen.exists():assert json.loads(frozen.read_text())==payload
    else:util.write(frozen,payload)
    print('FROZEN CHOICE',json.dumps(choice),'eligible',len(eligible),flush=True)
    control_rows=[];null_pass=False
    if choice:
        chosen_early,_=score(market,choice,earlier,save=RUN/'frozen_choice_earlier')
        for seed in p['random_seeds']:
            target=RUN/'controls'/f'{seed}.json';target.parent.mkdir(exist_ok=True)
            if target.exists():cm=json.loads(target.read_text())
            else:
                directions=np.random.default_rng(seed).choice(np.array([-1.,1.]),size=len(market['signals']));cm,_=score(market,choice,earlier,directions);util.write(target,cm)
            control_rows.append(dict(seed=seed,value=cm['cost2']['economic_book_value'],cash=cm['cost2']['trader_cash']))
            print('TRAIN control',seed,flush=True)
        always,_=score(market,choice,earlier,np.ones(len(market['signals'])));util.write(RUN/'always_long_control.json',always)
        threshold=float(np.percentile([x['value'] for x in control_rows],95))
        null_pass=bool(chosen_early['cost2']['economic_book_value']>threshold and chosen_early['cost2']['economic_book_value']>always['cost2']['economic_book_value'])
    else:chosen_early=None;always=None;threshold=None
    pd.DataFrame(control_rows).to_csv(RUN/'random_direction_controls.csv',index=False)
    bm_later,_=score(market,BENCH,later,save=RUN/'benchmark_later');chosen_later=None
    if choice and null_pass:chosen_later,_=score(market,choice,later,save=RUN/'frozen_choice_later')
    accepted=bool(choice and null_pass and chosen_later and acceptable(chosen_later,bm_later))
    result=dict(status='TRAIN_ONLY_MINUTE_RESEARCH_CHALLENGER' if accepted else 'NO_QUALIFIED_REPLACEMENT',accepted=accepted,candidates=48,
        earlier_eligible=len(eligible),configuration=choice,benchmark_earlier=bm,choice_earlier=chosen_early,
        benchmark_later=bm_later,choice_later=chosen_later,random_controls_passed=null_pass,random_95percentile=threshold,
        always_long_control=always,control_warning='Fixedchoice controls only, not multiple-selectionadjusted significance. All earlier/later TRAINreused.',
        accounting='Actualminutequotes; full gap/adverse liquidation fills;DLLsoftsessionstop; no globalDDrejection. Economicbookvalue includes hypothetical remaining account excess, not guaranteed payout.',
        scope='Fortressstyle jointminute prototype with calendarrollblackout, virtualfrozen opportunities, opposite-side rejection and fixed20microcap; not exact deployedFortressparity. No live/paperchanges or full brokercertification.',
        validation_accessed=False,test_accessed=False,forward_paper_accessed=False,independent_confirmation=False,deployment_changed=False,
        protocol_sha256=util.sha(RUN/'protocol.json'),frozen_choice_sha256=util.sha(frozen),minute_data_sha256=util.sha(RUN/'minute_inputs.npz'))
    util.write(RUN/'results.json',result)
    if accepted:
        version=ROOT/'strategy_versions/gemini_triple_stack/v2.1.0-minute-research';version.mkdir(parents=True,exist_ok=True)
        util.write(version/'frozen_candidate.json',dict(result=result,deployed=False));shutil.copyfile(RUN/'protocol.json',version/'protocol.json');shutil.copytree(RUN/'code',version/'code',dirs_exist_ok=True)
    publish(result,frame)
    print('FINAL',json.dumps(dict(accepted=accepted,choice=choice,earlier_eligible=len(eligible),null_pass=null_pass,earlier=chosen_early,later=chosen_later)),flush=True)


def publish(r,frame):
    stem='FUNDED_MINUTE_RESEARCH_TRAIN';util.write(ROOT/'reports'/f'{stem}.json',r)
    rows=[]
    for period in ('earlier','later'):
        for model in ('benchmark','choice'):
            m=r.get(f'{model}_{period}')
            if m is None:continue
            for cost in ('base','cost2'):
                x=m[cost];rows.append(dict(Period=period,Policy=model,Costs=cost,Cash_received=x['trader_cash'],Book_value=x['economic_book_value'],Floor_closures=x['floor_closed_cases'],DLL_sessions=x['DLL_sessions'],Inactive_terminations=x['inactivity_terminated_cases'],Data_fault_cases=x['data_fault_cases'],Mark_DD=x['worst_trading_mark_drawdown']))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4.5))
    for ax,period in zip(axes,('earlier','later')):
        vals=[];labels=[]
        for model in ('benchmark','choice'):
            m=r.get(f'{model}_{period}')
            if m is not None:vals.append(m['cost2']['trader_cash']);labels.append(model)
        bars=ax.bar(labels,vals,color=['#5785be','#d3a44c'][:len(vals)]);ax.bar_label(bars,fmt='$%.0f');ax.set(title=period+' reusedTRAIN',ylabel='Mean24monthtradercash atstresscosts');ax.grid(axis='y',alpha=.2)
    fig.tight_layout();fig.savefig(ROOT/'reports'/f'{stem}.png',dpi=150);plt.close(fig)
    title='Funded minute replay: '+('TRAIN-only challenger' if r['accepted'] else 'no qualifying replacement')
    text='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title><style>body{font:16px/1.6 system-ui;max-width:1400px;margin:32px auto;padding:0 24px;background:#111820;color:#e9edf2}a{color:#96d8ff}table{border-collapse:collapse;font-size:14px}td,th{padding:9px;border-bottom:1px solid #456}pre{white-space:pre-wrap}.scroll{overflow:auto}.note{padding:18px;background:#382d22}img{max-width:100%}</style><h1>'+title+'</h1><p>48frozen account/sleeve policies. Joint minute replay restores539overnight opportunities alongside1808base slots; each gets fresh stops/targets, scheduled exits and actualminute gap/forcedfills. Earlier TRAIN selects one; controls and laterTRAIN neverchoose a replacement. No V/T/forwardpaper outcomes or deployment.</p><p class="note">'+html.escape(r['scope'])+' '+html.escape(r['accounting'])+' Simultaneous crossasset adverse quotes and adverse-before-target are conservative OHLC assumptions, not exacttick/brokerliquidationchronology. Conservative inactivitytermination after30days is an assumption for the publishedmayclose clause. Current ruleterms applied retrospectively. Pre2019E-miniproxies do not establish real micromarketliquidity.</p><div class="scroll">'+pd.DataFrame(rows).to_html(index=False,border=0,float_format=lambda x:f'{x:,.2f}')+'</div><img src="'+stem+'.png" alt="Cash comparison"><h2>Frozen choice</h2><pre>'+html.escape(json.dumps(r['configuration'],indent=2))+'</pre><h2>EarlierTRAIN top20</h2><div class="scroll">'+frame.head(20).to_html(index=False,border=0,float_format=lambda x:f'{x:,.3f}')+'</div><p><a href="../runs/funded_minute_research_v1/protocol.json">Frozen protocol</a> · <a href="../runs/funded_minute_research_v1/all_earlier_minute_policies.csv">All48policies</a> · <a href="../runs/funded_minute_research_v1/minute_identity.json">Market and calendar provenance</a> · <a href="'+stem+'.json">Full results</a></p></html>'
    (ROOT/'reports'/f'{stem}.html').write_text(text,encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true');parser.add_argument('--run',action='store_true');args=parser.parse_args()
    if args.freeze:freeze()
    elif args.run:main()
    else:parser.error('Choose --freeze or --run')

"""Post-run accounting/execution audit; never selects another policy."""
import hashlib
import html
import json
from pathlib import Path
import numpy as np
import pandas as pd
import funded_minute_train as study

ROOT=study.ROOT;RUN=study.RUN


def publish_audited(r,frame,audit):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    records=[]
    for period in ('earlier','later'):
        for cost in ('base','cost2'):
            m=r['benchmark_'+period][cost]
            records.append(dict(period=period,cost=cost,windows=m['windows'],data_fault=m['data_fault_cases'],
                inactive=m['inactivity_terminated_cases'],floor_closed=m['floor_closed_cases'],
                completed=m['windows']-m['data_fault_cases']-m['inactivity_terminated_cases']-m['floor_closed_cases']))
    reference=pd.DataFrame(records)
    counts=[len(frame),int(((frame.base_floor==0)&(frame.stress_floor==0)).sum()),
        int(((frame.base_data_fault==0)&(frame.stress_data_fault==0)).sum()),int(frame.qualified.sum())]
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    axes[0].barh(['Policies tested','No floor closure at both costs','No data fault at both costs','All frozen gates passed'],counts,color=['#5785be','#5785be','#c88736','#63a587'])
    axes[0].invert_yaxis();axes[0].set_xlim(0,54);axes[0].set_title('Earlier TRAIN screen (48 policies)')
    for i,value in enumerate(counts):axes[0].text(value+.5,i,str(value),va='center')
    bottom=np.zeros(4)
    for field,color,label in [('completed','#63a587','Completed'),('inactive','#c88736','Inactivity termination'),('data_fault','#b55454','Missing-data stop'),('floor_closed','#7b5d98','Floor closure')]:
        axes[1].bar(np.arange(4),reference[field],bottom=bottom,color=color,label=label);bottom+=reference[field].to_numpy()
    axes[1].set_xticks(np.arange(4),['Earlier\nbase','Earlier\nstress','Later\nbase','Later\nstress']);axes[1].set_title('Reference account paths');axes[1].set_ylabel('24-month training windows');axes[1].legend(fontsize=8)
    fig.suptitle('No qualifying replacement; incomplete paths prevent payout claims');fig.tight_layout()
    fig.savefig(ROOT/'reports/FUNDED_MINUTE_RESEARCH_TRAIN.png',dpi=150);plt.close(fig)
    summary=pd.DataFrame([{'Stage':'Earlier TRAIN','Windows':55,'Window starts':'2010-07 to 2015-01'},
        {'Stage':'Later TRAIN reference only','Windows':61,'Window starts':'2017-01 to 2022-01'}])
    columns={'name':'Policy','base_cash':'Base partial cash','stress_cash':'Stress partial cash',
        'base_data_fault':'Base data faults','stress_data_fault':'Stress data faults','base_inactivity':'Base inactivity','stress_inactivity':'Stress inactivity','qualified':'Qualifies'}
    shown=frame[list(columns)].rename(columns=columns)
    body='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Funded research: no qualifying improvement</title><style>body{font:16px/1.6 system-ui;max-width:1300px;margin:32px auto;padding:0 24px;background:#111820;color:#e9edf2}a{color:#96d8ff}table{border-collapse:collapse;font-size:14px}td,th{padding:9px;border-bottom:1px solid #456;text-align:right}td:first-child,th:first-child{text-align:left}.scroll{overflow:auto}.note{padding:18px;background:#382d22}img{max-width:100%}code{overflow-wrap:anywhere}</style></head><body><h1>No qualifying improvement found</h1><p>Completed 48 frozen account and sleeve policies using training data only. None passed the predefined gates. The deployed Fortress settings remain unchanged.</p><p class="note"><strong>These are incomplete research paths, not payout forecasts.</strong> Missing source prices and conservative inactivity termination prevent a reliable full-horizon comparison. Cash shown below is partial trader cash received before a stop; it is not net trading profit or evidence of a viable policy.</p><h2>What changed in the research engine</h2><p>The joint minute replay includes 1,808 intraday and 539 overnight signal opportunities, raw historical prices, full gap losses, protective brackets and session-ending daily-loss liquidations. It resumes after a daily-loss stop in the next session and closes permanently only at the static account floor. The former blanket $2,000 drawdown gate is removed. A 20-micro cap, conservative news-opening limits, prior-minute volume capacity and known-calendar entry guards apply. Those extra guards are research assumptions, not verified individual account terms.</p><p>This is a Fortress-style prototype, not execution parity with the deployed card: routing, calendar guards and exits differ. It cannot establish that the deployed champion earned or lost these amounts.</p><h2>Frozen experiment</h2>'''
    body+=summary.to_html(index=False,border=0)
    body+='''<p>48 configurations vary retained balance ($2,000/$5,000/$8,500), fixed versus risk-based contracts, risk fraction (25%/50%), overnight activation and daily versus hybrid payout paths. Rank only on earlier training windows; require no floor closures or data faults, positive economic value, at least 5% more value and no less trader cash than the reference at both base and doubled costs. No policy qualified, so no candidate was selected and the planned controls were not run. These training periods have been reused historically; they are not independent unseen evidence.</p>'''
    body+='<img src="FUNDED_MINUTE_RESEARCH_TRAIN.png" alt="Policy screen and incomplete reference paths"><h2>Reference path completion</h2>'+reference.rename(columns={'data_fault':'Missing data','inactive':'Inactivity','floor_closed':'Floor closure','completed':'Completed'}).to_html(index=False,border=0)
    body+='<h2>Audit</h2><p>22 synthetic tests passed. All 48 earlier summary and raw outcome arrays reconcile; they represent '+str(audit['distinct_prefix_outcome_arrays'])+' distinct outcome arrays. Independent entry, stop, target, fee and trade-accounting formulas checked '+f"{audit['independent_trade_accounting_and_fill_checks']:,}"+' closed reference trades. Instrumented source parity is a diagnostic check, not independent simulator validation.</p><p>A representative stop occurs at 2014-07-23 05:26 UTC: the held NQ proxy has no quote since 05:20 while ES still has prices. The replay stops instead of inventing a liquidation fill. Inactivity closure is a conservative research treatment of an account clause saying it may close; it is not asserted as certain broker behavior.</p>'
    body+='<p><strong>Audit scope deviation:</strong> '+html.escape(audit['postrun_audit_deviation'])+'</p>'
    body+='<h2>All 48 earlier TRAIN policies</h2><div class="scroll">'+shown.to_html(index=False,border=0,float_format=lambda x:f'{x:,.2f}')+'</div>'
    body+='''<h2>Limits and next useful work</h2><p>Minute OHLC assumes adverse movement before targets and simultaneous adverse prices across instruments. Exact tick sequencing, queues, execution latency, temporary restrictions and the individual account dashboard are unverified. Pre-2019 E-mini prices support hypothetical micro economics, not actual micro liquidity. Fixed schedules replace cached realized overnight safety exits; known cash-market holidays are excluded. Calendar announcement-time precision is assumed.</p><p>The useful next step is to establish the deployed card's exact streaming execution parity and obtain trustworthy quotes for gaps before another funded comparison. Low-cost signal research must remain training-only. Do not relax the data gates or choose parameters from validation, test or forward-paper results.</p><p>Published account references: <a href="https://help.topstep.com/en/articles/15520357-topstep-labs">Daily Payouts+ terms</a>, <a href="https://help.topstep.com/en/articles/10490293-daily-loss-limit-in-the-trading-combine-and-express-funded-account">Daily-loss rules</a>, <a href="https://help.topstep.com/en/articles/13613539-risk-adjustments-high-risk-high-volatility">News risk adjustments</a>. Exceptional closure reference: <a href="https://www.cmegroup.com/media-room/press-releases/2012/10/29/cme_group_to_reopenusequityindexandinterestratecomplexestonight.html">CME Sandy announcement before the overnight reopening</a>.</p><p><a href="../runs/funded_minute_research_v2/protocol.json">Frozen protocol</a> · <a href="../runs/funded_minute_research_v2/all_earlier_minute_policies.csv">All policy results CSV</a> · <a href="../runs/funded_minute_research_v2/minute_identity.json">Data provenance</a> · <a href="FUNDED_MINUTE_RESEARCH_TRAIN_audit.json">Audit</a> · <a href="FUNDED_MINUTE_RESEARCH_TRAIN.json">Full results</a></p><p>Validation, test and forward-paper outcomes were not accessed. No deployment changed.</p></body></html>'''
    (ROOT/'reports/FUNDED_MINUTE_RESEARCH_TRAIN.html').write_text(body,encoding='utf-8')


def diagnostic_engine():
    source=(RUN/'code/funded_minute_core.py').read_text(encoding='utf-8')
    original=source.splitlines();lines=[]
    for number,line in enumerate(original,1):
        line=line.replace('@njit(cache=True)','@njit(cache=False)')
        line=line.replace('data_fault=1',f'data_fault=1;fault_line={number};fault_i=i')
        if 'slots=8;n=len(ts)' in line:line+=';fault_line=0;fault_i=-1'
        if 'return metrics,logs[:nlog].copy()' in line:
            line=line.replace('return metrics,','return np.concatenate((metrics,np.array([float(fault_line),float(fault_i)]))),')
        lines.append(line)
    namespace={};exec(compile('\n'.join(lines),'audit_instrumented_frozen_core','exec'),namespace)
    return namespace['replay'],original


def main():
    p=json.loads((RUN/'protocol.json').read_text());r=json.loads((RUN/'results.json').read_text())
    assert r['accepted'] is False and r['configuration'] is None
    for rel,h in p['source_hashes'].items():assert study.util.sha(ROOT/rel)==h
    for rel,h in p['data_hashes'].items():assert study.util.sha(ROOT/rel)==h
    for d in p['training_sources'].values():assert d['role']=='train' and study.util.sha(d['path'])==d['sha256']
    assert study.util.sha(RUN/'minute_inputs.npz')==r['minute_data_sha256']
    market=dict(np.load(RUN/'minute_inputs.npz'));t,start,end=study.windows()
    earlier=np.flatnonzero(end<=int(pd.Timestamp('2017-01-01').value))
    later=np.flatnonzero(start>=int(pd.Timestamp('2017-01-01').value))
    frame=pd.read_csv(RUN/'all_earlier_minute_policies.csv')
    assert len(frame)==48 and not frame.qualified.any()
    frozen=json.loads((RUN/'frozen_earlier_choice.json').read_text());assert frozen['configuration'] is None
    assert frozen['ranking_sha256']==study.util.sha(RUN/'all_earlier_minute_policies.csv')
    signatures=set();prefix_checks=0
    for c in p['candidates']:
        m,a=study.score(market,c,earlier);saved=json.loads((RUN/'checkpoints'/f"{c['name']}.json").read_text())
        for k in ('base','cost2'):
            for field in m[k]:np.testing.assert_allclose(m[k][field],saved[k][field],atol=1e-7,rtol=0)
            np.testing.assert_allclose(a[k],np.load(RUN/'checkpoints'/f"{c['name']}.npz")[k],atol=1e-7,rtol=0)
        assert not study.acceptable(m,r['benchmark_earlier']);prefix_checks+=1
        signatures.add(hashlib.sha256(a['base'].tobytes()+a['cost2'].tobytes()).hexdigest())
    execution_checks=0
    for period,indices in (('earlier',earlier),('later',later)):
        m,a=study.score(market,study.BENCH,indices)
        for cost,label in ((1,'base'),(2,'cost2')):
            for field in m[label]:np.testing.assert_allclose(m[label][field],r['benchmark_'+period][label][field],atol=1e-7,rtol=0)
            logs=pd.read_csv(RUN/('benchmark_'+period)/(label+'_trades.csv.gz'))
            sig=market['signals'];idx=logs.signal_id.to_numpy(int);ei=logs.entry_quote_index.to_numpy(int);xi=logs.exit_quote_index.to_numpy(int)
            asset=sig[idx,2].astype(int);side=logs.side.to_numpy();qty=logs.quantity.to_numpy();mult=np.where(asset==0,2.,5.)
            opening=market['ohlc'][asset,0,ei];raw=opening+side*.5*cost
            entry=np.where(side>0,np.ceil(raw*4-1e-9),np.floor(raw*4+1e-9))/4
            np.testing.assert_allclose(entry,logs.entry_price,atol=1e-7,rtol=0)
            np.testing.assert_allclose(logs.fees,qty*cost,atol=1e-7,rtol=0)
            assert np.all(qty<=market['capacity'][asset,ei]) and np.all(qty>=1)
            assert np.all(market['entry_allowed'][ei]) and np.all(ei<=xi)
            for price in (logs.entry_price,logs.exit_price):np.testing.assert_allclose(price*4,np.round(price*4),atol=1e-7,rtol=0)
            net=side*qty*(logs.exit_price-entry)*mult-logs.fees
            np.testing.assert_allclose(net,logs.net_pnl,atol=1e-7,rtol=0)
            scheduled=logs.reason.to_numpy()==2
            assert np.all(market['ts'][xi[scheduled]]>=sig[idx[scheduled],6])
            # Check stops and targets using raw quotes and frozen entry brackets.
            dist=np.where(sig[idx,8]>0,opening*.0055+.5*cost,sig[idx,4]);stop=entry-side*dist
            exopen=market['ohlc'][asset,0,xi];high=market['ohlc'][asset,1,xi];low=market['ohlc'][asset,2,xi]
            hit=np.where(side>0,low<=stop,high>=stop)
            protective=logs.reason.to_numpy()==3
            assert np.all(hit[protective])
            ref=np.where(side>0,np.minimum(exopen,stop),np.maximum(exopen,stop));rawexit=ref-side*.5*cost
            expected=np.where(side>0,np.floor(rawexit*4+1e-9),np.ceil(rawexit*4-1e-9))/4
            np.testing.assert_allclose(expected[protective],logs.exit_price.to_numpy()[protective],atol=1e-7,rtol=0)
            target=np.round((entry+side*dist*sig[idx,5])*4)/4;targeted=logs.reason.to_numpy()==4
            assert np.all(~hit[targeted]) and np.all(sig[idx[targeted],5]>0)
            assert np.all(np.where(side>0,high>=target+.25,low<=target-.25)[targeted])
            np.testing.assert_allclose(target[targeted],logs.exit_price.to_numpy()[targeted],atol=1e-7,rtol=0)
            execution_checks+=len(logs)
    engine,lines=diagnostic_engine();args=[market[k] for k in ('ts','trade_day','ohlc','contracts','capacity','news_limit','entry_allowed','signals')]
    failures=[];diagnostic_parity=0;cases=[]
    # Instrument the frozen source only to locate stops; never modify market inputs or fills.
    for c in (study.BENCH,p['candidates'][0]):
        indices=list(earlier[[0,len(earlier)//2,-1]])
        if c==study.BENCH:indices+=list(later[[0,-1]])
        _,raw=study.score(market,c,earlier)
        fault=np.flatnonzero(raw['base'][:,10]>0)
        if len(fault):indices.append(earlier[fault[0]])
        for wi in sorted(set(indices)):
            arguments=(*args,start[wi],end[wi],c['keep'],c['equal_risk'],c['fraction'],c['night_always'],c['payout_mode'],1.)
            normal,log=study.replay(*arguments);diag,dlog=engine(*arguments)
            np.testing.assert_allclose(normal,diag[:15],atol=1e-7,rtol=0);np.testing.assert_allclose(log,dlog,atol=1e-7,rtol=0);diagnostic_parity+=1
            if diag[10]:
                line=int(diag[-2]);i=int(diag[-1]);asset_candidates=[]
                for asset in (0,1):
                    valid=np.flatnonzero(np.isfinite(market['ohlc'][asset,0,:i+1]));last=valid[-1] if len(valid) else -1
                    asset_candidates.append(dict(asset=asset,last_quote_utc=str(pd.Timestamp(market['ts'][last],tz='UTC')) if last>=0 else None,quote_age_minutes=float((market['ts'][i]-market['ts'][last])/60e9) if last>=0 else None))
                failures.append(dict(policy=c['name'],window_start=str(t[wi].date()),at_utc=str(pd.Timestamp(market['ts'][i],tz='UTC')),frozen_line=line,condition=lines[line-1].strip(),quote_context=asset_candidates))
    assert not (RUN/'frozen_choice_later').exists() and not (RUN/'controls').exists()
    audit=dict(passed=True,all48prefix_metrics_and_raw_arrays_reconciled=True,distinct_prefix_outcome_arrays=len(signatures),
        benchmark_period_cost_summaries_reconciled=4,independent_trade_accounting_and_fill_checks=execution_checks,
        instrumented_frozen_engine_parity_cases=diagnostic_parity,synthetic_tests=22,data_fault_samples=failures,
        qualifying_replacement=False,zero_qualifiers=True,no_candidate_selected_or_controlled=True,
        postrun_audit_deviation='First audit accidentally replayed first registered candidate at two laterTRAIN diagnostic starts (2017Jan,2022Jan) after all48 rejected. No alternative chosen, no settings changed, no validation/test accessed. LaterTRAIN not entirely sealed for that rejected policy; these two cases are not confirmation evidence. Corrected audit limits alternate diagnostic cases to earlierTRAIN.',
        warning='Accounting audit passed; research outcomes fail. Partial values on data-fault/inactivity paths are NOT credible complete24monthpayout forecasts. Diagnostic instrumentation is sameengine parity, not independentenginevalidation.',
        validation_accessed=False,test_accessed=False,forward_paper_accessed=False,deployment_changed=False)
    study.util.write(RUN/'postrun_audit.json',audit);study.util.write(ROOT/'reports/FUNDED_MINUTE_RESEARCH_TRAIN_audit.json',audit)
    # Report-only publication; frozen research source snapshots untouched.
    publish_audited(r,frame,audit);report=ROOT/'reports/FUNDED_MINUTE_RESEARCH_TRAIN.html'
    study.util.write(RUN/'publication_verification.json',dict(html_sha256=study.util.sha(report),png_sha256=study.util.sha(ROOT/'reports/FUNDED_MINUTE_RESEARCH_TRAIN.png'),audit_script_sha256=study.util.sha(Path(__file__)),source_snapshots_unchanged=True))
    print(json.dumps(audit,indent=2))


if __name__=='__main__':main()

"""Bounded continuation of Gemini's exact stack; TRAIN-only selection/report.

One winner is frozen on earlier TRAIN before later TRAIN is evaluated. The
legacy result is a reproduction audit only, not evidence of safe account rules.
"""
import hashlib
import html
import json
from pathlib import Path
import shutil
import numpy as np
import pandas as pd
from gemini_stack_account_core import replay,summary,independent_reference

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/gemini_stack_continuation_v1'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,default=str)+'\n',encoding='utf-8')
def daynum(value):return int(pd.Timestamp(value).value//86400000000000)


def windows(start='2010-07-01',stop='2022-01-01'):
    t=pd.date_range(start,stop,freq='MS')
    return t,np.array([daynum(x) for x in t]),np.array([daynum(x+pd.DateOffset(months=24)) for x in t]),np.array([daynum(x+pd.DateOffset(months=12)) for x in t])


class Study:
    def __init__(self,mode):
        self.meta=json.loads((RUN/mode/'complete.json').read_text());p=RUN/mode/'tables.npz'
        if sha(p)!=self.meta['tables_sha256']:raise ValueError('Frozen table hash changed')
        self.data=np.load(p);self.mode=mode
        self.clock=self.data['dates'];self.names=self.meta['books']

    def arrays(self,c,scenario):
        si=self.meta['scenarios'].index(scenario)
        ids=[self.names.index(x) for x in ('base','both',c['book'])]
        return self.data['net'][ids,si],self.data['risk'][ids,si]

    def score(self,c,indices=None,verify=False):
        t,starts,ends,yearends=windows()
        if indices is not None:t,starts,ends,yearends=t[indices],starts[indices],ends[indices],yearends[indices]
        result={};raw={};checks=0
        for kind in ('S0','S3','S4'):
            net,risk=self.arrays(c,kind)
            clock=self.clock
            if self.mode=='legacy':
                # Exact original base-only calendar, including missing whole
                # added-sleeve days. Preserved for reproduction ONLY. The new
                # causal study deliberately uses the full portfolio calendar.
                mask=np.load(RUN/'legacy/exact_base_calendar_masks.npz')[kind]
                net,risk,clock=net[:,:,:,mask],risk[:,:,mask],clock[mask]
            rows=replay(net,risk,clock,starts,ends,yearends,c['K'],c['gate1'],c['gate2'],c['max_p4'])
            np.testing.assert_allclose(rows[:,0]+rows[:,7],rows[:,8],atol=1e-6,rtol=0)
            if verify:
                for i in range(len(t)):
                    ref=independent_reference(net,risk,clock,starts[i],ends[i],yearends[i],c['K'],c['gate1'],c['gate2'],c['max_p4'])
                    np.testing.assert_allclose(rows[i],ref,atol=1e-6,rtol=0);checks+=1
            result[kind]=summary(rows);raw[kind]=rows
        result['independent_path_checks']=checks
        return result,raw,t


def gates(candidate,baseline):
    return bool(candidate['S3']['conservative_stoprisk_flag_fraction']<=.05 and candidate['S4']['conservative_stoprisk_flag_fraction']<=.095
        and candidate['S0']['near_miss_fraction']<=baseline['S0']['near_miss_fraction']
        and all(candidate[k]['closed_fraction']<=baseline[k]['closed_fraction']+.005 for k in ('S0','S3','S4')))


def save_paths(folder,raw,t):
    folder.mkdir(parents=True,exist_ok=True)
    columns=['withdrawn','closed','stoprisk_flag','near_miss','first_days','year1_payouts','year1_withdrawn','ending_balance','trading_pnl','payouts']
    for k,a in raw.items():
        frame=pd.DataFrame(a,columns=columns);frame.insert(0,'start',t);frame.to_csv(folder/(k+'_24month_windows.csv'),index=False)


def main():
    if (RUN/'results.json').exists():print('Completed result preserved;no repeat.');return
    protocol=json.loads((RUN/'protocol.json').read_text())
    for name,h in protocol['source_hashes'].items():
        if sha(ROOT/'scripts'/name)!=h:raise ValueError('Original source changed:'+name)
    for mode in ('legacy','causal'):
        if not (RUN/mode/'complete.json').exists():raise RuntimeError('Both frozen TRAIN preparations required')
    configs=protocol['candidates'];baseline_cfg=configs[0]
    code=RUN/'code';code.mkdir(exist_ok=True)
    for name in [*protocol['source_hashes'],'gemini_stack_account_core.py',Path(__file__).name]:shutil.copyfile(ROOT/'scripts'/name,code/name)
    # Exact legacy comparison against the original function's saved results.
    legacy=Study('legacy');legacy_metrics,legacy_raw,legacy_t=legacy.score(baseline_cfg,verify=True)
    saved=json.loads((RUN/'legacy/original_gemini_reproduction.json').read_text())
    legacy_checks={}
    for kind in ('S0','S3','S4'):
        m=legacy_metrics[kind];old=saved[kind]
        for field,original,decimals in [('mean_withdrawals','usd',0),('closed_fraction','closed',3),('conservative_stoprisk_flag_fraction','cons',3),('near_miss_fraction','near',3)]:
            assert round(m[field],decimals)==old[original],(kind,field,m[field],old[original])
        legacy_checks[kind]=True
    save_paths(RUN/'legacy/reconciled_paths',legacy_raw,legacy_t)
    print('LEGACY EXACT FRACTIONS',json.dumps(legacy_metrics),flush=True)
    study=Study('causal');baseline_all,base_raw,all_t=study.score(baseline_cfg,verify=True)
    save_paths(RUN/'baseline_causal_paths',base_raw,all_t)
    original_baseline=dict(name='Gemini triple stack',configuration=baseline_cfg,claimed_24month_mean_withdrawals=52016.,
        reproduced_legacy_metrics=legacy_metrics,corrected_causal_baseline=baseline_all,protocol_sha256=sha(RUN/'protocol.json'),
        legacy_warning='Oldrouterand2019hole. S3flag7/139=5.03597%,rounded5.0usedinoriginalgates. Thisfailsstrict5%limit.',
        live_deployed=False,external_confirmation=False)
    archive=ROOT/'strategy_versions/gemini_triple_stack/v1.0.0-research';archive.mkdir(parents=True,exist_ok=True)
    if not (archive/'baseline.json').exists():write(archive/'baseline.json',original_baseline)
    # Proper chronology for24monthwindows: purge any window crossing2017.
    earlier=np.array([x+pd.DateOffset(months=24)<=pd.Timestamp('2017-01-01') for x in all_t]);later=all_t>=pd.Timestamp('2017-01-01')
    baseline_discovery,_,_=study.score(baseline_cfg,earlier)
    rows=[];results={}
    for c in configs:
        m,_,_=study.score(c,earlier);gate=gates(m,baseline_discovery)
        results[c['name']]=m
        row=dict(name=c['name'],book=c['book'],K=c['K'],gate=c['gate1'],risk_gate=gate,mean_withdrawals=m['S0']['mean_withdrawals'],
            S0closed=m['S0']['closed_fraction'],S0near=m['S0']['near_miss_fraction'],S3risk=m['S3']['conservative_stoprisk_flag_fraction'],S4risk=m['S4']['conservative_stoprisk_flag_fraction'])
        rows.append(row);print('EARLIER TRAIN',json.dumps(row),flush=True)
    pd.DataFrame(rows).to_csv(RUN/'all_earlier_training_candidates.csv',index=False)
    eligible=[(i,r) for i,r in enumerate(rows) if r['risk_gate']]
    if eligible:choice_i=max(eligible,key=lambda pair:(pair[1]['mean_withdrawals'],-pair[1]['S3risk'],-pair[0]))[0]
    else:choice_i=0
    choice=configs[choice_i]
    freeze=dict(configuration=choice,selection='EarlierTRAINonly,purged24monthwindows',discovery=results[choice['name']],
        eligible_cells=len(eligible),selection_failed_no_eligible=not bool(eligible),protocol_sha256=sha(RUN/'protocol.json'),
        discovery_csv_sha256=sha(RUN/'all_earlier_training_candidates.csv'),later_training_accessed_for_choice=False)
    with (RUN/'frozen_earlier_train_choice.json').open('x',encoding='utf-8') as stream:json.dump(freeze,stream,indent=2)
    print('FROZEN CHOICE',choice['name'],'eligible',len(eligible),flush=True)
    baseline_later,_,_=study.score(baseline_cfg,later)
    chosen_later,chosen_raw,chosen_t=study.score(choice,later,verify=True)
    save_paths(RUN/'frozen_choice_later_paths',chosen_raw,chosen_t)
    candidate_discovery=results[choice['name']]
    lift_early=candidate_discovery['S0']['mean_withdrawals']/baseline_discovery['S0']['mean_withdrawals']-1
    lift_later=chosen_later['S0']['mean_withdrawals']/baseline_later['S0']['mean_withdrawals']-1
    accepted=bool(choice_i!=0 and len(eligible)>0 and lift_early>=.05 and lift_later>=.05 and gates(candidate_discovery,baseline_discovery) and gates(chosen_later,baseline_later))
    result=dict(legacy_original=original_baseline,causal_full_training_baseline=baseline_all,
        discovery=dict(baseline=baseline_discovery,frozen_choice=candidate_discovery,lift_fraction=lift_early,eligible_cells=len(eligible)),
        frozen_configuration=choice,confirmation=dict(baseline=baseline_later,frozen_choice=chosen_later,lift_fraction=lift_later,risk_gate=gates(chosen_later,baseline_later)),
        candidates=len(configs),verified_training_improvement=accepted,classification='TRAIN_ONLY_RESEARCH_CHALLENGER' if accepted else 'NO_QUALIFIED_IMPROVEMENT',
        model_warning='CausalroutingandTRAINgapfillarecorrected,butaccountusesdailyP&Lclippingandlargest-stop-riskproxies,notexactintrabarDLL/floorreplay. Withdrawalsarehypotheticalandpayouteligibilityrulesunverified. RepeatedTRAINoptimizationandnormalizedpricessignificantlylimitclaims.',
        validation_accessed=False,test_accessed=False,deployment_changed=False,independent_unseen_confirmation=False)
    write(RUN/'results.json',result);write(ROOT/'reports/GEMINI_STACK_CONTINUATION_TRAIN.json',result)
    verification=dict(passed=True,legacy_reproduced=legacy_checks,legacy_path_reference_checks=legacy_metrics['independent_path_checks'],
        baseline_causal_path_reference_checks=baseline_all['independent_path_checks'],frozen_choice_reference_checks=chosen_later['independent_path_checks'],
        withdrawal_balance_conservation=True,earlier_train_only_selection=True,latertrain_not_used_to_replace_choice=True,
        exact_not_rounded_gates=True,validation_accessed=False,test_accessed=False,source_hashes_match=True,production_certification=False)
    write(ROOT/'reports/GEMINI_STACK_CONTINUATION_TRAIN_verification.json',verification)
    if accepted:
        version=ROOT/'strategy_versions/gemini_triple_stack/v1.1.0-train-challenger';version.mkdir(parents=True,exist_ok=True)
        write(version/'frozen_candidate.json',dict(configuration=choice,result=result,deployed=False))
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(12,4.8))
    for ax,period in zip(axes,('discovery','confirmation')):
        s=result[period];values=[s['baseline']['S0']['mean_withdrawals'],s['frozen_choice']['S0']['mean_withdrawals']]
        bars=ax.bar(['Causaltriplebaseline','FrozenTRAINchoice'],values,color=['#5187c2','#dfaa4a']);ax.bar_label(bars,fmt='$%.0f')
        ax.set(title='EarlierTRAINdiscovery' if period=='discovery' else 'LaterTRAINconfirmation',ylabel='Mean24monthscenario withdrawals($)');ax.set_ylim(0,max(values)*1.2);ax.grid(axis='y',alpha=.2)
    fig.suptitle('Gemini stack continuation: '+('traininggatepass' if accepted else 'noqualifyingimprovement'))
    fig.tight_layout();fig.savefig(ROOT/'reports/GEMINI_STACK_CONTINUATION_TRAIN.png',dpi=150);plt.close(fig)
    table=[]
    for period in ('discovery','confirmation'):
        for label,m in [('baseline',result[period]['baseline']),('choice',result[period]['frozen_choice'])]:
            for scenario in ('S0','S3','S4'):
                x=m[scenario];table.append(dict(Period=period,Model=label,Scenario=scenario,Starts=x['windows'],Mean_withdrawals=x['mean_withdrawals'],Closed_pct=100*x['closed_fraction'],Stoprisk_flag_pct=100*x['conservative_stoprisk_flag_fraction']))
    title='Gemini triple-stack continuation: '+('TRAIN-onlychallenger' if accepted else 'noqualifyingreplacement')
    page='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title><style>body{font:16px/1.65 system-ui;max-width:1300px;padding:32px;margin:auto;background:#111820;color:#e9edf2}a{color:#91d7ff}table{border-collapse:collapse;font-size:14px}td,th{padding:10px;border-bottom:1px solid #456}img{width:100%}.scroll{overflow:auto}pre{white-space:pre-wrap}.note{padding:20px;background:#352b1a}</style><h1>'+title+'</h1><p class="note">The screenshot\'s$52,016was exactly reproduced in the legacy model. It is mean simulated24monthWITHDRAWALS,notnetprofitandnotevaluationpassprofit. Its S3gate passedonlyafter rounding7/139flags(5.03597%)to5.0%;it failsanexact5%limit. The original entry-label router and2019TRAINdatahole were preserved onlyforreproduction. Theyarecorrectedfornewselection.</p><p>Resumed31frozen gate/sleevecells,includingthependingquad-stackandpenta-stackadditions. Newselectionusescausalentry-timepriorityroutingandfilledTRAIN2019splice,withsameeconomicmodelandpayoutassumptions. OnechoiceisfrozenonearlierTRAINbeforelaterTRAINconfirmation. Noexternalvalidation/test,paperoutcomes,orremoteAPIcalls;nodeploymentchanges.</p><img src="GEMINI_STACK_CONTINUATION_TRAIN.png" alt="EarlierTRAIN andlaterTRAIN payouts"><div class="scroll">'+pd.DataFrame(table).to_html(index=False,border=0,float_format=lambda x:f'{x:,.2f}')+'</div><h2>Frozenchoice</h2><pre>'+html.escape(json.dumps(choice,indent=2))+'</pre><h2>Measurementlimits</h2><p>'+result['model_warning']+'</p><p>Hereconsmeansamodelconservativelargest-stop-riskflag,notverifiedaccountclosure. Closurechecksuseendofdaybalance;DLLclipsdailyP&Lat−$1,000anddoesnotreconstructafloor-stopfill. Astopriskflagcoulduseatradewithinadailytablethatthestopskipped,soitmustnotbelabelledanobservedbreach. Therouterauditdoesnotrepairtheseseparateaccountapproximations. Retaintheselimitsbeforeanypaper/livepromotion.</p><h2>Legacyandcausalbaseline</h2><pre>'+html.escape(json.dumps(dict(legacy=legacy_metrics,causal=baseline_all),indent=2))+'</pre><p><a href="../runs/gemini_stack_continuation_v1/protocol.json">Frozenprotocol</a> · <a href="../runs/gemini_stack_continuation_v1/all_earlier_training_candidates.csv">All31discoverycells</a> · <a href="GEMINI_STACK_CONTINUATION_TRAIN.json">Fullresults</a> · <a href="GEMINI_STACK_CONTINUATION_TRAIN_verification.json">Verification</a></p></html>'
    (ROOT/'reports/GEMINI_STACK_CONTINUATION_TRAIN.html').write_text(page,encoding='utf-8')
    print('FINAL',json.dumps(dict(candidates=len(configs),accepted=accepted,choice=choice,legacy_mean=legacy_metrics['S0']['mean_withdrawals'],causal_full_mean=baseline_all['S0']['mean_withdrawals'],earlier_lift=lift_early,later_lift=lift_later,earlier_eligible=len(eligible))),flush=True)


if __name__=='__main__':main()
